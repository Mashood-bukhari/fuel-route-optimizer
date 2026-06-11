# Fuel Route Optimizer

An advanced, cost-effective US route planner built with **Django 6** and **Leaflet JS**. This application calculates the optimal route between any two locations in the USA, identifies optimal locations to refuel based on local prices, and provides a beautiful interactive map detailing the trip itinerary.

---

## 🌟 Key Features

*   **Optimal Refueling Schedule**: Assumes a maximum vehicle range of 500 miles and calculates the exact locations to stop for fuel to minimize the total trip cost.
*   **Offline Gas Station Database**: Preprocessed and geocoded all 7,531 US fuel stops from the dataset using a customized matching algorithm, resulting in **zero runtime geocoding requests** for gas stations and lightning-fast calculations.
*   **Convenience vs. Cost Optimization**: Employs a custom Dynamic Programming (DP) engine with a configurable "Stop Penalty" ($0 - $25) to avoid excessive stops for negligible savings.
*   **Interactive Visual Map**: Displays route path via OSRM (Open Source Routing Machine), markers for start/finish points, and markers for each fuel stop with detailed popups.
*   **Responsive Sidebar UI**: Shows key metrics (Total Cost, Distance, Refueling Count) alongside a step-by-step timeline itinerary.

---

## 🛠️ Restructured Django Layout

The project has been rearranged to follow the standard, clean Django style:

```text
fuel-route-optimizer/
├── manage.py
├── preprocess.py
├── fuel-prices-for-be-assessment.csv
├── fuel_stops_geocoded.json
├── us_cities.csv
├── db.sqlite3
├── fuel_route_optimizer/       # Main Django project configuration
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── optimizer/                  # Refueling & routing application
│   ├── migrations/
│   ├── templates/
│   │   └── optimizer/
│   │       └── index.html      # Interactive frontend map page
│   ├── __init__.py
│   ├── apps.py
│   ├── tests.py                # Unit test suite
│   └── views.py                # Core API, geocoding and DP views
└── venv/                       # Virtual environment
```

---

## 📐 Algorithm Design

### 1. Spatial Filtering
With over 7,500 gas stations in the database, evaluating every station against thousands of coordinates along the route would be slow.
*   **Bounding Box Filter**: We calculate the bounding box of the route coordinates and pad it by ~15 miles. Only gas stations within this bounding box are considered candidates.
*   **Euclidean Snapping**: For candidate stations, we use a fast squared-distance Euclidean calculation in coordinate space to locate the nearest point on the route.
*   **Haversine Projection**: The exact distance from the station to the route is verified using the Haversine formula. Stations within 10 miles are considered accessible and mapped to their distance along the route.
*   **Local Deduplication**: To avoid multiple redundant stops at the same highway exit, stations within 5 miles of each other along the route are grouped, keeping only the cheapest station.

### 2. Refueling Optimization via Dynamic Programming
We define the optimization problem as finding the sequence of stops that minimizes the total cost of fuel consumed.
Let $DP[i]$ be the minimum cost to reach the destination from station $i$ (with a full tank at station $i$).
$$DP[i] = \min \left( \text{cost\_to\_dest}(i), \min_{j} \left\{ \text{cost}(i \to j) + DP[j] + \text{stop\_penalty} \right\} \right)$$
*   **Base Case**: If the destination is reachable from $i$ within 500 miles, $\text{cost\_to\_dest}(i)$ is calculated directly.
*   **Recurrence**: For each reachable station $j$ (where $x_j - x_i \le 500$ miles), the cost of fuel consumed to travel from $i$ to $j$ is charged at the rate $p_i$ of station $i$. We add the $DP[j]$ cost to finish the trip and a `stop_penalty` to penalize the time/overhead of making a stop.
*   **Start Node**: The vehicle starts with a full tank of fuel at distance 0, meaning the travel to the first chosen stop $j$ consumes fuel already in the tank, incurring $\$0$ cost (excluding the stopping penalty).

---

## 🚀 Getting Started

### 1. Set Up Environment
Create and activate the virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Preprocess Gas Station Database
To verify or regenerate the geocoded fuel stops JSON:
```bash
python3 preprocess.py
```
This maps the CSV data to city/state coordinates in `us_cities.csv` and outputs `fuel_stops_geocoded.json` in milliseconds.

### 3. Run migrations and dev server
```bash
python3 manage.py migrate
python3 manage.py runserver
```
Visit the interactive UI at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### 4. Run tests
To execute the suite of unit tests verifying geocoding, OSRM routing integration, DP calculations, and API inputs:
```bash
python3 manage.py test
```

---

## 🔌 API Endpoint Documentation

### Calculate Route
*   **Endpoint**: `GET /api/route/`
*   **Query Parameters**:
    *   `start` (string, required): Starting location (e.g., `"New York, NY"`)
    *   `finish` (string, required): Ending location (e.g., `"Miami, FL"`)
    *   `penalty` (float, optional): Stop penalty value in dollars. Default is `5.0`.

#### Sample Success Response (`GET /api/route/?start=New+York,+NY&finish=Miami,+FL`)
```json
{
  "total_distance_miles": 1279.3295050849,
  "total_fuel_cost": 235.094795184193,
  "start_location": {
    "name": "New York, New York, United States",
    "latitude": 40.7127281,
    "longitude": -74.0060152
  },
  "finish_location": {
    "name": "Miami, Florida, United States",
    "latitude": 25.7741728,
    "longitude": -80.19362
  },
  "fuel_stops": [
    {
      "id": "71161",
      "name": "CIRCLE K #2720931",
      "address": "I-95, EXIT 107 & US-301",
      "city": "Kenly",
      "state": "NC",
      "price": 3.149,
      "latitude": 35.607742,
      "longitude": -78.138227,
      "distance_from_start": 487.3109809804735,
      "distance_to_route": 0.5463821003966486
    },
    {
      "id": "72975",
      "name": "SHEETZ #804",
      "address": "I-95, Exit 41",
      "city": "Hope Mills",
      "state": "NC",
      "price": 2.859,
      "latitude": 34.953564,
      "longitude": -78.935364,
      "distance_from_start": 554.3472629598954,
      "distance_to_route": 1.2673864923398315
    },
    {
      "id": "52431",
      "name": "WOODBINE TRAVEL CENTER",
      "address": "I-95, EXIT 14",
      "city": "Woodbine",
      "state": "GA",
      "price": 3.03233333,
      "latitude": 30.943692,
      "longitude": -81.678313,
      "distance_from_start": 892.0573909772392,
      "distance_to_route": 0.20364928739989805
    }
  ],
  "route_geometry": [
    [40.712118, -74.005737],
    [40.712113, -74.005758],
    ...
  ]
}
```

#### Sample Error Response (400 Bad Request)
```json
{
  "error": "No feasible refueling path. Gap between available fuel stops exceeds the 500-mile vehicle range."
}
```
