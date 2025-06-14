from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import heapq
import requests
from dotenv import load_dotenv
import polyline

load_dotenv()  

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['OPENWEATHER_API_KEY'] = os.getenv('OPENWEATHER_API_KEY', '822df8fa8103d34127595d59a565e52c')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    favorite_routes = db.relationship('FavoriteRoute', backref='user', lazy=True)

class FavoriteRoute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Build the graph with real distances as weights
def build_real_distance_graph(base_graph, coordinates):
    real_graph = {}
    for src, neighbors in base_graph.items():
        real_graph[src] = {}
        for dest in neighbors:
            coord1 = coordinates[src]
            coord2 = coordinates[dest]
            real_graph[src][dest] = round(geodesic(coord1, coord2).km, 2)
    return real_graph

# 1. Define coordinates first
coordinates = {
    'Forest Research Institute': (30.3547, 77.9470),
    'Paltan Bazaar': (30.3252, 78.0430),
    'ISBT Dehradun': (30.2901, 78.0535),
    'Clock Tower': (30.3256, 78.0437),
    'Rajpur Road': (30.3700, 78.0800),
    'Pacific Mall': (30.3915, 78.0782),
    'Dehradun Railway Station': (30.3155, 78.0322),
    'Robber\'s Cave': (30.3792, 78.0595),
    'Sahastradhara': (30.3956, 78.1317),
    'Mussoorie Road': (30.4022, 78.0747),
    'Doon University': (30.3544, 77.9368),
    'Graphic Era University': (30.2722, 78.0796),
    'Max Hospital': (30.3250, 78.0419),
    'Parade Ground': (30.3258, 78.0445),
    'Gandhi Park': (30.3257, 78.0447),
    'Tapkeshwar Temple': (30.3342, 78.0081),
}

# 2. Define base_graph with more realistic direct connections
base_graph = {
    'Forest Research Institute': { 'Paltan Bazaar': 1, 'ISBT Dehradun': 1, 'Pacific Mall': 1 },
    'Paltan Bazaar': { 'Forest Research Institute': 1, 'ISBT Dehradun': 1, 'Clock Tower': 1, 'Gandhi Park': 1 },
    'ISBT Dehradun': { 'Forest Research Institute': 1, 'Paltan Bazaar': 1, 'Clock Tower': 1, 'Graphic Era University': 1, 'Dehradun Railway Station': 1 },
    'Clock Tower': { 'Paltan Bazaar': 1, 'ISBT Dehradun': 1, 'Rajpur Road': 1, 'Gandhi Park': 1 },
    'Rajpur Road': { 'Clock Tower': 1, 'Pacific Mall': 1, 'Mussoorie Road': 1 },
    'Pacific Mall': { 'Rajpur Road': 1, 'Dehradun Railway Station': 1, 'Forest Research Institute': 1 },
    'Dehradun Railway Station': { 'Pacific Mall': 1, 'Robber\'s Cave': 1, 'ISBT Dehradun': 1 },
    'Robber\'s Cave': { 'Dehradun Railway Station': 1, 'Sahastradhara': 1 },
    'Sahastradhara': { 'Robber\'s Cave': 1, 'Mussoorie Road': 1 },
    'Mussoorie Road': { 'Sahastradhara': 1, 'Doon University': 1, 'Rajpur Road': 1 },
    'Doon University': { 'Mussoorie Road': 1, 'Graphic Era University': 1 },
    'Graphic Era University': { 'Doon University': 1, 'Max Hospital': 1, 'ISBT Dehradun': 1 },
    'Max Hospital': { 'Graphic Era University': 1, 'Parade Ground': 1 },
    'Parade Ground': { 'Max Hospital': 1, 'Gandhi Park': 1 },
    'Gandhi Park': { 'Parade Ground': 1, 'Tapkeshwar Temple': 1, 'Clock Tower': 1, 'Paltan Bazaar': 1 },
    'Tapkeshwar Temple': { 'Gandhi Park': 1 },
}

# 3. Build the real distance graph
graph = build_real_distance_graph(base_graph, coordinates)

# Use the full set of locations for location_map
location_map = {name: name for name in coordinates.keys()}

# Update dijkstra to work with this graph

def dijkstra(graph, start, end):
    distances = {node: float('inf') for node in graph}
    previous = {node: None for node in graph}
    distances[start] = 0
    unvisited = set(graph.keys())
    while unvisited:
        current = min(unvisited, key=lambda node: distances[node])
        if distances[current] == float('inf') or current == end:
            break
        unvisited.remove(current)
        for neighbor, weight in graph[current].items():
            alt = distances[current] + weight
            if alt < distances[neighbor]:
                distances[neighbor] = alt
                previous[neighbor] = current
    # Reconstruct path
    path = []
    curr = end
    while curr:
        path.insert(0, curr)
        curr = previous[curr]
    if path and path[0] == start:
        return distances[end], path
    else:
        return float('inf'), []

