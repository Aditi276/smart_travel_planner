let map = null;
let mapInitialized = false;

const popularLocations = [
    'Forest Research Institute',
    'Paltan Bazaar',
    'ISBT Dehradun',
    'Clock Tower',
    'Rajpur Road',
    'Pacific Mall',
    'Dehradun Railway Station',
    'Robber\'s Cave',
    'Sahastradhara',
    'Mussoorie Road',
    'Doon University',
    'Graphic Era University',
    'Max Hospital',
    'Parade Ground',
    'Gandhi Park',
    'Tapkeshwar Temple'
];

function initializeMap() {
    if (!mapInitialized) {
        map = L.map('map').setView([30.3165, 78.0322], 13); 
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        mapInitialized = true;
    } else {
        setTimeout(() => map.invalidateSize(), 200);
    }
}

document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
    
        button.classList.add('active');
        document.getElementById(`${button.dataset.tab}-form`).classList.add('active');
    });
});

async function login() {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('token', data.token);
            showApp();
        } else {
            alert(data.error);
        }
    } catch (error) {
        alert('An error occurred during login');
    }
}

async function register() {
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('Registration successful! Please login.');
            document.querySelector('[data-tab="login"]').click();
        } else {
            alert(data.error);
        }
    } catch (error) {
        alert('An error occurred during registration');
    }
}

function logout() {
    localStorage.removeItem('token');
    showAuth();
}

function showAuth() {
    document.getElementById('auth-section').classList.remove('hidden');
    document.getElementById('app-section').classList.add('hidden');
}

function showApp() {
    document.getElementById('auth-section').classList.add('hidden');
    document.getElementById('app-section').classList.remove('hidden');
    initializeMap();
}

function showSpinner() {
    document.getElementById('loading-spinner').classList.add('active');
}
function hideSpinner() {
    document.getElementById('loading-spinner').classList.remove('active');
    document.getElementById('loading-spinner').classList.add('hidden');
}

async function findRoute() {
    const source = document.getElementById('source').value;
    const destination = document.getElementById('destination').value;
    if (!source || !destination) {
        alert("Please select both source and destination.");
        return;
    }
    if (source === destination) {
        alert("Source and destination cannot be the same.");
        return;
    }

    showSpinner();

    try {
        // Fetch route and info from backend
        const response = await fetch('/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source, destination })
        });
        const data = await response.json();

        document.getElementById('route-info').classList.remove('hidden');
        if (data.error) {
            document.getElementById('distance').textContent = data.error;
            document.getElementById('time').textContent = "-";
            document.getElementById('fuel-budget').textContent = "-";
            document.getElementById('weather-info').innerHTML = '';
            hideSpinner();
            return;
        }
        document.getElementById('distance').textContent = data.distance + " km";
        document.getElementById('time').textContent = data.time;
        document.getElementById('fuel-budget').textContent = data.fuel_budget + " ₹";
        await fetchAndDisplayWeather(data.weather);

        // Draw the route polyline using backend polyline_coords (real road path if available)
        if (data.polyline_coords && data.polyline_coords.length > 1) {
            const latlngs = data.polyline_coords;
            map.eachLayer((layer) => {
                if (layer instanceof L.Marker || layer instanceof L.Polyline) {
                    map.removeLayer(layer);
                }
            });
            if (latlngs.length > 0) {
                L.marker(latlngs[0]).addTo(map);
                L.marker(latlngs[latlngs.length - 1]).addTo(map);
            }
            L.polyline(latlngs, { color: '#1e3c72' }).addTo(map);
            map.fitBounds(L.latLngBounds(latlngs));
            hideSpinner();
        } else {
            hideSpinner();
        }
    } catch (error) {
        console.error("Error finding route:", error);
        document.getElementById('distance').textContent = "Error finding route.";
        document.getElementById('time').textContent = "-";
        document.getElementById('fuel-budget').textContent = "-";
        document.getElementById('weather-info').innerHTML = '';
        hideSpinner();
    }
}

