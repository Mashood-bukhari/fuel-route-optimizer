import csv
import json

# Hardcoded coordinates for the few unmatched US cities
hardcoded_coordinates = {
    ('elizabethport', 'NJ'): (40.6482, -74.1915),
    ('university park', 'IL'): (41.4464, -87.6848),
    ('port wentworth', 'GA'): (32.1491, -81.1632),
    ('evergreen', 'AL'): (31.4346, -86.9544),
    ('henrico', 'VA'): (37.5407, -77.4360),
    ('brookpark', 'OH'): (41.3989, -81.8157),
}

us_states = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
    'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA',
    'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
}

def load_cities():
    cities = {}
    with open('us_cities.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['CITY'].strip().lower(), row['STATE_CODE'].strip().upper())
            cities[key] = (float(row['LATITUDE']), float(row['LONGITUDE']))
    return cities

def main():
    cities = load_cities()
    stops = []
    skipped = 0
    
    with open('fuel-prices-for-be-assessment.csv', mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_raw = row['City'].strip()
            city = city_raw.lower()
            state = row['State'].strip().upper()
            
            if state not in us_states:
                # Skip non-US stops
                skipped += 1
                continue
                
            lat, lng = None, None
            key = (city, state)
            
            if key in cities:
                lat, lng = cities[key]
            elif key in hardcoded_coordinates:
                lat, lng = hardcoded_coordinates[key]
            else:
                # Fallback check for any padded strings in City
                city_clean = city_raw.strip().lower()
                clean_key = (city_clean, state)
                if clean_key in cities:
                    lat, lng = cities[clean_key]
                elif clean_key in hardcoded_coordinates:
                    lat, lng = hardcoded_coordinates[clean_key]
                else:
                    print(f"Warning: Could not geocode {city_raw}, {state}")
                    skipped += 1
                    continue
            
            try:
                price = float(row['Retail Price'])
            except ValueError:
                print(f"Warning: Invalid price for stop {row['OPIS Truckstop ID']}: {row['Retail Price']}")
                continue
                
            stops.append({
                'id': row['OPIS Truckstop ID'].strip(),
                'name': row['Truckstop Name'].strip(),
                'address': row['Address'].strip(),
                'city': city_raw,
                'state': state,
                'price': price,
                'latitude': lat,
                'longitude': lng
            })
            
    # Write to JSON
    with open('fuel_stops_geocoded.json', 'w', encoding='utf-8') as out_f:
        json.dump(stops, out_f, indent=2)
        
    print(f"Preprocessed {len(stops)} US fuel stops. Skipped {skipped} stops.")

if __name__ == '__main__':
    main()