def get_weather_data(location_name):
    try:
        # Use coordinates directly if available
        coord = coordinates.get(location_name)
        if coord:
            lat, lon = coord
        else:
            # Fallback to geocoding
            geolocator = Nominatim(user_agent="travel_planner")
            location = geolocator.geocode(location_name + ", Dehradun, India")
            print(f"Geocoding '{location_name}':", location)
            if not location:
                print(f"Geocoding failed for: {location_name}")
                return None
            lat, lon = location.latitude, location.longitude
        # Get weather data from OpenWeatherMap API
        api_key = app.config['OPENWEATHER_API_KEY']
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        print(f"Weather API URL: {url}")
        response = requests.get(url)
        print(f"Weather API status code: {response.status_code}")
        if response.status_code == 200:
            weather_data = response.json()
            print(f"Weather data for {location_name}: {weather_data}")
            return {
                'temperature': round(weather_data['main']['temp']),
                'feels_like': round(weather_data['main']['feels_like']),
                'humidity': weather_data['main']['humidity'],
                'description': weather_data['weather'][0]['description'],
                'wind_speed': weather_data['wind']['speed'],
                'icon': weather_data['weather'][0]['icon']
            }
        else:
            print(f"Weather API error for {location_name}: {response.text}")
        return None
    except Exception as e:
        print(f"Error fetching weather data for {location_name}: {str(e)}")
        return None

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login_page():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user.password):
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=1)
        }, app.config['SECRET_KEY'])
        return jsonify({'token': token}), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
        
    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    new_user = User(username=data['username'], email=data['email'], password=hashed_password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'message': 'User created successfully'}), 201

def is_in_dehradun(location):
    if not location:
        return False
    address = location.raw.get('display_name', '').lower()
    return 'dehradun' in address

def calculate_real_distance(path, coordinates):
    total_distance = 0
    for i in range(len(path) - 1):
        coord1 = coordinates[path[i]]
        coord2 = coordinates[path[i+1]]
        total_distance += geodesic(coord1, coord2).km
    return round(total_distance, 2)

# Add this function to get real route from OpenRouteService

def get_real_route_ors(source, destination):
    ors_api_key = '5b3ce3597851110001cf62480a414c147a414e068ac670e64b9c1e55'
    if not ors_api_key:
        print('OpenRouteService API key not set!')
        return None, None, None
    src_coords = coordinates[source][::-1]  # (lon, lat)
    dest_coords = coordinates[destination][::-1]  # (lon, lat)
    url = 'https://api.openrouteservice.org/v2/directions/driving-car'
    headers = {
        'Authorization': ors_api_key,
        'Content-Type': 'application/json'
    }
    body = {
        'coordinates': [src_coords, dest_coords]
    }
    try:
        response = requests.post(url, headers=headers, json=body)
        if response.status_code == 200:
            data = response.json()
            summary = data['routes'][0]['summary']
            distance_km = round(summary['distance'] / 1000, 2)
            duration_min = int(summary['duration'] / 60)
            # Decode the polyline string into a list of [lat, lon] pairs
            polyline_string = data['routes'][0]['geometry']
            polyline_coords = polyline.decode(polyline_string)
            return distance_km, duration_min, polyline_coords
        else:
            print('ORS error:', response.text)
        return None, None, None
    except Exception as e:
        print('ORS exception:', str(e))
        return None, None, None

# Points of Interest data
points_of_interest = {
    "A": [
        {"name": "Café Coffee Day", "type": "food", "rating": 4.2},
        {"name": "Book Store", "type": "shopping", "rating": 4.0}
    ],
    "B": [
        {"name": "City Park", "type": "attraction", "rating": 4.5},
        {"name": "Museum", "type": "attraction", "rating": 4.3}
    ],
    "C": [
        {"name": "Shopping Mall", "type": "shopping", "rating": 4.1},
        {"name": "Restaurant", "type": "food", "rating": 4.4}
    ],
    "D": [
        {"name": "Hotel", "type": "accommodation", "rating": 4.0},
        {"name": "Local Market", "type": "shopping", "rating": 4.2}
    ]
}

@app.route('/nearby-places', methods=['POST'])
def get_nearby_places():
    data = request.json
    location = data.get('location')
    
    if not location:
        return jsonify({'error': 'Invalid location'}), 400
    
    poi_type = data.get('type', 'all')
    places = points_of_interest.get(location, [])
    
    if poi_type != 'all':
        places = [place for place in places if place['type'] == poi_type]
    
    # Sort by rating
    places.sort(key=lambda x: x['rating'], reverse=True)
    
    return jsonify({
        'location': location,
        'places': places
    }), 200


