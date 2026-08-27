#!/usr/bin/env python3
"""Met à jour le catalogue embarqué marques / modèles (assets/data/brands_models.json).

Sources :
- API publique NHTSA vPIC (https://vpic.nhtsa.dot.gov) : modèles par marque,
  téléchargés en direct — aucune clé requise ;
- complément « marché algérien » : modèles emblématiques absents du référentiel
  américain (Livan, Dacia, Jetour, Haval, Clio/Symbol/Logan, Picanto…).

L'application charge ce fichier en LOCAL : elle reste 100 % hors ligne.
Relancer ce script nécessite Internet (une seule fois, pour rafraîchir) :

    python scripts/update_vehicle_catalog.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "data" / "brands_models.json"

API = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}?format=json"

# Marques proposées (nom affiché -> nom NHTSA). None = absent de NHTSA,
# la liste du complément suffit.
BRANDS: dict[str, str | None] = {
    "Acura": "ACURA", "Audi": "AUDI", "BAIC": "BAIC MOTOR", "BMW": "BMW",
    "BYD": "BYD", "Cadillac": "CADILLAC", "Changan": "CHANGAN", "Chery": "CHERY",
    "Chevrolet": "CHEVROLET", "Citroën": "CITROEN", "Dacia": None, "DFSK": "DFSK",
    "Dodge": "DODGE", "Fiat": "FIAT", "Ford": "FORD", "Geely": "GEELY",
    "Great Wall (GWM)": "GREAT WALL", "Haval": None, "Honda": "HONDA",
    "Hyundai": "HYUNDAI", "Infiniti": "INFINITI", "Isuzu": "ISUZU", "Iveco": "IVECO",
    "JAC": "JAC", "Jaecoo": None, "Jeep": "JEEP", "Jetour": None, "Kia": "KIA",
    "Lada": None, "Land Rover": "LAND ROVER", "Leapmotor": "LEAPMOTOR",
    "Lexus": "LEXUS", "Livan": None, "Mahindra": "MAHINDRA", "Mazda": "MAZDA",
    "Mercedes-Benz": "MERCEDES-BENZ", "MG": "MG", "Mini": "MINI",
    "Mitsubishi": "MITSUBISHI", "Nissan": "NISSAN", "Omoda": None, "Opel": "OPEL",
    "Peugeot": "PEUGEOT", "Porsche": "PORSCHE", "Proton": "PROTON",
    "Renault": "RENAULT", "Seat": "SEAT", "Skoda": "SKODA", "Smart": "SMART",
    "Ssangyong": "SSANGYONG", "Subaru": "SUBARU", "Suzuki": "SUZUKI", "Tata": "TATA",
    "Tesla": "TESLA", "Toyota": "TOYOTA", "Volkswagen": "VOLKSWAGEN",
    "Volvo": "VOLVO", "Wuling": "WULING",
}

# Complément marché algérien / international : modèles connus absents de NHTSA
# ou manquants dans ses listes. Fusionné sans doublon avec les données NHTSA.
SUPPLEMENT: dict[str, list[str]] = {
    "Renault": ["Clio", "Clio Classic", "Symbol", "Megane", "Captur", "Kadjar",
                "Koleos", "Arkana", "Austral", "Espace", "Talisman", "Twingo",
                "Zoe", "Kangoo", "Trafic", "Master", "Express", "Alaskan"],
    "Dacia": ["Logan", "Sandero", "Sandero Stepway", "Duster", "Jogger", "Spring",
              "Bigster", "Dokker", "Lodgy"],
    "Peugeot": ["106", "206", "207", "208", "301", "306", "307", "308", "2008",
                "3008", "406", "407", "408", "5008", "508", "Partner", "Rifter",
                "Expert", "Boxer", "Traveller"],
    "Kia": ["Picanto", "Morning", "Rio", "Stonic", "Sonet", "Seltos", "Sportage",
            "Sorento", "Niro", "Ceed", "Xceed", "Stinger", "Bongo", "K2500"],
    "Hyundai": ["i10", "Grand i10", "Atos", "i20", "Accent", "Elantra", "Creta",
                "Tucson", "Santa Fe", "IX35", "Staria", "H1", "Porter"],
    "Citroën": ["C1", "C2", "C3", "C3 Aircross", "C4", "C4 Cactus", "C5",
                "C5 Aircross", "C-Elysée", "Berlingo", "Jumpy", "Jumper"],
    "Volkswagen": ["Polo", "Golf", "Passat", "Vento", "Jetta", "Tiguan", "T-Roc",
                   "T-Cross", "Taigo", "Touareg", "Arteon", "Caddy",
                   "Transporter", "Amarok", "Crafter", "Up"],
    "Seat": ["Ibiza", "Leon", "Arona", "Ateca", "Tarraco", "Alhambra", "Toledo",
             "Cordoba", "Altea"],
    "Skoda": ["Fabia", "Octavia", "Superb", "Scala", "Kamiq", "Karoq", "Kodiaq",
              "Rapid", "Yeti"],
    "Opel": ["Corsa", "Astra", "Insignia", "Grandland", "Crossland", "Mokka",
             "Zafira", "Combo", "Vivaro", "Movano"],
    "Fiat": ["Panda", "Punto", "500", "500X", "Tipo", "Linea", "Doblò", "Fiorino",
             "Qubo", "Ducato", "Fastback", "Grande Panda"],
    "Toyota": ["Aygo", "Yaris", "Corolla", "Auris", "Avensis", "Camry", "C-HR",
               "RAV4", "Hilux", "Land Cruiser", "Land Cruiser Prado", "Fortuner",
               "Hiace", "Proace"],
    "Nissan": ["Micra", "March", "Sunny", "Almera", "Sentra", "Juke", "Qashqai",
               "X-Trail", "Kicks", "Terrano", "Navara", "Pathfinder", "Patrol",
               "Urvan", "NV200", "Interstar", "Master"],
    "Suzuki": ["Alto", "Celerio", "Swift", "Baleno", "Dzire", "Ignis", "Vitara",
               "S-Cross", "Jimny", "Ertiga", "APV", "Super Carry"],
    "Mazda": ["Mazda 2", "Mazda 3", "Mazda 6", "CX-3", "CX-30", "CX-5", "CX-60",
              "CX-9", "MX-5", "BT-50"],
    "Honda": ["Jazz", "City", "Civic", "Accord", "HR-V", "CR-V", "Pilot"],
    "Chevrolet": ["Spark", "Aveo", "Optra", "Cruze", "Malibu", "Camaro",
                  "Captiva", "Trax", "Equinox", "Trailblazer", "Tahoe",
                  "Silverado", "Colorado", "N300", "N400"],
    "Ford": ["Fiesta", "Focus", "Mondeo", "Puma", "EcoSport", "Kuga", "Edge",
             "Explorer", "Ranger", "F-150", "Transit", "Tourneo"],
    "Mercedes-Benz": ["Classe A", "Classe B", "Classe C", "Classe E", "Classe S",
                      "CLA", "GLA", "GLB", "GLC", "GLE", "GLS", "EQB", "Vito",
                      "Sprinter", "X-Class"],
    "BMW": ["Série 1", "Série 2", "Série 3", "Série 4", "Série 5", "Série 7",
            "X1", "X2", "X3", "X4", "X5", "X6", "X7", "Z4", "i3", "i4", "iX"],
    "Audi": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q5", "Q7",
             "Q8", "e-tron", "TT", "RS3", "RS6", "S3", "S5"],
    "Geely": ["Emgrand", "Coolray", "Azkarra", "Tugella", "Okavango", "GX3 Pro",
              "Starray", "Panda Mini", "Geometry C"],
    "Livan": ["X3 Pro", "X6 Pro", "S6 Pro", "S1 Pro", "X2 Pro", "Maputo S6 Pro"],
    "Chery": ["QQ", "Arrizo 5", "Arrizo 6", "Tiggo 2 Pro", "Tiggo 3",
              "Tiggo 4 Pro", "Tiggo 7 Pro", "Tiggo 8", "Tiggo 8 Pro", "Tiggo 9"],
    "Changan": ["Alsvin", "Eado", "CS15", "CS35 Plus", "CS55", "CS55 Plus",
                "CS75", "CS95", "UNI-T", "UNI-K"],
    "Haval": ["Jolion", "H2", "H6", "H6 GT", "H9"],
    "Jetour": ["Dashing", "X70", "X70 Plus", "X90 Plus", "X95", "T2"],
    "Jaecoo": ["7", "J7", "J8"],
    "Omoda": ["5", "C5"],
    "MG": ["MG3", "MG5", "MG6", "ZS", "HS", "RX5", "RX8", "MG4", "Cyberster"],
    "JAC": ["JS2", "JS3", "JS4", "JS6", "S2", "S3", "S4", "T6", "T8", "Sunray"],
    "BYD": ["F3", "Dolphin", "Seagull", "Atto 2", "Atto 3", "Seal", "Han",
            "Song Plus", "Tang", "Qin"],
    "DFSK": ["Glory 330", "Glory 500", "Glory 560", "Glory iX5", "C31", "C35",
             "Mini Truck", "Super Cab"],
    "BAIC": ["X25", "X35", "X55", "X75", "Senova D20", "BJ40", "Beijing X7"],
    "Great Wall (GWM)": ["C30", "Voleex", "Wingle 5", "Wingle 7", "Poer", "H1",
                         "H2", "H5", "H9"],
    "Wuling": ["Mini EV", "Bingo", "Starlight", "730", "560", "Confero", "Almaz"],
    "Leapmotor": ["T03", "C10", "C11"],
    "Proton": ["Saga", "Persona", "Gen 2", "S70", "X50", "X70"],
    "Tata": ["Indica", "Indigo", "Xenon", "Tiago", "Altroz", "Punch", "Nexon",
             "Harrier", "Safari"],
    "Mahindra": ["Bolero", "KUV100", "TUV300", "Scorpio", "XUV500", "XUV700",
                 "Thar", "Pick-Up"],
    "Volvo": ["S60", "S90", "V40", "V60", "V90", "XC40", "XC60", "XC90", "C40"],
    "Land Rover": ["Defender", "Discovery", "Discovery Sport", "Freelander",
                   "Range Rover", "Range Rover Evoque", "Range Rover Sport",
                   "Range Rover Velar"],
    "Jeep": ["Renegade", "Compass", "Cherokee", "Grand Cherokee", "Wrangler",
             "Gladiator"],
    "Mini": ["Cooper", "Clubman", "Countryman", "Paceman"],
    "Porsche": ["911", "Boxster", "Cayman", "Cayenne", "Macan", "Panamera",
                "Taycan"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"],
    "Mitsubishi": ["Space Star", "Attrage", "Lancer", "ASX", "Outlander",
                   "Eclipse Cross", "Pajero", "L200", "Xpander", "Montero"],
    "Subaru": ["Impreza", "Legacy", "XV", "Crosstrek", "Forester", "Outback",
               "Ascent", "BRZ"],
    "Isuzu": ["D-Max", "MU-X", "Trooper", "NKR", "NPR"],
    "Lexus": ["CT", "IS", "ES", "GS", "LS", "UX", "NX", "RX", "GX", "LX"],
    "Infiniti": ["Q30", "Q50", "Q60", "QX30", "QX50", "QX60", "QX70", "QX80"],
    "Ssangyong": ["Actyon", "Tivoli", "Korando", "Rexton", "Musso"],
    "Smart": ["Fortwo", "Forfour", "#1", "#3"],
    "Lada": ["2107", "Samara", "Granta", "Largus", "Vesta", "XRAY", "Niva"],
    "Acura": ["ILX", "TLX", "RLX", "RDX", "MDX", "NSX"],
    "Cadillac": ["ATS", "CT4", "CT5", "CT6", "XT4", "XT5", "XT6", "Escalade"],
    "Dodge": ["Caliber", "Nitro", "Journey", "Charger", "Challenger", "Durango",
              "Ram 1500"],
    "Iveco": ["Daily", "Massif", "EuroCargo", "Stralis"],
}

# Motifs clairement inutilisables dans une liste de saisie (« 10 series »…).
JUNK = re.compile(r"^\\d{1,3}(\\s+series)?$", re.IGNORECASE)


def fetch_models(nhtsa_name: str) -> list[str]:
    url = API.format(make=urllib.request.quote(nhtsa_name))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = json.load(response)
    return [str(r["Model_Name"]).strip() for r in data.get("Results", [])]


def clean_name(name: str) -> bool:
    if not name or len(name) < 1 or len(name) > 40:
        return False
    if JUNK.match(name):
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]", name))


def build_catalog() -> dict:
    brands: dict[str, list[str]] = {}

    def add(brand: str, models: list[str]) -> None:
        merged: dict[str, str] = {}
        for model in models:
            if not clean_name(model):
                continue
            key = re.sub(r"\\s+", " ", model).strip().lower()
            merged.setdefault(key, re.sub(r"\\s+", " ", model).strip())
        brands[brand] = sorted(merged.values(), key=str.casefold)

    # 1) Complément local (base garantie, même hors ligne)
    for brand in BRANDS:
        add(brand, SUPPLEMENT.get(brand, []))

    # 2) Enrichissement NHTSA (parallélisé)
    to_fetch = {
        brand: nhtsa for brand, nhtsa in BRANDS.items() if nhtsa
    }
    print(f"Téléchargement NHTSA pour {len(to_fetch)} marques…")

    def task(brand: str, nhtsa: str):
        try:
            return brand, fetch_models(nhtsa)
        except Exception as exc:
            return brand, exc

    done = failed = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(task, b, n) for b, n in to_fetch.items()]
        for future in as_completed(futures):
            brand, result = future.result()
            if isinstance(result, Exception):
                failed += 1
                print(f"  ⚠ {brand} : NHTSA indisponible ({result.__class__.__name__})")
                continue
            done += 1
            before = len(brands[brand])
            add(brand, SUPPLEMENT.get(brand, []) + result)
            print(f"  ✓ {brand}: +{len(brands[brand]) - before} modèle(s) NHTSA")

    print(f"\nTerminé : {done} marques enrichies, {failed} échecs NHTSA.")
    return brands


def main() -> int:
    brands = build_catalog()
    total_models = sum(len(v) for v in brands.values())
    payload = {
        "_meta": {
            "source": "API NHTSA vPIC (vpic.nhtsa.dot.gov) + complément marché algérien",
            "generated": date.today().isoformat(),
            "brands": len(brands),
            "models": total_models,
        },
        "brands": brands,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✔ {len(brands)} marques / {total_models} modèles écrits dans {OUT}")
    for sample in ("Kia", "Livan", "Dacia", "Renault", "Peugeot"):
        models = brands.get(sample, [])
        print(f"   {sample} ({len(models)}) : {models[:6]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
