"""Dépôts (repositories) : seule couche qui parle au SQLite.

Chaque méthode ouvre une connexion courte, ce qui évite tout problème
de thread et simplifie la gestion des erreurs. Les erreurs SQLite sont
converties en :class:`database.db.DatabaseError` avec un message français.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from database.db import DatabaseError, connect
from models.simulation import Simulation
from services.calculator import DEFAULT_SETTINGS


def _dec(value: object) -> Decimal:
    """Convertit une valeur SQL (REAL) en Decimal sans surprise d'affichage."""
    return Decimal(str(value))


def _row_to_simulation(row) -> Simulation:
    year, month, day = str(row["date"]).split("-")
    return Simulation(
        id=row["id"],
        date=date(int(year), int(month), int(day)),
        marque=row["marque"],
        modele=row["modele"],
        annee=row["annee"],
        cylindree=_dec(row["cylindree"]),
        prix_usd=_dec(row["prix_usd"]),
        fret_usd=_dec(row["fret_usd"]),
        taux_change=_dec(row["taux_change"]),
        taux_fret=_dec(row["taux_fret"]),
        devise=row["devise"],
        prix_dzd=_dec(row["prix_dzd"]),
        fret_dzd=_dec(row["fret_dzd"]),
        valeur_douaniere=_dec(row["valeur_douaniere"]),
        taux_douane=_dec(row["taux_douane"]),
        droits_douane=_dec(row["droits_douane"]),
        tva=_dec(row["tva"]),
        frais_transitaire=_dec(row["frais_transitaire"]),
        frais_portuaires=_dec(row["frais_portuaires"]),
        taxe_vehicule=_dec(row["taxe_vehicule"]),
        cout_total=_dec(row["cout_total"]),
    )