def fuel_price(distance, petrol_price_per_litre=100, mileage=40):
    both_side_distance = distance * 2
    both_distance_petrol_consumption = both_side_distance / mileage
    petrol_consumption_total_price = both_distance_petrol_consumption * petrol_price_per_litre
    return round(petrol_consumption_total_price, 2)  


@app.route('/route', methods=['POST'])
def route():
    data = request.json
    user_input_source = data.get('source')
    user_input_destination = data.get('destination')

    src_node = location_map.get(user_input_source)
    dest_node = location_map.get(user_input_destination)

    if not src_node or not dest_node:
        return jsonify({'error': 'Invalid location selected. Please choose from: ' + ', '.join(location_map.keys())}), 400

    if src_node not in graph or dest_node not in graph:
        return jsonify({'error': 'Source or destination not found in the graph.'}), 400

    dijkstra_distance, path = dijkstra(graph, src_node, dest_node)
    if dijkstra_distance == float("inf"):
        return jsonify({'error': 'No route found'}), 404

    # Use the actual path to sum the real geodesic distances
    distance = calculate_real_distance(path, coordinates)
    time = round(distance / 40, 2)
    hours = int(time)
    minutes = int((time - hours) * 60)

    if hours > 0:
        time_str = f"{hours} hours {minutes} minutes"
    else:
        time_str = f"{minutes} minutes"

    # Add weather data for source and destination
    weather = {
        'source': get_weather_data(user_input_source),
        'destination': get_weather_data(user_input_destination)
    }

    # Add fuel budget
    fuel_budget = fuel_price(distance)

    # Get real road-following polyline from ORS
    ors_distance, ors_duration, polyline_coords = get_real_route_ors(user_input_source, user_input_destination)
    if not polyline_coords or len(polyline_coords) < 2:
        # Fallback: use the path from the graph (at least two points)
        polyline_coords = [coordinates[loc] for loc in path]
        if len(polyline_coords) < 2:
            polyline_coords = [coordinates[user_input_source], coordinates[user_input_destination]]

    return jsonify({
        'distance': distance,
        'path': path,
        'time': time_str,
        'fuel_budget': fuel_budget,
        'weather': weather,
        'polyline_coords': polyline_coords
    })


@app.route('/traffic-update', methods=['GET'])
def get_traffic_update():
    # Simulated traffic conditions (in a real app, this would come from a traffic API)
    traffic_conditions = {
        "A": {"status": "moderate", "delay": 5},  # 5 minutes delay
        "B": {"status": "heavy", "delay": 15},
        "C": {"status": "light", "delay": 2},
        "D": {"status": "moderate", "delay": 8}
    }
    return jsonify(traffic_conditions), 200

@app.route('/alternative-routes', methods=['POST'])
def get_alternative_routes():
    data = request.json
    source = data.get('source')
    destination = data.get('destination')
    
    if not source or not destination:
        return jsonify({'error': 'Invalid locations'}), 400
    
    # Get all possible paths using a modified Dijkstra's algorithm
    def get_all_paths(graph, start, end, max_paths=3):
        paths = []
        queue = [(0, start, [])]
        seen = set()
        
        while queue and len(paths) < max_paths:
            (cost, node, path) = heapq.heappop(queue)
            if node in seen:
                continue
            path = path + [node]
            if node == end:
                paths.append((cost, path))
            seen.add(node)
            for (neighbor, weight) in graph.get(node, []):
                if neighbor not in seen:
                    heapq.heappush(queue, (cost + weight, neighbor, path))
        return paths
    
    alternative_routes = get_all_paths(graph, source, destination)
    return jsonify([{
        'distance': dist,
        'path': path,
        'time': f"{int(dist/40)} hours {int((dist/40 % 1) * 60)} minutes"
    } for dist, path in alternative_routes]), 200

@app.route('/favorite-route', methods=['POST'])
@login_required
def add_favorite_route():
    data = request.get_json()
    new_favorite = FavoriteRoute(
        user_id=current_user.id,
        source=data['source'],
        destination=data['destination']
    )
    db.session.add(new_favorite)
    db.session.commit()
    return jsonify({'message': 'Route added to favorites'}), 201

@app.route('/favorite-routes', methods=['GET'])
@login_required
def get_favorite_routes():
    favorites = FavoriteRoute.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': fav.id,
        'source': fav.source,
        'destination': fav.destination,
        'created_at': fav.created_at.isoformat()
    } for fav in favorites]), 200

@app.route('/favorite-route/<int:route_id>', methods=['DELETE'])
@login_required
def delete_favorite_route(route_id):
    favorite = FavoriteRoute.query.get_or_404(route_id)
    if favorite.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(favorite)
    db.session.commit()
    return jsonify({'message': 'Route removed from favorites'}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 
