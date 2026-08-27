"""Catalogue embarqué de marques / modèles (téléchargé une fois, chargé en local).

Le fichier ``assets/data/brands_models.json`` est généré par
``scripts/update_vehicle_catalog.py`` (API NHTSA vPIC + complément marché
algérien). L'application le lit **sans aucune connexion Internet** et le
fusionne avec les marques / modèles créés par l'utilisateur en base.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from utils.paths import asset_path


@lru_cache(maxsize=1)
def _load() -> dict[str, list[str]]:
    """Charge le catalogue embarqué ({} si le fichier est absent ou corrompu)."""
    path = asset_path("data", "brands_models.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        brands = payload.get("brands", {})
        if isinstance(brands, dict) and brands:
            return brands
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def meta() -> dict:
    """Métadonnées du catalogue (source, date de génération…)."""
    path = asset_path("data", "brands_models.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return dict(payload.get("_meta", {}))
    except (OSError, ValueError):
        return {}


def builtin_brands() -> list[str]:
    """Marques du catalogue embarqué, triées (insensible à la casse)."""
    return sorted(_load().keys(), key=str.casefold)


def builtin_models(brand: str) -> list[str]:
    """Modèles embarqués d'une marque (recherche insensible à la casse)."""
    needle = (brand or "").strip().casefold()
    if not needle:
        return []
    for name, models in _load().items():
        if name.casefold() == needle:
            return list(models)
    return []


def merge_names(*lists: list[str]) -> list[str]:
    """Fusionne plusieurs listes de noms : dédoublonnage insensible à la
    casse (première occurrence conservée) puis tri alphabétique."""
    merged: dict[str, str] = {}
    for items in lists:
        for item in items or []:
            name = re.sub(r"\s+", " ", str(item)).strip()
            if name:
                merged.setdefault(name.casefold(), name)
    return sorted(merged.values(), key=str.casefold)


def brands_for_combo(db_brands: list[str]) -> list[str]:
    """Liste complète pour la combo Marque : catalogue embarqué + base."""
    return merge_names(db_brands, builtin_brands())


def models_for_combo(brand: str, db_models: list[str]) -> list[str]:
    """Liste complète pour la combo Modèle : embarqué + base pour cette marque."""
    return merge_names(db_models, builtin_models(brand))
