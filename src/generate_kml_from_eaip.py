!pip install simplekml

import re
import simplekml
import requests
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

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
        match = re.match(r"(\d+)\s*ft\s*AMSL", upper)
        if match:
            upper = int(match.group(1)) * 0.3048
            upper_stat = True 

    if not lower_stat:
        match = re.match(r"(\d+)\s*ft\s*AMSL", lower)
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


def generate_kml(polygon_coords, lower_alt, upper_alt, name="CTR", airspace_class="D"):
    kml = simplekml.Kml()
    
    # Contour haut (plafond)
    pol_top = kml.newpolygon(name=f"{name} upper")
    pol_top.outerboundaryis = [(lon, lat, upper_alt) for lat, lon in polygon_coords]
    pol_top.altitudemode = simplekml.AltitudeMode.absolute
    pol_top.style.polystyle.color = simplekml.Color.changealphaint(100, class_color(airspace_class))
    
    # Contour bas (plancher), ici avec transparence
    pol_bottom = kml.newpolygon(name=f"{name} lower")
    pol_bottom.outerboundaryis = [(lon, lat, lower_alt) for lat, lon in polygon_coords]
    pol_bottom.altitudemode = simplekml.AltitudeMode.absolute
    pol_bottom.style.polystyle.color = simplekml.Color.changealphaint(100, class_color(airspace_class))
    
    # Faces verticales pour fermer le volume
    for i in range(len(polygon_coords)):
        next_i = (i + 1) % len(polygon_coords)
        #ls = kml.newlinestring(name=f"{name} side {i}")
        ls = kml.newpolygon(name=f"{name} side {i}")
        # ls.coords
        ls.outerboundaryis = [
            (polygon_coords[i][1], polygon_coords[i][0], lower_alt),
            (polygon_coords[next_i][1], polygon_coords[next_i][0], lower_alt),
            (polygon_coords[next_i][1], polygon_coords[next_i][0], upper_alt),
            (polygon_coords[i][1], polygon_coords[i][0], upper_alt),
            (polygon_coords[i][1], polygon_coords[i][0], lower_alt),
        ]
        ls.altitudemode = simplekml.AltitudeMode.absolute
        ls.extrude = 0
        #ls.style.linestyle.width = 2
        #ls.style.linestyle.color = simplekml.Color.changealphaint(100, class_color(airspace_class))
        ls.style.polystyle.color = simplekml.Color.changealphaint(100, class_color(airspace_class))
    
    kml.save(f"{name}.kml")


# === Extraction automatique depuis eAIP ===
def extract_zone_info(url, zone_name):
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    tables = soup.find_all("table")
    
    for tbl in tables:
         for tr in tbl.find_all("tr"):
             txt = tr.get_text(" ", strip=True)
             
             if zone_name == txt:   
                 nexttr = tr.find_next_sibling('tr')
    
                 cells = nexttr.find_all("td")
                 raw = [cell.get_text(" ", strip=True) for cell in cells]

                 return {
                     "name": zone_name,
                     "coords": raw[0],
                     "class": raw[1],
                     "vertical": raw[2],
                 }
    return None

def extract_zone_info_tma(url, zone_name):
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    tables = soup.find_all("table")
    
    for tbl in tables:
         for tr in tbl.find_all("tr"):
             txt = tr.get_text(" ", strip=True)
             
             if  txt.startswith(zone_name):
    
                 cells = tr.find_all("td")
                 raw = [cell.get_text(" ", strip=True) for cell in cells]

                 return {
                     "name": zone_name,
                     "coords": raw[0].replace(zone_name, ""),
                     "class": raw[1],
                     "vertical": raw[2],
                 }
    return None

url = "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-ENR-2.1-fr-FR.html"
#url = "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-ENR-2.2-fr-FR.html"
#url = "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-AD-2.LFBD-fr-FR.html"
# Exemple : CTA Aquitaine partie 2
#zone = extract_zone_info(url, "CTA AQUITAINE partie W")
#zone = extract_zone_info(url, "CTA AQUITAINE partie SE")
zone = extract_zone_info_tma(url, "TMA AQUITAINE partie 10")
#zone = extract_zone_info(url, "CTR BORDEAUX MERIGNAC")
#zone = extract_zone_info(url, "SIV AQUITAINE partie 2")

if zone:
    polygon = parse_polygon_coords(zone['coords'])
    lo_alt, hi_alt = parse_vertical_limits(zone['vertical'])
    generate_kml(polygon, lo_alt, hi_alt, name=zone['name'].replace(" ", "_").replace("(", "_").replace(")", "_"), airspace_class=zone['class'])
else:
    print("Error")
