from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from optimizer.views import haversine, find_optimal_fuel_route

class FuelRouteOptimizerTests(TestCase):
    
    def test_haversine_distance(self):
        # Coordinates of NY and LA
        ny_lat, ny_lng = 40.7128, -74.0060
        la_lat, la_lng = 34.0522, -118.2437
        
        # Expected distance is approx 2445-2450 miles
        dist = haversine(ny_lat, ny_lng, la_lat, la_lng)
        self.assertTrue(2440 <= dist <= 2460)

    def test_haversine_zero_distance(self):
        # Distance to itself should be 0
        dist = haversine(40.7128, -74.0060, 40.7128, -74.0060)
        self.assertEqual(dist, 0.0)

    @patch('optimizer.views.get_route')
    def test_optimal_route_calculation_short(self, mock_get_route):
        # Mock OSRM to return a short route (100 miles)
        # 100 miles is less than 500 miles, so no fuel stops are needed.
        mock_get_route.return_value = (
            [[40.7128, -74.0060], [40.2000, -74.5000], [39.9526, -75.1652]],  # coordinates
            160934  # 100 miles in meters
        )
        
        result, error = find_optimal_fuel_route(
            40.7128, -74.0060, 39.9526, -75.1652,
            "Start", "End",
            stop_penalty=5.0
        )
        
        self.assertIsNone(error)
        self.assertEqual(len(result['fuel_stops']), 0)
        self.assertEqual(result['total_fuel_cost'], 0.0)
        self.assertTrue(99.0 <= result['total_distance_miles'] <= 101.0)

    @patch('optimizer.views.get_route')
    def test_optimal_route_calculation_impossible_gap(self, mock_get_route):
        # Route is 1200 miles, but let's assume no fuel stops are within range (empty database / filtered out)
        # This should return an error stating no feasible refueling path exists.
        mock_get_route.return_value = (
            [[40.0, -74.0], [35.0, -80.0], [30.0, -90.0]],
            1931212  # 1200 miles in meters
        )
        
        # We will patch load_stops or just let it run with empty candidates
        with patch('json.load') as mock_json_load:
            # Empty list of stops
            mock_json_load.return_value = []
            
            result, error = find_optimal_fuel_route(
                40.0, -74.0, 30.0, -90.0,
                "Start", "End",
                stop_penalty=5.0
            )
            
            self.assertIsNone(result)
            self.assertIn("No feasible refueling path", error)

    def test_api_validation_errors(self):
        client = Client()
        # Missing start and finish parameters
        response = client.get(reverse('route_api'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.json()['error'])

        # Missing finish parameter
        response = client.get(reverse('route_api') + "?start=New+York")
        self.assertEqual(response.status_code, 400)
        
    @patch('optimizer.views.geocode')
    def test_api_geocoding_failure(self, mock_geocode):
        # Geocoding returns None
        mock_geocode.return_value = None
        client = Client()
        
        response = client.get(reverse('route_api') + "?start=NonexistentPlace&finish=Miami")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Failed to geocode", response.json()['error'])
