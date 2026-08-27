"""Véhicule saisi par l'utilisateur."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from utils.currency import decimal_to_str


@dataclass(frozen=True)
class Vehicle:
    """Identité du véhicule concerné par la simulation."""

    marque: str
    modele: str
    annee: int
    cylindree: Decimal  # en litres

    @property
    def label(self) -> str:
        """Libellé d'affichage : « LIVAN X3 PRO 2025 »."""
        return f"{self.marque} {self.modele} {self.annee}".upper()

    @property
    def cylindree_label(self) -> str:
        return f"{decimal_to_str(self.cylindree)} L"
