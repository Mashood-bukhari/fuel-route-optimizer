import json
import math
import os
import urllib.request
import urllib.parse
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

# Helper: Haversine distance in miles
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8  # Earth radius in miles
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Helper: Geocode location via Nominatim
def geocode(location_name):
    # Search within USA for better geocoding accuracy
    query = f"{location_name}, USA" if "USA" not in location_name else location_name
    base_url = getattr(settings, 'NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
    url = f"{base_url}/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    
    # We must use a browser-like User-Agent to avoid 403 Forbidden errors
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Referer': 'https://google.com/'
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if not data:
                return None
            return {
                'lat': float(data[0]['lat']),
                'lng': float(data[0]['lon']),
                'name': data[0]['display_name']
            }
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

# Helper: Get driving route via OSRM
def get_route(start_lat, start_lng, finish_lat, finish_lng):
    base_url = getattr(settings, 'OSRM_URL', 'https://router.project-osrm.org')
    url = f"{base_url}/route/v1/driving/{start_lng},{start_lat};{finish_lng},{finish_lat}?overview=full&geometries=geojson"
    
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('code') != 'Ok':
                return None
            
            route = data['routes'][0]
            # Convert coordinates from [lng, lat] to [lat, lng] for Leaflet
            coords = [[pt[1], pt[0]] for pt in route['geometry']['coordinates']]
            distance_meters = route['distance']
            return coords, distance_meters
    except Exception as e:
        print(f"Routing error: {e}")
        return None

# Core logic: Find optimal fuel route using Dynamic Programming
def find_optimal_fuel_route(start_lat, start_lng, finish_lat, finish_lng, start_name, finish_name, stop_penalty=5.0):
    # 1. Get driving route
    route_result = get_route(start_lat, start_lng, finish_lat, finish_lng)
    if not route_result:
        return None, "Failed to calculate driving route between locations."
        
    route_coords, distance_meters = route_result
    total_distance_miles = distance_meters * 0.000621371
    
    # Calculate cumulative distance along route points
    route_distances = [0.0]
    for i in range(1, len(route_coords)):
        prev = route_coords[i-1]
        curr = route_coords[i]
        d = haversine(prev[0], prev[1], curr[0], curr[1])
        route_distances.append(route_distances[-1] + d)
        
    # 2. Load and deduplicate fuel stops database
    db_path = os.path.join(settings.BASE_DIR, 'fuel_stops_geocoded.json')
    if not os.path.exists(db_path):
        return None, "Fuel stops database not found."
        
    with open(db_path, 'r', encoding='utf-8') as f:
        all_stops = json.load(f)
        
    # Deduplicate stops by keeping the minimum price for each unique OPIS ID
    unique_stops = {}
    for stop in all_stops:
        key = stop['id']
        if key not in unique_stops or stop['price'] < unique_stops[key]['price']:
            unique_stops[key] = stop
    fuel_stops = list(unique_stops.values())
    
    # 3. Filter fuel stops using route bounding box with padding (approx 15 miles)
    lats = [c[0] for c in route_coords]
    lngs = [c[1] for c in route_coords]
    lat_min, lat_max = min(lats) - 0.22, max(lats) + 0.22
    lng_min, lng_max = min(lngs) - 0.22, max(lngs) + 0.22
    
    candidates = []
    for stop in fuel_stops:
        if lat_min <= stop['latitude'] <= lat_max and lng_min <= stop['longitude'] <= lng_max:
            candidates.append(stop)
            
    # 4. Map fuel stops to their closest projection on the route
    accessible_stops = []
    for stop in candidates:
        # Euclidean quick check to find closest route point index
        best_idx = min(range(len(route_coords)), key=lambda idx: (route_coords[idx][0] - stop['latitude'])**2 + (route_coords[idx][1] - stop['longitude'])**2)
        # Calculate exact Haversine distance
        dist_to_route = haversine(stop['latitude'], stop['longitude'], route_coords[best_idx][0], route_coords[best_idx][1])
        
        # Consider stops within 10 miles of the route
        if dist_to_route <= 10.0:
            stop_copy = stop.copy()
            stop_copy['distance_from_start'] = route_distances[best_idx]
            stop_copy['distance_to_route'] = dist_to_route
            accessible_stops.append(stop_copy)
            
    # 5. Sort stops by distance from start along the route
    accessible_stops.sort(key=lambda s: s['distance_from_start'])
    
    # 6. Deduplicate stops that are within 5 miles of each other along the route, keeping the cheapest
    filtered_stops = []
    for stop in accessible_stops:
        found_close = False
        for idx, existing in enumerate(filtered_stops):
            if abs(existing['distance_from_start'] - stop['distance_from_start']) <= 5.0:
                found_close = True
                if stop['price'] < existing['price']:
                    filtered_stops[idx] = stop
                break
        if not found_close:
            filtered_stops.append(stop)
    accessible_stops = filtered_stops
    
    # 7. Construct nodes list: Start node, intermediate accessible stops, Destination node
    nodes = []
    # Start node
    nodes.append({
        'id': 'START',
        'name': 'Start Location',
        'address': start_name,
        'city': '',
        'state': '',
        'price': 0.0,
        'latitude': start_lat,
        'longitude': start_lng,
        'distance_from_start': 0.0
    })
    nodes.extend(accessible_stops)
    # Destination node
    nodes.append({
        'id': 'DESTINATION',
        'name': 'Finish Location',
        'address': finish_name,
        'city': '',
        'state': '',
        'price': 0.0,
        'latitude': finish_lat,
        'longitude': finish_lng,
        'distance_from_start': total_distance_miles
    })
    
    # 8. Run Dynamic Programming to find the optimal refueling schedule
    M = len(accessible_stops)
    dp = [float('inf')] * (M + 2)
    next_stop = [-1] * (M + 2)
    
    dp[M+1] = 0.0
    
    for i in range(M, -1, -1):
        x_i = nodes[i]['distance_from_start']
        p_i = nodes[i]['price']
        
        # Option A: Check if destination is reachable directly
        x_dest = nodes[M+1]['distance_from_start']
        if x_dest - x_i <= 500.0:
            if i == 0:
                dp[i] = 0.0
                next_stop[i] = M+1
            else:
                dp[i] = ((x_dest - x_i) / 10.0) * p_i
                next_stop[i] = M+1
                
        # Option B: Check reachable intermediate stops
        for j in range(i + 1, M + 1):
            x_j = nodes[j]['distance_from_start']
            if x_j - x_i > 500.0:
                break # Further stops are out of range
                
            if i == 0:
                cost = dp[j] + stop_penalty
            else:
                cost = ((x_j - x_i) / 10.0) * p_i + dp[j] + stop_penalty
                
            if cost < dp[i]:
                dp[i] = cost
                next_stop[i] = j
                
    # If starting position cannot reach destination and no valid path exists
    if dp[0] == float('inf'):
        return None, "No feasible refueling path. Gap between available fuel stops exceeds the 500-mile vehicle range."
        
    # 9. Reconstruct the optimal sequence of stops
    optimal_stops = []
    curr = next_stop[0]
    while curr != M+1 and curr != -1:
        optimal_stops.append(nodes[curr])
        curr = next_stop[curr]
        
    # 10. Calculate the exact fuel cost (excluding stopping penalty)
    total_fuel_cost = 0.0
    curr_pos = 0.0
    for idx, stop in enumerate(optimal_stops):
        if idx > 0:
            gallons = (stop['distance_from_start'] - curr_pos) / 10.0
            total_fuel_cost += gallons * optimal_stops[idx-1]['price']
        curr_pos = stop['distance_from_start']
        
    # Final leg cost from last stop to destination
    if optimal_stops:
        gallons = (total_distance_miles - curr_pos) / 10.0
        total_fuel_cost += gallons * optimal_stops[-1]['price']
    else:
        total_fuel_cost = 0.0
        
    result = {
        'total_distance_miles': total_distance_miles,
        'total_fuel_cost': total_fuel_cost,
        'fuel_stops': optimal_stops,
        'route_geometry': route_coords,
        'start_location': {
            'name': start_name,
            'latitude': start_lat,
            'longitude': start_lng
        },
        'finish_location': {
            'name': finish_name,
            'latitude': finish_lat,
            'longitude': finish_lng
        }
    }
    return result, None

# View: REST API endpoint
def route_api(request):
    start = request.GET.get('start', '').strip()
    finish = request.GET.get('finish', '').strip()
    penalty_str = request.GET.get('penalty', '5.0').strip()
    
    if not start or not finish:
        return JsonResponse({'error': 'Both start and finish query parameters are required.'}, status=400)
        
    try:
        stop_penalty = float(penalty_str)
    except ValueError:
        stop_penalty = 5.0
        
    # Geocode locations
    start_info = geocode(start)
    if not start_info:
        return JsonResponse({'error': f"Failed to geocode start location: '{start}'"}, status=400)
        
    finish_info = geocode(finish)
    if not finish_info:
        return JsonResponse({'error': f"Failed to geocode finish location: '{finish}'"}, status=400)
        
    # Calculate route
    result, error_msg = find_optimal_fuel_route(
        start_info['lat'], start_info['lng'],
        finish_info['lat'], finish_info['lng'],
        start_info['name'], finish_info['name'],
        stop_penalty=stop_penalty
    )
    
    if error_msg:
        return JsonResponse({'error': error_msg}, status=400)
        
    return JsonResponse(result)

# View: Interactive Map Frontend
def index(request):
    return render(request, 'optimizer/index.html')
