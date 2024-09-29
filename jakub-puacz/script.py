import copy
import math
import typing as tp
from dataclasses import dataclass

import elevation
import fiona
import folium
import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import rasterio
import requests
from pyproj import Transformer
from shapely.geometry import LineString, Point
from simplekml import Kml
from tqdm import tqdm

ATTRACTIVENESS = "attractiveness"
SCORE = "score"
ELEVATION = "elevation"
HEIGHT = "height"
SPEED_MAP = {
    'PL:rural': 90,
    'PL:urban': 50,
}


def contains(param, name):
    if isinstance(param, list):
        return name in param
    else:
        return param == name


class PathFinder:

    def __init__(
            self,
            start_point: tp.Tuple[float, float],
            end_point: tp.Tuple[float, float],
            graph: tp.Optional[nx.Graph] = None,
        ):
        self.graph: tp.Union[nx.Graph, nx.MultiDiGraph, None] = graph
        self.start_point = start_point
        self.end_point = end_point
        ox.settings.useful_tags_way = ["surface", "incline"]

    def load_graph(self, radius_from_path: int = 50_000):
        """
        `radius_from_path` is given in meters.
        """
        line = LineString([self.start_point, self.end_point])
        buffered_polygon = line.buffer(radius_from_path)
        self.graph = ox.graph_from_polygon(buffered_polygon, network_type="all")

    def load_elevation_map(self):
        # Download and clip SRTM data to a bounding box
        elevation.clip(bounds=(18.8982,	49.0136, 21.8185, 50.6107), output='malopolska_dem.tif',
                       cache_dir="topo_cache")
    

    def load_graph_from_region(self):
        region = 'Małopolskie Voivodeship, Poland'  # Adjust the region as needed
    
        # Download the street network for the region
        self.graph = ox.graph_from_place(region, network_type='all')

    def load_graph_from_radius(self, radius: int):
        self.graph = ox.graph_from_point(self.start_point, dist=radius, network_type='all')

    def save_graph(self):
        ox.save_graphml(self.graph, filepath="graph.graphml")

    def load_from_file(self, filepath: str = "graph.graphml"):
        self.graph = ox.load_graphml(filepath)

    def get_elevation_of(self, data, dem, lon: float, lat: float):
        # dem_crs = dem.crs
        # transformer = Transformer.from_crs("epsg:4326", dem_crs, always_xy=True)
        # x, y = transformer.transform(lon, lat)
        # row, col = ~dem.transform * (x, y)
        # row = int(np.floor(row))
        # col = int(np.floor(col))
        # if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
        #     return data[row, col]
        # else:
        #     return None
        transform = dem.transform  # This is an Affine object
    
        # Apply the inverse of the affine transform to convert from (lon, lat) to (row, col)
        col, row = ~transform * (lon, lat)
        
        # Convert to integers (round or floor)
        row = int(np.floor(row))
        col = int(np.floor(col))
        
        # Now row and col are the pixel indices in the raster
        return data[row, col]
        
    def get_elevations_of(self, data, dem, lon, lat):
        dem_crs = dem.crs
        transformer = Transformer.from_crs("epsg:4326", dem_crs, always_xy=True)
        x, y = transformer.transform(lon, lat)
        print(x)
        rows, cols = ~dem.transform * (x, y)
        rows = (np.floor(row)).astype(int)
        cols = (np.floor(col)).astype(int)
        elevations = []
        for row, col in zip(rows, cols):
            if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
                elevations.append(data[row, col])
            else:
                elevations.append(np.nan)  # Mark as NaN if out of bounds
        
        return elevations
    
    def load_alt_points_from_api(self):
        bbox = (19.087, 49.176, 21.451, 50.547)
        api_key = "974f72494081e30452e08a7f059beea6f605fbc8"
        link = f'https://tessadem.com/api/elevation?key={api_key}&mode=area&rows=128&columns=128&locations={bbox[0]},{bbox[1]}|{bbox[2]},{bbox[3]}&format=geotiff'
        res = requests.get(link)
        return res
    
    def load_alt_for_points(self):
        with rasterio.open("topo_cache/SRTM1/malopolska_dem.tif") as dem:
            # Read the DEM data (first band)
            elevation_data = dem.read(1)
            batch_size = 10_000
            all_nodes = list(self.graph.nodes)
            for i, node in tqdm(enumerate(all_nodes)):
                # if i % batch_size == 0 and i != 0:
                #     indices = all_nodes[i-batch_size:i]
                #     nodes_lat, nodes_lon = [self.graph.nodes[i]['y'] for i in indices], [self.graph.nodes[i]['x'] for i in indices]
                #     self.get_elevations_of(elevation_data, dem, nodes_lon, nodes_lat)
                #     elv *= 0.3048
                #     for i in indices:
                #         self.graph.nodes[i][HEIGHT] = elv
                lat, lon = self.graph.nodes[node]['y'], self.graph.nodes[node]['x']
                elv = self.get_elevation_of(elevation_data, dem, lon, lat)
                elv = (elv * 0.3048) if elv is not None else None
                self.graph.nodes[node][HEIGHT] = elv

    def filter(self):
        for u, v, key, data in tqdm(self.graph.edges(keys=True, data=True)):
            
            # Adding attractiveness
            data[ATTRACTIVENESS] = -data['length']

            # # Weighting/excluding by speed
            if 'maxspeed' in data:
                for speed in data['maxspeed'] if isinstance(data['maxspeed'], list) else [data['maxspeed']]:
                    try:
                        speed_value = int(speed)
                    except:
                        speed_value = SPEED_MAP.get(speed, None)
                        if speed_value is None:
                            speed_value = SPEED_MAP.get(data['maxspeed'], None)
                            if speed_value is None:
                                print(data['maxspeed']) 
                                continue

                    if speed_value in range(0, 30):
                        data[ATTRACTIVENESS] += 100
                    elif speed_value in range(30, 50):
                        data[ATTRACTIVENESS] += 0
                    elif speed_value in range(50, 90):
                        data[ATTRACTIVENESS] -= 200
                    elif speed_value > 90:
                        data[ATTRACTIVENESS] -= 500

            # # Weighting/excluding by type
            if 'highway' in data and contains(data['highway'], 'cycleway'): # 'tertiary']:
                data[ATTRACTIVENESS] += 1500
            # elif contains(data['highway'], 'tertiary'):
            #     data[ATTRACTIVENESS] += 50
            # elif contains(data['highway'], 'secondary'):
            #     data[ATTRACTIVENESS] += 50
            # elif contains(data['highway'], 'primary'):
            #     data[ATTRACTIVENESS] -= 200
            # elif contains(data['highway'], 'pedestrian'):
            #     data[ATTRACTIVENESS] += 80
            # elif contains(data['highway'], 'unclassified'):
            #     data[ATTRACTIVENESS] -= 300
            # else:
            #     data[ATTRACTIVENESS] -= 100

            # Bridges are unatractive
            # if 'bridge' in data and data['bridge'] == 'yes':
            #     data[ATTRACTIVENESS] -= 10_000

            # Weigjhting amount of lanes
            if 'lanes' in data and np.any(np.array(data['lanes']).astype(int) > 1):
                data[ATTRACTIVENESS] -= 100

            # Weighting the elevation of the edge
            try:
                elv_start = self.graph.nodes[u][HEIGHT]
                elv_end = self.graph.nodes[v][HEIGHT]
                if elv_end > 210 or elv_start > 210:
                    data[ATTRACTIVENESS] -= 10_000
                # elv_start *= 0.3048
                # elv_end *= 0.3048
                elevation_value = abs(elv_start - elv_end) # Diff of elevation levels
                angle = math.atan(elevation_value / data['length'])
                data[ELEVATION] = elevation_value
                data[ATTRACTIVENESS] -= elevation_value * 20
                data[ATTRACTIVENESS] -= ((elv_start + 0.5 * elevation_value) * 0.001) ** 10
                data[HEIGHT] = elv_start + 0.5 * elevation_value
                data['angle'] = angle
                # data[ATTRACTIVENESS] = data['length'] + max(elv_start, elv_end)
            except Exception as ex:
                print(ex)
                pass

            # Evaluating score based on attractiveness
            data[SCORE] = -data[ATTRACTIVENESS]
            if data[SCORE] < 1:
                data[SCORE] = 1
            

    def find_path(self):
        # Get nearest nodes to points A and B
        a_node = ox.distance.nearest_nodes(self.graph, self.start_point[1], self.start_point[0])
        b_node = ox.distance.nearest_nodes(self.graph, self.end_point[1], self.end_point[0])

        print("Finding shortest...")
        # Find the shortest path using custom weights
        shortest_path = nx.shortest_path(self.graph, a_node, b_node, weight=SCORE)
        print("Found!")

        # Plot the graph and the shortest path
        # ox.plot_graph_route(self.graph, shortest_path)

        # Output path distance in meters
        distance = nx.shortest_path_length(self.graph, a_node, b_node, weight=SCORE)
        print(f"Shortest path distance: {distance} meters")

        self.path = shortest_path

    def show_path(self):
        # Create a map centered on point A
        m = folium.Map(location=self.start_point, zoom_start=12)

        # Plot the shortest path based on edge geometries
        for u, v, key in zip(self.path[:-1], self.path[1:], range(len(self.path)-1)):
            # Retrieve edge data and check if it has a geometry (for curved roads)
            edge_data = self.graph.get_edge_data(u, v)
            print(edge_data)
            
            if 'geometry' in edge_data:
                # If edge has geometry (linestring), extract and plot the full geometry
                coords = list(edge_data['geometry'].coords)
            else:
                # If no geometry, plot a straight line between nodes
                coords = [(self.graph.nodes[u]['y'], self.graph.nodes[u]['x']),
                        (self.graph.nodes[v]['y'], self.graph.nodes[v]['x'])]
            
            # Add the segment to the map
            color = "red" if edge_data[0].get(ELEVATION) is None else "blue"
            height = "unknown"
            if edge_data[0].get(HEIGHT) is not None:
                height = edge_data[0][HEIGHT]
            folium.PolyLine(coords, color=color, weight=5, opacity=0.7,
                            popup=folium.Popup(html=f"<h2>{height}<h2/><br/><h2>{edge_data[0].get('highway')}<h2/>")).add_to(m)

        # Add markers for start (point A) and end (point B)
        folium.Marker(location=self.start_point, popup="Start: Point A", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(location=self.end_point, popup="End: Point B", icon=folium.Icon(color="red")).add_to(m)

        # Display the map
        return m