import json
import os

import openai
import requests
import streamlit as st
import streamlit.components.v1 as components

# Ensure you have the OpenAI package installed:
# You can install it using: pip install openai


# Set page configuration
st.set_page_config(page_title="Google Maps Route Planner with OpenAI Integration", layout="wide")


st.markdown(
    """
    <style>
        .reportview-container {
            margin-top: -2em;
        }
        #MainMenu {visibility: hidden;}
        .stDeployButton {display:none;}
        .stAppDeployButton {display: none;}
        footer {visibility: hidden;}
        #stDecoration {display:none;}
    </style>
""",
    unsafe_allow_html=True,
)

# Add a title to the app
st.title("Małopolska by Bike")

# Load OpenAI API key from Streamlit secrets
# Make sure to add your OpenAI API key in the Streamlit secrets (Settings > Secrets)
# openai_api_key = st.secrets["openai_api_key"]
openai.api_key = os.getenv("OPENAI_API_KEY")


def call_get_coordinates(params):
    url = "http://localhost:8000/"

    # Set the headers
    headers = {"accept": "application/json"}

    # Make the GET request
    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "from_str": params["start_city"],
                "to_str": params["end_city"],
                "bbox_name": params["bounding_box"],
                "type": params["type"],
            },
        )

        # Check if the request was successful
        if response.status_code == 200:
            # Print the JSON response
            return response.json()["coords"]
        else:
            print(f"Error: Received status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")


# Function to get coordinates from OpenAI based on user input
def get_coordinates(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    You are a helpful assistant that returns parameters in JSON format:
                    
                    start_city: The starting city of the route defined by the user.
                    end_city: The ending city of the route defined by the user.
                    bounding_box: 'KRAKOW' if the route is around Krakow, POLAND or 'NOWY_SACZ' if the route is around Nowy Sacz, POLAND.
                    type: 'FAST' if user mentioned fast/quick in the message or 'DEFAULT' otherwise.                                        
                    """,
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        # Extract the assistant's reply
        reply = response.choices[0].message["content"].strip()
        reply = reply.replace("```json", "")
        reply = reply.replace("```", "")

        # st.write(f"Assistant's reply: {reply}")
        params = json.loads(reply)
        # st.write(f"Params: {params}")
        # Parse the JSON
        # coords = json.loads(reply)
        coords_json = call_get_coordinates(params)
        # print(coords_json)
        # json_cords = "array_data.json"
        # coords_json = json.load(open(json_cords))

        return coords_json
    except Exception as e:
        st.error(f"Error processing input: {e}")
        return None


# User input
user_input = st.text_input("Gdzie chcesz dojechać?", "")

# Initialize coordinates
coords_json = []


def generate_google_maps_url(coords):
    if len(coords) >= 2:
        # Origin and destination
        origin = f"{coords[0][0]},{coords[0][1]}"
        destination = f"{coords[-1][0]},{coords[-1][1]}"

        # Waypoints
        waypoints = "|".join([f"{coord[0]},{coord[1]}" for coord in coords[1:-1]])

        # Create the URL
        if waypoints:
            google_maps_url = f"https://www.google.com/maps/dir/{origin}/{waypoints}/{destination}"
        else:
            google_maps_url = f"https://www.google.com/maps/dir/{origin}/{destination}"

        return google_maps_url
    return None


if user_input:
    with st.spinner("Obliczamy trasę..."):
        coords_json = get_coordinates(user_input)

    if coords_json:
        # Optionally, you can limit the number of coordinates to optimize performance
        mod = max(int(len(coords_json) / 25), 1)
        coords_json = coords_json[:1] + coords_json[mod::mod][:23] + coords_json[-1:]
        # coords_json = [[x, y] for (y, x) in coords_json]  # Ensure [lat, lng] format

        google_maps_url = generate_google_maps_url(coords_json)

        if google_maps_url:
            st.markdown(f"[Przejdź do google maps]({google_maps_url})", unsafe_allow_html=True)

        # Convert coordinates to JSON string for embedding in JavaScript
        coords_json_str = json.dumps(coords_json)

        # Embed Google Maps using HTML and JavaScript
        map_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Google Maps Route Planner</title>
            <script src="https://maps.googleapis.com/maps/api/js?key=API_KEY"></script>
            <script>
                function initMap() {{
                    var map = new google.maps.Map(document.getElementById('map'), {{
                        zoom: 4,
                        center: new google.maps.LatLng({coords_json[0][0]}, {coords_json[0][1]})
                    }});
        
                    var directionsService = new google.maps.DirectionsService();
                    var directionsRenderer = new google.maps.DirectionsRenderer({{
                        map: map,
                        suppressMarkers: true 
                    }});
        
                    var coords = {coords_json_str};
                    
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
                            travelMode: 'WALKING' // You can change this to 'DRIVING', 'BICYCLING', etc.
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

        # # Display the coordinates used
        # st.write("Coordinates used for routing:")
        # for i, coord in enumerate(coords_json, 1):
        #     st.write(f"Point {i}: Latitude {coord[0]}, Longitude {coord[1]}")
else:
    st.info("Twoja trasa...")
