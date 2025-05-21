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

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_planner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Example graph: adjacency list (node: [(neighbor, distance), ...])
graph = {
    "A": [("B", 2), ("C", 5)],
    "B": [("A", 2), ("C", 1), ("D", 4)],
    "C": [("A", 5), ("B", 1), ("D", 1)],
    "D": [("B", 4), ("C", 1)]
}

location_map = {
    "Indian Institute": "A",
    "Clock Tower": "B",
    "ISBT": "C",
    "Railway Station": "D"
}

def dijkstra(graph, start, end):
    queue = [(0, start, [])]
    seen = set()
    while queue:
        (cost, node, path) = heapq.heappop(queue)
        if node in seen:
            continue
        path = path + [node]
        if node == end:
            return (cost, path)
        seen.add(node)
        for (neighbor, weight) in graph.get(node, []):
            if neighbor not in seen:
                heapq.heappush(queue, (cost + weight, neighbor, path))
    return (float("inf"), [])

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

@app.route('/route', methods=['POST'])
def route():
    data = request.json
    user_input_source = data.get('source')
    user_input_destination = data.get('destination')
    print(f"Received source: {user_input_source}, destination: {user_input_destination}")

    # Map user input to graph nodes
    src_node = location_map.get(user_input_source)
    dest_node = location_map.get(user_input_destination)

    if not src_node or not dest_node:
        return jsonify({'error': 'Invalid location selected. Please choose from: ' + ', '.join(location_map.keys())}), 400

    if src_node not in graph or dest_node not in graph:
        return jsonify({'error': 'Source or destination not found in the graph.'}), 400

    distance, path = dijkstra(graph, src_node, dest_node)
    if distance == float("inf"):
        return jsonify({'error': 'No route found'}), 404
    # Assume average speed 40 km/h for time estimate
    time = round(distance / 40, 2)
    return jsonify({'distance': distance, 'path': path, 'time': time})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 

    from flask import render_template

