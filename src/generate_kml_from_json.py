import re
import simplekml
import zipfile
import json

def dms_to_decimal(dms_str):
    match = re.match(r"(\d+)°(\d+)'(\d+)(?:\"|')?([NSEW])", dms_str.strip())
    if not match:
        raise ValueError(f"Invalid DMS format: {dms_str}")
    deg, minute, sec, hemi = match.groups()
    decimal = int(deg) + int(minute) / 60 + int(sec) / 3600
    if hemi in ['S', 'W']:
        decimal = -decimal
    return decimal


def parse_coordinate_pair(pair_str):
    try:
        lat_str, lon_str = [s.strip() for s in pair_str.split(',')]
        lat = dms_to_decimal(lat_str)
        lon = dms_to_decimal(lon_str)
        return (lat, lon)
    except Exception as e:
        raise ValueError(f"Invalid coordinate pair: {pair_str} ({e})")


def parse_polygon_coords(coord_string):
    coord_pattern = re.compile(r"(\d+°\d+'(?:\d+)?\"?[NS])\s*,\s*(\d+°\d+'(?:\d+)?\"?[EW])")
    matches = coord_pattern.findall(coord_string)
    coords = []
    for lat_str, lon_str in matches:
        try:
            coords.append(parse_coordinate_pair(f"{lat_str} , {lon_str}"))
        except ValueError:
            continue
    return coords


def parse_vertical_limits(limits_str):
    limits = limits_str.split('------------');

    upper = limits[0].strip()
    lower = limits[1].strip()

    print(f"[{lower}] [{upper}]")
    
    upper_stat = False 
    lower_stat = False

    if upper == "UNL":
        upper = 100000
        upper_stat = True 

    if lower == "SFC":
        lower = 0
        lower_stat = True 

    if not upper_stat:
        match = re.match(r"FL\s*(\d+)", upper)
        if match:
            upper = int(match.group(1)) * 100 * 0.3048
            upper_stat = True 

    if not lower_stat:
        match = re.match(r"FL\s*(\d+)", lower)
        if match:
            lower = int(match.group(1)) * 100 * 0.3048
            lower_stat = True 

    if not upper_stat:
        match = re.match(r"(\d+)\s*ft\s*", upper)
        if match:
            upper = int(match.group(1)) * 0.3048
            upper_stat = True 

    if not lower_stat:
        match = re.match(r"(\d+)\s*ft\s*", lower)
        if match:
            lower = int(match.group(1)) * 0.3048
            lower_stat = True     

    print(f"{lower} {lower_stat} {upper} {upper_stat}")

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
    color = simplekml.Color.changealphaint(100, class_color(airspace_class))

    # Contour haut (plafond)
    pol_top = kml_folder.newpolygon(name=f"{name} upper")
    pol_top.outerboundaryis = [(lon, lat, upper_alt) for lat, lon in polygon_coords]
    pol_top.altitudemode = simplekml.AltitudeMode.absolute
    pol_top.style.polystyle.color = color
    
    # Contour bas (plancher), ici avec transparence
    pol_bottom = kml_folder.newpolygon(name=f"{name} lower")
    pol_bottom.outerboundaryis = [(lon, lat, lower_alt) for lat, lon in polygon_coords]
    pol_bottom.altitudemode = simplekml.AltitudeMode.absolute
    pol_bottom.style.polystyle.color = color

    # Faces verticales pour fermer le volume
    wall_folder = kml_folder.newfolder(name="wall")
    
    for i in range(len(polygon_coords)):
        next_i = (i + 1) % len(polygon_coords)
        ls = wall_folder.newpolygon(name=f"{name} side {i}")
        ls.outerboundaryis = [
            (polygon_coords[i][1], polygon_coords[i][0], lower_alt),
            (polygon_coords[next_i][1], polygon_coords[next_i][0], lower_alt),
            (polygon_coords[next_i][1], polygon_coords[next_i][0], upper_alt),
            (polygon_coords[i][1], polygon_coords[i][0], upper_alt),
            (polygon_coords[i][1], polygon_coords[i][0], lower_alt),
        ]
        ls.altitudemode = simplekml.AltitudeMode.absolute
        ls.extrude = 0
        ls.style.polystyle.color = color


# === Traitement du JSON en un seul KML global ===
kml = simplekml.Kml()

with open("../extracts/airspaces.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for page in data.values():
    for airspace in page:
        ident = airspace["ident"]
        folder = kml.newfolder(name=ident)
        for layer in airspace["layers"]:
            try:
                subfolder = folder.newfolder(name=layer["ident"])
                coords = parse_polygon_coords(layer["coord"])
                lo_alt, hi_alt = parse_vertical_limits(layer["limit"])
                
                add_zone_to_kml(subfolder, coords, lo_alt, hi_alt, name=layer["ident"], airspace_class=layer["class"])
            except Exception as e:
                print(f"Erreur sur {layer['ident']}: {e}")


kml_path = "../extracts/airspaces_global.kml"
kmz_path = "../extracts/airspaces_global.kmz"

kml.save(kml_path)

with zipfile.ZipFile(kmz_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
    kmz.write(kml_path, arcname="doc.kml")  # nom attendu dans un KMZ