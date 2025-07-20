import re
import simplekml
import zipfile
import json
from geographiclib.geodesic import Geodesic

# === Pré-compilation des expressions régulières ===
re_dms = re.compile(r"(\d+)°(\d+)'(\d+)(?:\"|')?([NSEW])")
re_arc = re.compile(r"arc (anti-)?horaire de (\d+(?:\.\d+)?)\s*(NM|km|m) de rayon centré sur (.+?)\s*,\s*([0-9°'\"]+[NEWS])(?:\s*\(.*\))?\s*$")
re_circle = re.compile(r"cercle de (\d+(?:\.\d+)?)\s*(NM|km|m) de rayon centré sur (.+?)\s*,\s*([0-9°'\"]+[NEWS])(?:\s*\(.*\))?\s*$")
re_fl = re.compile(r"FL\s*(\d+)")
re_ft = re.compile(r"(\d+)\s*ft\s*")

# === Conversion DMS => décimal ===
def dms_to_decimal(dms_str):
    match = re_dms.match(dms_str.strip())
    if not match:
        raise ValueError(f"Invalid DMS format: {dms_str}")
    deg, minute, sec, hemi = match.groups()
    decimal = int(deg) + int(minute) / 60 + int(sec) / 3600
    if hemi in ['S', 'W']:
        decimal = -decimal
    return decimal

def parse_coord_pair(pair_str):
    try:
        lat_str, lon_str = [s.strip() for s in pair_str.split(',')]
        lat = dms_to_decimal(lat_str)
        lon = dms_to_decimal(lon_str)
        return (lat, lon)
    except Exception as e:
        raise ValueError(f"Invalid coordinate pair: {pair_str} ({e})")


# === Arc de cercle ===
def generate_arc_points(start_str, center_str, end_str, radius_nm, max_circle_points=20, clockwise=True):
    radius_m = radius_nm * 1852
    start_lat, start_lon = parse_coord_pair(start_str)
    center_lat, center_lon = parse_coord_pair(center_str)
    end_lat, end_lon = parse_coord_pair(end_str)
    g = Geodesic.WGS84
    azi_start = g.Inverse(center_lat, center_lon, start_lat, start_lon)["azi1"] % 360
    azi_end = g.Inverse(center_lat, center_lon, end_lat, end_lon)["azi1"] % 360

    if clockwise:
        sweep = (azi_end - azi_start) % 360
        if sweep == 0:
            sweep = 360
        azi_step = sweep / max(1, round(max_circle_points * sweep / 360))
    else:
        sweep = (azi_start - azi_end) % 360
        if sweep == 0:
            sweep = 360
        azi_step = -sweep / max(1, round(max_circle_points * sweep / 360))

    num_points = max(2, round(max_circle_points * sweep / 360))

    arc_points = []
    for i in range(num_points + 1):
        azi = (azi_start + i * azi_step) % 360
        pos = g.Direct(center_lat, center_lon, azi, radius_m)
        arc_points.append((pos["lat2"], pos["lon2"]))

    return arc_points

# === Cercle complet ===
def generate_circle(center_str, radius_nm, total_points=20):
    radius_m = radius_nm * 1852
    center_lat, center_lon = parse_coord_pair(center_str)
    g = Geodesic.WGS84
    circle = []
    for i in range(total_points):
        azi = (360 * i) / total_points
        pos = g.Direct(center_lat, center_lon, azi, radius_m)
        circle.append((pos["lat2"], pos["lon2"]))
    circle.append(circle[0])
    return circle


# === Extraction portion de frontière ===
def extract_border_points(border, start, end):
    def dist(a, b):
        return (a[0]-b[0])**2 + (a[1]-b[1])**2
        
    n = len(border)
    i0 = min(range(n), key=lambda i: dist(border[i], start))
    i1 = min(range(n), key=lambda i: dist(border[i], end))
    
    dist_cw = (i1 - i0) % n
    dist_ccw = (i0 - i1) % n
    if dist_cw <= dist_ccw:
        indices = [(i0 + k) % n for k in range(dist_cw + 1)]
    else:
        indices = [(i0 - k) % n for k in range(dist_ccw + 1)]
    return [border[i] for i in indices]

