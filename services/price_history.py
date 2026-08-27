"""Statistiques d'évolution des prix pour un véhicule donné."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from models.simulation import Simulation

_CENT = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceStats:
    """Statistiques calculées sur l'historique d'un véhicule."""

    points: list  # list[tuple[date, Decimal, Decimal]] : (date, prix USD, coût total DZD)
    premier: Decimal
    dernier: Decimal
    variation: Decimal  # dernier - premier
    variation_pct: Decimal | None  # en points de %
    minimum: Decimal
    maximum: Decimal
    moyenne: Decimal

    @property
    def count(self) -> int:
        return len(self.points)


def compute_price_stats(sims: list[Simulation]) -> PriceStats | None:
    """Calcule min / max / moyenne / variations sur une liste chronologique.

    Renvoie ``None`` si aucune simulation n'est fournie.
    """
    if not sims:
        return None
    ordered = sorted(sims, key=lambda s: (s.date, s.id or 0))
    points = [(s.date, s.prix_usd, s.cout_total) for s in ordered]
    prix = [p for _, p, _ in points]

    premier = prix[0]
    dernier = prix[-1]
    variation = dernier - premier
    variation_pct = (
        _q2(variation / premier * 100) if premier != 0 else None
    )

    return PriceStats(
        points=points,
        premier=premier,
        dernier=dernier,
        variation=variation,
        variation_pct=variation_pct,
        minimum=min(prix),
        maximum=max(prix),
        moyenne=_q2(sum(prix) / len(prix)),
    )
