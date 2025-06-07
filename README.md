# Smart Travel Planner

A web application that helps users plan their travel routes using OpenStreetMap and Dijkstra's algorithm for route optimization. The application includes user authentication and a modern, responsive interface.

## Features

- User authentication (login/register)
- Interactive map using OpenStreetMap
- Route planning between two locations
- Distance and time estimation
- Modern and responsive UI

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd smart-travel-planner
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

## Usage

1. Register a new account or login with existing credentials
2. Enter your source and destination locations
3. Click "Find Route" to see the optimized route
4. View the distance and estimated travel time
5. The route will be displayed on the interactive map

## Technologies Used

- Backend:
  - Python
  - Flask
  - SQLAlchemy
  - Flask-Login
  - Geopy

- Frontend:
  - HTML5
  - CSS3
  - JavaScript
  - Leaflet.js (for maps)

## Contributing

Feel free to submit issues and enhancement requests! 