def convert_dist_to_nm(dist, unit):
    result = None
    if unit == "NM":
        result = dist
    elif unit == "km":
        result = dist / 1.852
    elif unit == "m":
        result = dist / 1852
    else:
        raise ValueError(f"Unknown unit : {unit}")
    return result
                
# === Parsing des coordonnées avec arcs, cercles et frontière ===
def parse_polygon_coords(coord_string, france_border, sea_border):
    segments = re.split(r"\s-\s", coord_string)
    coords = []
    i = 0
    while i < len(segments):
        segment = segments[i]
        arc_match = re_arc.match(segment)
        circle_match = re_circle.match(segment)
        if arc_match and i > 0 and i < len(segments) - 1:
            is_clockwise = arc_match.group(1) is None
            raw_radius = float(arc_match.group(2))
            unit = arc_match.group(3)
            radius = convert_dist_to_nm(raw_radius, unit)
            center_lat = arc_match.group(4)
            center_lon = arc_match.group(5)
            prev_point = segments[i - 1]
            next_point = segments[i + 1]
            arc_pts = generate_arc_points(prev_point, f"{center_lat},{center_lon}", next_point, radius, clockwise=is_clockwise)
            coords.extend(arc_pts)
            i += 2
        elif circle_match:
            raw_radius = float(circle_match.group(1))
            unit = circle_match.group(2)           
            radius = convert_dist_to_nm(raw_radius, unit)
            center_lat = circle_match.group(3)
            center_lon = circle_match.group(4)
            coords.extend(generate_circle(f"{center_lat},{center_lon}", radius))
            i += 1
        elif ("frontière" in segment.lower() or "la côte atlantique" in segment.lower()) and i > 0 and i < len(segments) - 1:
            start = parse_coord_pair(segments[i - 1])
            end = parse_coord_pair(segments[i + 1])
            coords.extend(extract_border_points(france_border, start, end))
            i += 2
        elif "eaux territoriales" in segment.lower() and i > 0 and i < len(segments) - 1:
            start = parse_coord_pair(segments[i - 1])
            end = parse_coord_pair(segments[i + 1])
            coords.extend(extract_border_points(sea_border, start, end))
            i += 2
        else:
            try:
                coords.append(parse_coord_pair(segment))
            except Exception:
                print(f"Probleme avec {segment}")
                pass
            i += 1
    return coords


def parse_vertical_limits(limits_str):
    limits = limits_str.split('------------');

    upper = limits[0].strip()
    lower = limits[1].strip()
   
    upper_stat = False 
    lower_stat = False

    if upper == "UNL":
        upper = 100000
        upper_stat = True 

    if lower == "SFC":
        lower = 0
        lower_stat = True 

    if not upper_stat:
        match = re_fl.match(upper)
        if match:
            upper = int(match.group(1)) * 100 * 0.3048
            upper_stat = True 

    if not lower_stat:
        match = re_fl.match(lower)
        if match:
            lower = int(match.group(1)) * 100 * 0.3048
            lower_stat = True 

    if not upper_stat:
        match = re_ft.match(upper)
        if match:
            upper = int(match.group(1)) * 0.3048
            upper_stat = True 

    if not lower_stat:
        match = re_ft.match(lower)
        if match:
            lower = int(match.group(1)) * 0.3048
            lower_stat = True     

    if lower_stat and upper_stat:
        return (lower, upper)

    raise ValueError(f"Invalid vertical limits format: {limits_str}")


def class_color(airspace_class):
    colors = {
        "C": simplekml.Color.red,
        "D": simplekml.Color.green,
        "E": simplekml.Color.blue,
        "G": simplekml.Color.gray,
    }
    return colors.get(airspace_class.upper(), simplekml.Color.white)