async function fetchAndDisplayWeather(weatherData) {
    try {
        let weatherHtml = '<div class="weather-container">';
        // Source weather
        weatherHtml += `<div class="weather-box">
            <h4>Source Weather</h4>
            <div class="weather-details">`;
        if (weatherData && weatherData.source) {
            const sourceWeather = weatherData.source;
            weatherHtml += `
                <p>Temperature: ${sourceWeather.temperature}°C</p>
                <p>Feels like: ${sourceWeather.feels_like}°C</p>
                <p>Humidity: ${sourceWeather.humidity}%</p>
                <p>Description: ${sourceWeather.description}</p>
                <p>Wind Speed: ${sourceWeather.wind_speed} m/s</p>
            `;
        } else {
            weatherHtml += `<p>Weather data not available.</p>`;
        }
        weatherHtml += `</div></div>`;
        // Destination weather
        weatherHtml += `<div class="weather-box">
            <h4>Destination Weather</h4>
            <div class="weather-details">`;
        if (weatherData && weatherData.destination) {
            const destWeather = weatherData.destination;
            weatherHtml += `
                <p>Temperature: ${destWeather.temperature}°C</p>
                <p>Feels like: ${destWeather.feels_like}°C</p>
                <p>Humidity: ${destWeather.humidity}%</p>
                <p>Description: ${destWeather.description}</p>
                <p>Wind Speed: ${destWeather.wind_speed} m/s</p>
            `;
        } else {
            weatherHtml += `<p>Weather data not available.</p>`;
        }
        weatherHtml += `</div></div>`;
        weatherHtml += '</div>';
        document.getElementById('weather-info').innerHTML = weatherHtml;
    } catch (err) {
        console.error('Error displaying weather:', err);
        document.getElementById('weather-info').innerHTML = '<p class="error">Could not display weather information.</p>';
    }
}

function displayRoute(routeData) {
    map.eachLayer((layer) => {
        if (layer instanceof L.Marker || layer instanceof L.Polyline) {
            map.removeLayer(layer);
        }
    });

    const sourceMarker = L.marker(routeData.source.coordinates).addTo(map);
    const destMarker = L.marker(routeData.destination.coordinates).addTo(map);

    L.polyline([
        routeData.source.coordinates,
        routeData.destination.coordinates
    ], { color: '#1e3c72' }).addTo(map);
   
    map.fitBounds(L.latLngBounds([
        routeData.source.coordinates,
        routeData.destination.coordinates
    ]));
   
    document.getElementById('distance').textContent = routeData.distance;
    document.getElementById('time').textContent = routeData.estimated_time;
    document.getElementById('route-info').classList.remove('hidden');
}

function displayRoutePath(latlngs, distance, timeText) {
    map.eachLayer((layer) => {
        if (layer instanceof L.Marker || layer instanceof L.Polyline) {
            map.removeLayer(layer);
        }
    });

    if (latlngs.length > 0) {
        L.marker(latlngs[0]).addTo(map);
        L.marker(latlngs[latlngs.length - 1]).addTo(map);
    }

    L.polyline(latlngs, { color: '#1e3c72' }).addTo(map);

    map.fitBounds(L.latLngBounds(latlngs));

    document.getElementById('distance').textContent = distance;
    document.getElementById('time').textContent = timeText;
    document.getElementById('route-info').classList.remove('hidden');
}
function populateDropdowns() {
    const sourceSelect = document.getElementById('source');
    const destSelect = document.getElementById('destination');
    sourceSelect.length = 1;
    destSelect.length = 1;
    popularLocations.forEach(loc => {
        const opt1 = document.createElement('option');
        opt1.value = loc;
        opt1.textContent = loc;
        sourceSelect.appendChild(opt1);
        const opt2 = document.createElement('option');
        opt2.value = loc;
        opt2.textContent = loc;
        destSelect.appendChild(opt2);
    });
}

window.addEventListener('load', () => {
    populateDropdowns();
    const token = localStorage.getItem('token');
    if (token) {
        showApp();
    } else {
        showAuth();
    }
});

