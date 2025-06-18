from flask import Flask, request, jsonify, render_template
from flask_pymongo import PyMongo
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
from bson.objectid import ObjectId

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/travel_planner'
app.config['OPENWEATHER_API_KEY'] = os.getenv('OPENWEATHER_API_KEY', '822df8fa8103d34127595d59a565e52c')

mongo = PyMongo(app)
login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None


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

base_graph = {
    'Forest Research Institute': {'Paltan Bazaar': 1, 'ISBT Dehradun': 1, 'Pacific Mall': 1},
    'Paltan Bazaar': {'Forest Research Institute': 1, 'ISBT Dehradun': 1, 'Clock Tower': 1, 'Gandhi Park': 1},
    'ISBT Dehradun': {'Forest Research Institute': 1, 'Paltan Bazaar': 1, 'Clock Tower': 1, 'Graphic Era University': 1, 'Dehradun Railway Station': 1},
    'Clock Tower': {'Paltan Bazaar': 1, 'ISBT Dehradun': 1, 'Rajpur Road': 1, 'Gandhi Park': 1},
    'Rajpur Road': {'Clock Tower': 1, 'Pacific Mall': 1, 'Mussoorie Road': 1},
    'Pacific Mall': {'Rajpur Road': 1, 'Dehradun Railway Station': 1, 'Forest Research Institute': 1},
    'Dehradun Railway Station': {'Pacific Mall': 1, 'Robber\'s Cave': 1, 'ISBT Dehradun': 1},
    'Robber\'s Cave': {'Dehradun Railway Station': 1, 'Sahastradhara': 1},
    'Sahastradhara': {'Robber\'s Cave': 1, 'Mussoorie Road': 1},
    'Mussoorie Road': {'Sahastradhara': 1, 'Doon University': 1, 'Rajpur Road': 1},
    'Doon University': {'Mussoorie Road': 1, 'Graphic Era University': 1},
    'Graphic Era University': {'Doon University': 1, 'Max Hospital': 1, 'ISBT Dehradun': 1},
    'Max Hospital': {'Graphic Era University': 1, 'Parade Ground': 1},
    'Parade Ground': {'Max Hospital': 1, 'Gandhi Park': 1},
    'Gandhi Park': {'Parade Ground': 1, 'Tapkeshwar Temple': 1, 'Clock Tower': 1, 'Paltan Bazaar': 1},
    'Tapkeshwar Temple': {'Gandhi Park': 1},
}

def build_real_distance_graph(base_graph, coordinates):
    real_graph = {}
    for src, neighbors in base_graph.items():
        real_graph[src] = {}
        for dest in neighbors:
            coord1 = coordinates[src]
            coord2 = coordinates[dest]
            real_graph[src][dest] = round(geodesic(coord1, coord2).km, 2)
    return real_graph

graph = build_real_distance_graph(base_graph, coordinates)
location_map = {name: name for name in coordinates.keys()}

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
    path = []
    curr = end
    while curr:
        path.insert(0, curr)
        curr = previous[curr]
    if path and path[0] == start:
        return distances[end], path
    else:
        return float('inf'), []

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if mongo.db.users.find_one({'username': data['username']}):
        return jsonify({'error': 'Username already exists'}), 400
        
    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    mongo.db.users.insert_one({
        'username': data['username'],
        'email': data['email'],
        'password': hashed_password
    })
    
    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = mongo.db.users.find_one({'username': data['username']})
    
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user['password']):
        token = jwt.encode({
            'user_id': str(user['_id']),
            'exp': datetime.utcnow() + timedelta(days=1)
        }, app.config['SECRET_KEY'])
        return jsonify({'token': token}), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/favorite-route', methods=['POST'])
@login_required
def add_favorite_route():
    data = request.get_json()
    mongo.db.favorite_routes.insert_one({
        'user_id': ObjectId(current_user.id),
        'source': data['source'],
        'destination': data['destination'],
        'created_at': datetime.utcnow()
    })
    return jsonify({'message': 'Route added to favorites'}), 201

@app.route('/favorite-routes', methods=['GET'])
@login_required
def get_favorite_routes():
    favorites = list(mongo.db.favorite_routes.find({'user_id': ObjectId(current_user.id)}))
    return jsonify([{
        'id': str(fav['_id']),
        'source': fav['source'],
        'destination': fav['destination'],
        'created_at': fav['created_at'].isoformat()
    } for fav in favorites]), 200

@app.route('/favorite-route/<route_id>', methods=['DELETE'])
@login_required
def delete_favorite_route(route_id):
    result = mongo.db.favorite_routes.delete_one({
        '_id': ObjectId(route_id),
        'user_id': ObjectId(current_user.id)
    })
    if result.deleted_count:
        return jsonify({'message': 'Route removed from favorites'}), 200
    return jsonify({'error': 'Route not found'}), 404