class SettingsRepository:
    """Paramètres de calcul (clé/valeur) stockés en SQLite."""

    def get_all(self) -> dict[str, str]:
        """Tous les paramètres, complétés par les valeurs par défaut."""
        try:
            conn = connect()
            try:
                rows = conn.execute("SELECT key, value FROM settings").fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Impossible de lire les paramètres : {exc}") from exc
        values = dict(DEFAULT_SETTINGS)
        values.update({row["key"]: row["value"] for row in rows})
        return values

    def save(self, values: dict[str, str]) -> None:
        try:
            conn = connect()
            try:
                for key, value in values.items():
                    conn.execute(
                        "INSERT INTO settings (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, str(value)),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            raise DatabaseError(f"Impossible d'enregistrer les paramètres : {exc}") from exc

    def reset_defaults(self) -> None:
        try:
            conn = connect()
            try:
                conn.execute("DELETE FROM settings")
                for key, value in DEFAULT_SETTINGS.items():
                    conn.execute(
                        "INSERT INTO settings (key, value) VALUES (?, ?)", (key, value)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            raise DatabaseError(f"Impossible de réinitialiser les paramètres : {exc}") from exc


class CatalogRepository:
    """Marques et modèles (combos auto-complétées)."""

    def list_brands(self) -> list[str]:
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT name FROM brands ORDER BY name COLLATE NOCASE"
                ).fetchall()
            finally:
                conn.close()
            return [row["name"] for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire les marques : {exc}") from exc

    def list_models(self, brand: str) -> list[str]:
        if not brand:
            return []
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT m.name FROM models m "
                    "JOIN brands b ON b.id = m.brand_id "
                    "WHERE b.name = ? COLLATE NOCASE "
                    "ORDER BY m.name COLLATE NOCASE",
                    (brand,),
                ).fetchall()
            finally:
                conn.close()
            return [row["name"] for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire les modèles : {exc}") from exc

    def add_brand(self, brand: str) -> None:
        if not brand.strip():
            return
        try:
            conn = connect()
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand.strip(),)
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            raise DatabaseError(f"Impossible d'enregistrer la marque : {exc}") from exc

    def add_model(self, brand: str, model: str) -> None:
        brand, model = brand.strip(), model.strip()
        if not brand or not model:
            return
        try:
            conn = connect()
            try:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,)
                )
                if cursor.lastrowid == 0:
                    row = conn.execute(
                        "SELECT id FROM brands WHERE name = ? COLLATE NOCASE", (brand,)
                    ).fetchone()
                    brand_id = row["id"]
                else:
                    brand_id = cursor.lastrowid
                conn.execute(
                    "INSERT OR IGNORE INTO models (brand_id, name) VALUES (?, ?)",
                    (brand_id, model),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            raise DatabaseError(f"Impossible d'enregistrer le modèle : {exc}") from exc


class SimulationRepository:
    """Historique des simulations."""

    _COLUMNS = (
        "date, marque, modele, annee, cylindree, prix_usd, fret_usd, taux_change, "
        "taux_fret, devise, prix_dzd, fret_dzd, valeur_douaniere, taux_douane, "
        "droits_douane, tva, frais_transitaire, frais_portuaires, taxe_vehicule, "
        "cout_total"
    )

    def save(self, sim: Simulation) -> int:
        """Insère ou met à jour une simulation, renvoie son identifiant."""
        values = (
            sim.date.isoformat(),
            sim.marque.strip(),
            sim.modele.strip(),
            sim.annee,
            float(sim.cylindree),
            float(sim.prix_usd),
            float(sim.fret_usd),
            float(sim.taux_change),
            float(sim.taux_fret),
            sim.devise,
            float(sim.prix_dzd),
            float(sim.fret_dzd),
            float(sim.valeur_douaniere),
            float(sim.taux_douane),
            float(sim.droits_douane),
            float(sim.tva),
            float(sim.frais_transitaire),
            float(sim.frais_portuaires),
            float(sim.taxe_vehicule),
            float(sim.cout_total),
        )
        try:
            conn = connect()
            try:
                if sim.id is None:
                    cursor = conn.execute(
                        f"INSERT INTO simulations ({self._COLUMNS}) "
                        f"VALUES ({', '.join('?' * 20)})",
                        values,
                    )
                    sim_id = cursor.lastrowid
                else:
                    conn.execute(
                        f"UPDATE simulations SET {', '.join(f'{c} = ?' for c in self._COLUMNS.split(', '))} "
                        "WHERE id = ?",
                        (*values, sim.id),
                    )
                    sim_id = sim.id
                conn.commit()
            finally:
                conn.close()
            return sim_id
        except Exception as exc:
            raise DatabaseError(f"Impossible d'enregistrer la simulation : {exc}") from exc

    def get(self, sim_id: int) -> Simulation | None:
        try:
            conn = connect()
            try:
                row = conn.execute(
                    "SELECT * FROM simulations WHERE id = ?", (sim_id,)
                ).fetchone()
            finally:
                conn.close()
            return _row_to_simulation(row) if row else None
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire la simulation : {exc}") from exc

    def delete(self, sim_id: int) -> None:
        try:
            conn = connect()
            try:
                conn.execute("DELETE FROM simulations WHERE id = ?", (sim_id,))
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            raise DatabaseError(f"Impossible de supprimer la simulation : {exc}") from exc

    def list_all(self) -> list[Simulation]:
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM simulations ORDER BY date DESC, id DESC"
                ).fetchall()
            finally:
                conn.close()
            return [_row_to_simulation(row) for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire l'historique : {exc}") from exc

    def find_vehicle_history(self, marque: str, modele: str, annee: int) -> list[Simulation]:
        """Historique chronologique d'un véhicule (marque + modèle + année)."""
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM simulations "
                    "WHERE marque = ? COLLATE NOCASE AND modele = ? COLLATE NOCASE "
                    "AND annee = ? "
                    "ORDER BY date ASC, id ASC",
                    (marque, modele, annee),
                ).fetchall()
            finally:
                conn.close()
            return [_row_to_simulation(row) for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire l'historique du véhicule : {exc}") from exc

    def distinct_brands(self) -> list[str]:
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT DISTINCT marque FROM simulations ORDER BY marque COLLATE NOCASE"
                ).fetchall()
            finally:
                conn.close()
            return [row["marque"] for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire les marques : {exc}") from exc

    def distinct_models(self, marque: str) -> list[str]:
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT DISTINCT modele FROM simulations "
                    "WHERE marque = ? COLLATE NOCASE ORDER BY modele COLLATE NOCASE",
                    (marque,),
                ).fetchall()
            finally:
                conn.close()
            return [row["modele"] for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire les modèles : {exc}") from exc

    def distinct_years(self, marque: str, modele: str) -> list[int]:
        try:
            conn = connect()
            try:
                rows = conn.execute(
                    "SELECT DISTINCT annee FROM simulations "
                    "WHERE marque = ? COLLATE NOCASE AND modele = ? COLLATE NOCASE "
                    "ORDER BY annee DESC",
                    (marque, modele),
                ).fetchall()
            finally:
                conn.close()
            return [row["annee"] for row in rows]
        except Exception as exc:
            raise DatabaseError(f"Impossible de lire les années : {exc}") from exc
