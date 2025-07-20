import re
import json
import os
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

URLS2 = [
    "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-AD-2.LFBD-fr-FR.html",
    "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-ENR-2.1-fr-FR.html",
    "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-ENR-2.2-fr-FR.html",
]

URLS = ["https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/FR-ENR-5.1-fr-FR.html"]

# --- Classes de données ---
class Subspace:
    def __init__(self, ident, coord, classification, limit):
        self.ident = ident.strip()
        self.coord = coord.strip()
        self.classification = classification.strip()
        self.limit = limit.strip()

    def to_dict(self):
        return {
            "ident": self.ident,
            "coord": self.coord,
            "class": self.classification,
            "limit": self.limit
        }

class Airspace:
    def __init__(self, ident):
        self.ident = ident.strip()
        self.subzones = []

    def add_subzone(self, sub):
        self.subzones.append(sub)      
       
    def get_ident(self):
        return self.ident

    def to_dict(self):
        return {
            "ident": self.ident,
            "layers": [s.to_dict() for s in self.subzones]
        }
        
    def __repr__(self):
        return str(self.to_dict())

# --- Fonctions utilitaires ---
def is_coord_format(s):
    return bool(re.search(r"\d{2}°\d{2}'\d{2}\"[NSEW]", s))

def parse_rows(rows, is_siv):

    airspaces = []
    current_airspace = None
    current_subspace = None
    start_with_coord_pattern = re.compile(r"(\d+°\d+'(?:\d+)?\"?[NS])") 
    
    last_ident = "UNKNOWN"
    last_coord = "UNKNOWN"
    
    for row in rows:
   
        cols = row.find_all(["td", "th"])
        
        ident_coord_split = cols[0].get_text("\n", strip=True).split("\n")
        
        ident_coord = "UNKNOWN"
        clazz = "UNKNOWN"
        limit = "UNKNOWN"
        
        if is_siv:
            try:            
                ident_coord = cols[0].get_text(" ", strip=True)
                clazz = "G"
                limit = cols[1].get_text(" ", strip=True)
            except:
                pass        
        else:
            try:            
                ident_coord = cols[0].get_text(" ", strip=True)
                clazz = cols[1].get_text(" ", strip=True)
                limit = cols[2].get_text(" ", strip=True)
            except:
                pass
        
        #print(f"{ident_coord} {clazz} {limit}")
        
        # case 1, some cells are empty, its a new airspace definition
        if len(cols) < 3 or limit == "":
            # we add previous airspace to airspace list
            if current_airspace is not None:                
                airspaces.append(current_airspace)
                
            current_airspace = Airspace(ident_coord)
            last_ident = ident_coord    
            continue
            
        # case 2, first cell is empty, another subzone for same zone
        elif ident_coord_split[0] == "":
            current_subspace = Subspace(last_ident, last_coord, clazz, limit)
            current_airspace.add_subzone(current_subspace)
    
            
        # case 3, first cell is only coord              
        elif start_with_coord_pattern.match(ident_coord_split[0]) or ident_coord_split[0].startswith("cercle"):
            current_subspace = Subspace(last_ident, ident_coord, clazz, limit)
            current_airspace.add_subzone(current_subspace)
          
            last_coord = ident_coord
    
       
        # case 4, first cell is mix between identifier and coords (TMA)
        elif current_airspace.get_ident() in ident_coord:
            match = start_with_coord_pattern.search(ident_coord)
            
            coord = "UNKNOWN"
            ident = "UNKNOWN"
            if match:
                ident = ident_coord[:match.start()]
                coord = ident_coord[match.start():]
            
            current_subspace = Subspace(ident, coord, clazz, limit)
            current_airspace.add_subzone(current_subspace)
            
            last_ident = ident
            last_coord = coord
            
        else:
            #print(f"Problem parsing row with {ident_coord} {clazz} {limit}")
            print("Problem:\n[{}]\n[{}]".format(last_ident, last_coord))
    
    airspaces.append(current_airspace)
    return airspaces


# --- Traitement HTML ---
def parse_html_file(soup):  

    result = []

    # search every tables
    tables = soup.find_all("table")

    
    for tbl in tables:
        rows = tbl.find_all("tr")
        if rows:

            hdrcols = rows[0].find_all(["td", "th"])
            if hdrcols:
                
                firstcol = hdrcols[0].get_text(" ", strip=True)                

                # if TR contains corresponding header, we start processing
                if "identification" in firstcol.lower() and "limites latérales" in firstcol.lower():
                    secondcol = hdrcols[1].get_text(" ", strip=True)
                    
                    # SIV table does not contain class
                    is_siv = "limites verticales" in secondcol.lower()
                    
                    rows.pop(0)
                    airspaces = parse_rows(rows, is_siv)
                    
                    for a in airspaces:
                        result.append(a.to_dict())

    return result

# === Point d’entrée ===
def main_local():
    # --- Recherche de tous les fichiers HTML dans sample_data ---
    input_dir = "../sample_data"
    input_files2 = [
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.endswith(".html") or f.endswith(".htm")
    ]
    input_files = ["../sample_data/FR-ENR-5.1-fr-FR.html"]

    # --- Traitement et génération JSON ---
    final_data = defaultdict(list)

    for filepath in input_files:
        key = os.path.basename(filepath)
        
        with open(filepath, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            airspaces = parse_html_file(soup)

        if airspaces:
            final_data[key] = airspaces

    # --- Sauvegarde ---
    with open("../extracts/airspaces_loc.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    print("Fichier airspaces.json généré avec tous les fichiers de sample_data.")

# === Point d’entrée ===
def main_remote():
    final_data = defaultdict(list)
    
    # --- Telechargements des pages web eAIP ---
    for url in URLS:
        key = url.rstrip('/').split('/')[-1]
    
        print(f"Analyse de {url}")
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Erreur HTTP {resp.status_code} pour {url}")
            continue
            
        soup = BeautifulSoup(resp.content, 'html.parser')
        airspaces = parse_html_file(soup)

        if airspaces:
            final_data[key] = airspaces

    # --- Sauvegarde ---
    with open("../extracts/airspaces2.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
        
    print("Fichier airspaces.json généré avec tous les fichiers de sample_data.")

# === Lancement ===
if __name__ == "__main__":
    main_local()