def get_weather_data(location_name):
    try:
        coord = coordinates.get(location_name)
        if coord:
            lat, lon = coord
        else:
            geolocator = Nominatim(user_agent="travel_planner")
            location = geolocator.geocode(location_name + ", Dehradun, India")
            if not location:
                return None
            lat, lon = location.latitude, location.longitude
        
        api_key = app.config['OPENWEATHER_API_KEY']
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        response = requests.get(url)
        
        if response.status_code == 200:
            weather_data = response.json()
            return {
                'temperature': round(weather_data['main']['temp']),
                'feels_like': round(weather_data['main']['feels_like']),
                'humidity': weather_data['main']['humidity'],
                'description': weather_data['weather'][0]['description'],
                'wind_speed': weather_data['wind']['speed'],
                'icon': weather_data['weather'][0]['icon']
            }
        return None
    except Exception as e:
        print(f"Error fetching weather data for {location_name}: {str(e)}")
        return None

def calculate_real_distance(path, coordinates):
    total_distance = 0
    for i in range(len(path) - 1):
        coord1 = coordinates[path[i]]
        coord2 = coordinates[path[i+1]]
        total_distance += geodesic(coord1, coord2).km
    return round(total_distance, 2)

def get_real_route_ors(source, destination):
    ors_api_key = '5b3ce3597851110001cf62480a414c147a414e068ac670e64b9c1e55'
    if not ors_api_key:
        print('OpenRouteService API key not set!')
        return None, None, None
    src_coords = coordinates[source][::-1]
    dest_coords = coordinates[destination][::-1]
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
            polyline_string = data['routes'][0]['geometry']
            polyline_coords = polyline.decode(polyline_string)
            return distance_km, duration_min, polyline_coords
        return None, None, None
    except Exception as e:
        print('ORS exception:', str(e))
        return None, None, None

def fuel_price(distance, petrol_price_per_litre=100, mileage=40):
    both_side_distance = distance * 2
    both_distance_petrol_consumption = both_side_distance / mileage
    petrol_consumption_total_price = both_distance_petrol_consumption * petrol_price_per_litre
    return round(petrol_consumption_total_price, 2)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login_page():
    return render_template('index.html')

@app.route('/guest')
def guest_page():
    return render_template('guest.html')

@app.route('/route', methods=['POST'])
def route():
    data = request.json
    user_input_source = data.get('source')
    user_input_destination = data.get('destination')

    if not user_input_source or not user_input_destination:
        return jsonify({'error': 'Source and destination are required'}), 400

    src_node = location_map.get(user_input_source)
    dest_node = location_map.get(user_input_destination)

    if not src_node or not dest_node:
        return jsonify({'error': 'Invalid location selected. Please choose from: ' + ', '.join(location_map.keys())}), 400

    if src_node not in graph or dest_node not in graph:
        return jsonify({'error': 'Source or destination not found in the graph.'}), 400

    dijkstra_distance, path = dijkstra(graph, src_node, dest_node)
    if dijkstra_distance == float("inf"):
        return jsonify({'error': 'No route found'}), 404

    distance = calculate_real_distance(path, coordinates)
    time = round(distance / 40, 2)
    hours = int(time)
    minutes = int((time - hours) * 60)

    if hours > 0:
        time_str = f"{hours} hours {minutes} minutes"
    else:
        time_str = f"{minutes} minutes"

    weather = {
        'source': get_weather_data(user_input_source),
        'destination': get_weather_data(user_input_destination)
    }

    fuel_budget = fuel_price(distance)

    ors_distance, ors_duration, polyline_coords = get_real_route_ors(user_input_source, user_input_destination)
    if not polyline_coords or len(polyline_coords) < 2:
        polyline_coords = [coordinates[loc] for loc in path]
        if len(polyline_coords) < 2:
            polyline_coords = [coordinates[user_input_source], coordinates[user_input_destination]]

    response_data = {
        'distance': distance,
        'path': path,
        'time': time_str,
        'fuel_budget': fuel_budget,
        'weather': weather,
        'polyline_coords': polyline_coords
    }

    if current_user.is_authenticated:
        response_data['is_authenticated'] = True
        response_data['username'] = current_user.username
    else:
        response_data['is_authenticated'] = False

    return jsonify(response_data)

@app.route('/locations', methods=['GET'])
def get_locations():
    return jsonify(list(location_map.keys()))

if __name__ == '__main__':
    app.run(debug=True) 