const graph = {
    'Forest Research Institute': { 'Paltan Bazaar': 6, 'ISBT Dehradun': 8 },
    'Paltan Bazaar': { 'Forest Research Institute': 6, 'ISBT Dehradun': 5, 'Clock Tower': 2 },
    'ISBT Dehradun': { 'Forest Research Institute': 8, 'Paltan Bazaar': 5, 'Clock Tower': 7 },
    'Clock Tower': { 'Paltan Bazaar': 2, 'ISBT Dehradun': 7, 'Rajpur Road': 4 },
    'Rajpur Road': { 'Clock Tower': 4, 'Pacific Mall': 3 },
    'Pacific Mall': { 'Rajpur Road': 3, 'Dehradun Railway Station': 6 },
    'Dehradun Railway Station': { 'Pacific Mall': 6, 'Robber\'s Cave': 7 },
    'Robber\'s Cave': { 'Dehradun Railway Station': 7, 'Sahastradhara': 5 },
    'Sahastradhara': { 'Robber\'s Cave': 5, 'Mussoorie Road': 8 },
    'Mussoorie Road': { 'Sahastradhara': 8, 'Doon University': 6 },
    'Doon University': { 'Mussoorie Road': 6, 'Graphic Era University': 7 },
    'Graphic Era University': { 'Doon University': 7, 'Max Hospital': 4 },
    'Max Hospital': { 'Graphic Era University': 4, 'Parade Ground': 3 },
    'Parade Ground': { 'Max Hospital': 3, 'Gandhi Park': 2 },
    'Gandhi Park': { 'Parade Ground': 2, 'Tapkeshwar Temple': 5 },
    'Tapkeshwar Temple': { 'Gandhi Park': 5 },
};

const coordinates = {
    'Forest Research Institute': [30.3547, 77.9470],
    'Paltan Bazaar': [30.3252, 78.0430],
    'ISBT Dehradun': [30.2901, 78.0535],
    'Clock Tower': [30.3256, 78.0437],
    'Rajpur Road': [30.3700, 78.0800],
    'Pacific Mall': [30.3915, 78.0782],
    'Dehradun Railway Station': [30.3155, 78.0322],
    'Robber\'s Cave': [30.3792, 78.0595],
    'Sahastradhara': [30.3956, 78.1317],
    'Mussoorie Road': [30.4022, 78.0747],
    'Doon University': [30.3544, 77.9368],
    'Graphic Era University': [30.2722, 78.0796],
    'Max Hospital': [30.3250, 78.0419],
    'Parade Ground': [30.3258, 78.0445],
    'Gandhi Park': [30.3257, 78.0447],
    'Tapkeshwar Temple': [30.3342, 78.0081],
};

function dijkstra(graph, start, end) {
    const distances = {};
    const previous = {};
    const nodes = Object.keys(graph);
    nodes.forEach(node => {
        distances[node] = Infinity;
        previous[node] = null;
    });
    distances[start] = 0;
    let unvisited = [...nodes];
    while (unvisited.length > 0) {
        unvisited.sort((a, b) => distances[a] - distances[b]);
        const closest = unvisited.shift();
        if (closest === end) break;
        if (distances[closest] === Infinity) break;
        for (let neighbor in graph[closest]) {
            let alt = distances[closest] + graph[closest][neighbor];
            if (alt < distances[neighbor]) {
                distances[neighbor] = alt;
                previous[neighbor] = closest;
            }
        }
    }
    let path = [];
    let curr = end;
    while (curr) {
        path.unshift(curr);
        curr = previous[curr];
    }
    if (path[0] !== start) path = []; 
    return { distance: distances[end], path };
}

async function getRealRoute(startCoords, endCoords) {
    const apiKey = '5b3ce3597851110001cf62480a414c147a414e068ac670e64b9c1e55'; 
    const url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${apiKey}&start=${startCoords[1]},${startCoords[0]}&end=${endCoords[1]},${endCoords[0]}`;
    const response = await fetch(url);
    if (!response.ok) {
        alert('Failed to fetch route from OpenRouteService.');
        return null;
    }
    const data = await response.json();
    return data.features[0].geometry.coordinates.map(coord => [coord[1], coord[0]]);
} 