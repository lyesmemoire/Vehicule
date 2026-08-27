"""Simulation enregistrée en base : entrées + résultats de calcul."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from models.vehicle import Vehicle

if TYPE_CHECKING:  # aucune dépendance models -> services à l'exécution
    from services.calculator import SimulationResult


@dataclass
class Simulation:
    """Ligne complète d'une simulation (telle que stockée en SQLite).

    ``taux_douane`` est exprimé en pourcentage (15 = 15 %).
    """

    date: date
    marque: str
    modele: str
    annee: int
    cylindree: Decimal
    prix_usd: Decimal
    fret_usd: Decimal
    taux_change: Decimal
    prix_dzd: Decimal
    fret_dzd: Decimal
    valeur_douaniere: Decimal
    taux_douane: Decimal
    droits_douane: Decimal
    tva: Decimal
    frais_transitaire: Decimal
    frais_portuaires: Decimal
    taxe_vehicule: Decimal
    cout_total: Decimal
    id: int | None = None

    @property
    def base_tva(self) -> Decimal:
        """Base de calcul de la TVA : valeur douanière + droits de douane."""
        return self.valeur_douaniere + self.droits_douane

    @property
    def vehicle(self) -> Vehicle:
        return Vehicle(
            marque=self.marque,
            modele=self.modele,
            annee=self.annee,
            cylindree=self.cylindree,
        )

    @property
    def label(self) -> str:
        return f"{self.marque} {self.modele} {self.annee}".upper()

    @classmethod
    def from_result(
        cls,
        result: SimulationResult,
        sim_date: date,
        sim_id: int | None = None,
    ) -> Simulation:
        """Construit la ligne persistable à partir d'un résultat de calcul."""
        return cls(
            id=sim_id,
            date=sim_date,
            marque=result.marque,
            modele=result.modele,
            annee=result.annee,
            cylindree=result.cylindree,
            prix_usd=result.prix_usd,
            fret_usd=result.fret_usd,
            taux_change=result.taux_change,
            prix_dzd=result.prix_dzd,
            fret_dzd=result.fret_dzd,
            valeur_douaniere=result.valeur_douaniere,
            taux_douane=result.taux_douane * 100,  # stockage en pourcentage
            droits_douane=result.droits_douane,
            tva=result.tva,
            frais_transitaire=result.frais_transitaire,
            frais_portuaires=result.frais_portuaires,
            taxe_vehicule=result.taxe_vehicule,
            cout_total=result.cout_total,
        )

    def duplicate(self, new_date: date) -> Simulation:
        """Copie de travail pour la duplication (date = jour de la copie)."""
        return replace(self, id=None, date=new_date)
