import json

# import contextily a
import streamlit as st
import streamlit.components.v1 as components

# Set page configuration
st.set_page_config(page_title="Google Maps Route Planner", layout="wide")

# Add a title to the app
st.title("Google Maps Route Planner")


json_cords = "array_data.json"
coords_json = json.load(open(json_cords))
mod = int(len(coords_json) / 25)
coords_json = coords_json[:1] + coords_json[mod::mod][:23] + coords_json[-1:]
coords_json = [[x, y] for (y, x) in coords_json]

# Embed Google Maps using HTML and JavaScript
map_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Google Maps Route Planner</title>
    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyDT9A7ox8MD-6kYir9_LEHVrWZ6kLDxEKI"></script>
    <script>
        function initMap() {{
            var map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 4,                
            }});

            var directionsService = new google.maps.DirectionsService();
            var directionsRenderer = new google.maps.DirectionsRenderer({{
                map: map,
                suppressMarkers: true 
            }});

            var coords = {coords_json};
            
            console.log(coords)
            if (coords.length >= 2) {{
                var origin = new google.maps.LatLng(coords[0][0], coords[0][1]);
                var destination = new google.maps.LatLng(coords[coords.length - 1][0], coords[coords.length - 1][1]);
                var waypointsForRequest = coords.slice(1, -1).map(coord => ({{
                    location: new google.maps.LatLng(coord[0], coord[1]),
                    stopover: true
                }}));

                var request = {{
                    origin: origin,
                    destination: destination,
                    waypoints: waypointsForRequest,
                    // travelMode: 'BICYCLING'
                    travelMode: 'WALKING'
                }};                              

                directionsService.route(request, function(result, status) {{
                    if (status === 'OK') {{
                        directionsRenderer.setDirections(result);
                        var totalDistance = result.routes[0].legs.reduce((total, leg) => total + leg.distance.value, 0) / 1000;
                        var totalDuration = result.routes[0].legs.reduce((total, leg) => total + leg.duration.value, 0) / 60;
                        document.getElementById('distance').innerText = 'Total Distance: ' + totalDistance.toFixed(2) + ' km';
                        document.getElementById('duration').innerText = 'Total Duration: ' + totalDuration.toFixed(0) + ' minutes';
                    }} else {{
                        document.getElementById('error-message').innerText = 'Directions request failed due to ' + status;
                    }}
                }});
            }} else {{
                document.getElementById('error-message').innerText = 'Please provide at least two coordinate pairs.';
            }}
        }}
    </script>
</head>
<body onload="initMap()">
    <div id="map" style="height: 500px; width: 100%;"></div>
    <div id="distance"></div>
    <div id="duration"></div>
    <div id="error-message" style="color: red;"></div>
</body>
</html>
"""

# Use the HTML component to display the map
components.html(map_html, height=700)

# Display the coordinates used
st.write("Coordinates used for routing:")
# for i, coord in enumerate(coords, 1):
#     st.write(f"Point {i}: Latitude {coord[0]}, Longitude {coord[1]}")
