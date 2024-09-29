import osmnx as ox
from fastapi import FastAPI
from script import PathFinder

Cracow = None
Nowy_Sacz = None

app = FastAPI()


def load_boading_boxes():
    box_now = ox.graph_from_bbox(49.7369, 49.1593, 20.8452, 19.7905, simplify=True)
    box_cra = ox.graph_from_bbox(50.2638, 49.8233, 20.3285, 19.0772, simplify=True)
    ox.save_graphml(box_now, filepath="nowy-sacz.graphml")
    ox.save_graphml(box_cra, filepath="cracow.graphml")
    Nowy_Sacz = box_now
    Cracow = box_cra

load_boading_boxes()

@app.get("/")
def read_root(from_str: str, to_str: str, bbox_name: str):
    start_point = ox.geocode(from_str)
    end_point = ox.geocode(to_str)
    pf = PathFinder(start_point, end_point, NOWY_SACZ if bbox_name == 'NOWY_SACZ' else CRACOW)
    pf.load_alt_for_points()
    pf.filter()
    pf.find_path()

    coords = []
    for u, v, key in zip(pf.path[:-1], pf.path[1:], range(len(pf.path)-1)):
        # Retrieve edge data and check if it has a geometry (for curved roads)
        coords.append((pf.graph.nodes[u]['y'], pf.graph.nodes[u]['x']))

    return {"coords": coords}