def add_zone_to_kml(kml_folder, polygon_coords, lower_alt, upper_alt, name, airspace_class):   
    style = simplekml.Style()
    style.polystyle.color = simplekml.Color.changealphaint(100, class_color(airspace_class))

    # Contour haut (plafond)
    pol_top = kml_folder.newpolygon(name=f"{name} upper")
    pol_top.outerboundaryis = [(lon, lat, upper_alt) for lat, lon in polygon_coords]
    pol_top.altitudemode = simplekml.AltitudeMode.absolute
    pol_top.style = style
    
    # Contour bas (plancher), ici avec transparence
    pol_bottom = kml_folder.newpolygon(name=f"{name} lower")
    pol_bottom.outerboundaryis = [(lon, lat, lower_alt) for lat, lon in polygon_coords]
    pol_bottom.altitudemode = simplekml.AltitudeMode.absolute
    pol_bottom.style = style

    # Faces verticales pour fermer le volume
    wall_folder = kml_folder.newfolder(name="wall")
    
    # Bugfix to prevent Shapely to throw A LinearRing must have at least 3 coordinate tuples error 
    epsilon = 1e-4
    
    nb_pts = len(polygon_coords)    
    for i in range(nb_pts):
        next_i = (i + 1) % nb_pts
        ls = wall_folder.newpolygon(name=f"{name} side {i}")
        
        upper_left = (polygon_coords[i][1]+epsilon, polygon_coords[i][0]+epsilon, upper_alt)
        upper_right = (polygon_coords[next_i][1], polygon_coords[next_i][0], upper_alt)
        lower_right = (polygon_coords[next_i][1]+epsilon, polygon_coords[next_i][0]+epsilon, lower_alt)
        lower_left = (polygon_coords[i][1], polygon_coords[i][0], lower_alt)
        
        ls.outerboundaryis = [
            lower_left,
            lower_right,
            upper_right,
            upper_left,
        ]
        ls.altitudemode = simplekml.AltitudeMode.absolute
        ls.extrude = 0
        ls.style = style

# === Chargement GeoJSON contour France ===   
def load_france_boundary(path_geojson):
    with open(path_geojson, 'r', encoding='utf-8') as f:
        gj = json.load(f)

    border_points = []

    if gj['type'] != 'GeometryCollection':
        raise ValueError("GeoJSON must be a GeometryCollection")

    for geom in gj['geometries']:
        if geom['type'] == 'MultiPolygon':
            for polygon in geom['coordinates']:
                for ring in polygon:
                    border_points.extend((lat, lon) for lon, lat in ring)
        elif geom['type'] == 'Polygon':
            for ring in geom['coordinates']:
                border_points.extend((lat, lon) for lon, lat in ring)

    return border_points   

# === Chargement contour frontière ===
france_border = load_france_boundary("../data/metropole-version-simplifiee.geojson")
territorial_waters = load_france_boundary("../data/EspMar_FR_MT_WGS84.geojson")

# === Traitement du JSON en un seul KML global ===
kml = simplekml.Kml()

with open("../extracts/airspaces_loc.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for page in data.values():
    for airspace in page:
        ident = airspace["ident"]
        
        folder = kml.newfolder(name=ident)
        for layer in airspace["layers"]:
            try:
                subfolder = folder.newfolder(name=layer["ident"])
                coords = parse_polygon_coords(layer["coord"], france_border, territorial_waters)
                lo_alt, hi_alt = parse_vertical_limits(layer["limit"])                
        
                add_zone_to_kml(subfolder, coords, lo_alt, hi_alt, name=layer["ident"], airspace_class=layer["class"])
            except Exception as e:
                print(f"Erreur sur {layer['ident']}: {e}")

kml_path = "../extracts/airspaces_global3.kml"
kmz_path = "../extracts/airspaces_global3.kmz"

kml.save(kml_path)

with zipfile.ZipFile(kmz_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
    kmz.write(kml_path, arcname="doc.kml")  # nom attendu dans un KMZ
