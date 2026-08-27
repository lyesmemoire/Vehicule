"""Gestion de la base SQLite locale.

La base est créée automatiquement au premier démarrage dans un dossier
utilisateur (jamais dans « Program Files ») :

- Windows : ``%APPDATA%\\VehicleCostCalculator\\vehicle_costs.db``
- macOS   : ``~/Library/Application Support/VehicleCostCalculator/``
- Linux   : ``~/.local/share/VehicleCostCalculator/``

Le chemin peut être surchargé via la variable d'environnement
``VEHICLE_COST_DATA_DIR`` (pratique pour les tests ou un mode portable).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from services.calculator import DEFAULT_SETTINGS

APP_DIR_NAME = "VehicleCostCalculator"
DB_FILENAME = "vehicle_costs.db"


class DatabaseError(Exception):
    """Erreur applicative liée à la base de données locale."""


def get_data_dir() -> Path:
    """Dossier de données de l'utilisateur courant."""
    override = os.environ.get("VEHICLE_COST_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return base / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME


def get_db_path() -> Path:
    return get_data_dir() / DB_FILENAME


def connect() -> sqlite3.Connection:
    """Ouvre une connexion SQLite (crée le dossier de données si besoin)."""
    try:
        get_data_dir().mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as exc:
        raise DatabaseError(
            f"Impossible d'ouvrir la base de données ({get_db_path()}) : {exc}"
        ) from exc
    except OSError as exc:
        raise DatabaseError(f"Dossier de données inaccessible : {exc}") from exc


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brands (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS models (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    UNIQUE (brand_id, name)
);

CREATE TABLE IF NOT EXISTS simulations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT    NOT NULL,  -- ISO : AAAA-MM-JJ
    marque            TEXT    NOT NULL,
    modele            TEXT    NOT NULL,
    annee             INTEGER NOT NULL,
    cylindree         REAL    NOT NULL,
    prix_usd          REAL    NOT NULL,
    fret_usd          REAL    NOT NULL,
    taux_change       REAL    NOT NULL,
    prix_dzd          REAL    NOT NULL,
    fret_dzd          REAL    NOT NULL,
    valeur_douaniere  REAL    NOT NULL,
    taux_douane       REAL    NOT NULL,  -- en pourcentage : 15 = 15 %
    droits_douane     REAL    NOT NULL,
    tva               REAL    NOT NULL,
    frais_transitaire REAL    NOT NULL,
    frais_portuaires  REAL    NOT NULL,
    taxe_vehicule     REAL    NOT NULL DEFAULT 0,
    cout_total        REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_simulations_vehicle
    ON simulations (marque, modele, annee);

CREATE INDEX IF NOT EXISTS idx_simulations_date
    ON simulations (date);
"""

# Migrations légères : ajout de colonnes sur des bases créées par une version
# précédente (ALTER exécuté seulement si la colonne est absente).
MIGRATIONS = [
    ("simulations", "base_tva",
     "ALTER TABLE simulations ADD COLUMN base_tva REAL NOT NULL DEFAULT 0"),
    ("simulations", "taxe_vehicule",
     "ALTER TABLE simulations ADD COLUMN taxe_vehicule REAL NOT NULL DEFAULT 0"),
]

# Catalogue de démonstration (inséré uniquement si la table est vide).
SAMPLE_BRANDS = ["Livan", "Kia", "Geely", "Chery", "Changan", "Hyundai"]
SAMPLE_MODELS = {
    "Livan": ["X3 Pro", "S6 Pro"],
    "Kia": ["Picanto", "Morning"],
}


def init_database() -> None:
    """Crée le schéma, applique les migrations et insère les valeurs par défaut."""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # Migrations : ajout des colonnes manquantes sur une base existante
        for table, column, statement in MIGRATIONS:
            columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if column not in columns:
                conn.execute(statement)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        if conn.execute("SELECT COUNT(*) AS n FROM brands").fetchone()["n"] == 0:
            for brand in SAMPLE_BRANDS:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,)
                )
                for model in SAMPLE_MODELS.get(brand, []):
                    conn.execute(
                        "INSERT OR IGNORE INTO models (brand_id, name) VALUES (?, ?)",
                        (cursor.lastrowid, model),
                    )
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Erreur lors de l'initialisation de la base : {exc}") from exc
    finally:
        conn.close()
