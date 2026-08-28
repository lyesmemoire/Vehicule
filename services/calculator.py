"""Logique financière centralisée : aucune formule dans l'interface.

Tous les montants sont manipulés avec ``Decimal`` pour éviter les erreurs
d'arrondi binaires, puis quantifiés au centime (arrondi demi-unité vers
le haut, usage comptable).

Les taux (douane, TVA, seuil de cylindrée, frais fixes) sont des
**paramètres de calcul définis par l'utilisateur** : ils ne constituent
pas une garantie de conformité réglementaire.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from models.vehicle import Vehicle
from utils.currency import parse_decimal

CENT = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    """Quantifie au centime (arrondi comptable)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


# Valeurs par défaut de l'application (texte tel que stocké en base).
DEFAULT_SETTINGS: dict[str, str] = {
    "taux_change": "250",
    "tva": "19",
    "douane_le_seuil": "15",
    "douane_sup_seuil": "30",
    "seuil_cylindree": "1.8",
    "frais_transitaire": "70000",
    "frais_portuaires": "130000",
    "taxe_vehicule": "0",
    "taux_eur": "270",
    "taux_cny": "35",
    "taux_fret_usd": "250",
    "taux_fret_eur": "270",
    "taux_fret_cny": "35",
}

# Devises gérées et clés de paramètres de leurs taux par défaut.
# « achat » = taux appliqué au prix du véhicule (souvent taux parallèle) ;
# « fret »  = taux appliqué au fret (souvent taux bancaire officiel).
DEVISES = ("USD", "EUR", "CNY")
DEVISE_RATE_KEYS = {"USD": "taux_change", "EUR": "taux_eur", "CNY": "taux_cny"}
DEVISE_RATE_FALLBACKS = {"USD": "250", "EUR": "270", "CNY": "35"}
DEVISE_FREIGHT_KEYS = {
    "USD": "taux_fret_usd", "EUR": "taux_fret_eur", "CNY": "taux_fret_cny",
}


def _to_decimal(raw: object, fallback: Decimal) -> Decimal:
    try:
        return parse_decimal(raw)
    except ValueError:
        return fallback


@dataclass(frozen=True)
class CalculationParams:
    """Paramètres de calcul issus de l'onglet Paramètres."""

    tva_taux: Decimal = Decimal("0.19")
    douane_taux_le_seuil: Decimal = Decimal("0.15")
    douane_taux_sup_seuil: Decimal = Decimal("0.30")
    seuil_cylindree: Decimal = Decimal("1.8")
    frais_transitaire: Decimal = Decimal("70000")
    frais_portuaires: Decimal = Decimal("130000")
    taxe_vehicule_defaut: Decimal = Decimal("0")  # valeur par défaut du formulaire

    @classmethod
    def defaults(cls) -> CalculationParams:
        return cls()

    @classmethod
    def from_settings(cls, settings: dict) -> CalculationParams:
        def dec(key: str, fallback: Decimal) -> Decimal:
            return _to_decimal(settings.get(key, ""), fallback)

        return cls(
            tva_taux=dec("tva", Decimal("19")) / 100,
            douane_taux_le_seuil=dec("douane_le_seuil", Decimal("15")) / 100,
            douane_taux_sup_seuil=dec("douane_sup_seuil", Decimal("30")) / 100,
            seuil_cylindree=dec("seuil_cylindree", Decimal("1.8")),
            frais_transitaire=dec("frais_transitaire", Decimal("70000")),
            frais_portuaires=dec("frais_portuaires", Decimal("130000")),
            taxe_vehicule_defaut=dec("taxe_vehicule", Decimal("0")),
        )


@dataclass(frozen=True)
class SimulationResult:
    """Résultat complet d'un calcul de coût de revient."""

    marque: str
    modele: str
    annee: int
    cylindree: Decimal
    prix_usd: Decimal
    fret_usd: Decimal
    taux_change: Decimal      # taux appliqué au prix d'achat

    prix_dzd: Decimal
    fret_dzd: Decimal
    valeur_douaniere: Decimal
    taux_douane: Decimal  # fraction : 0.15 = 15 %
    droits_douane: Decimal
    base_tva: Decimal
    tva: Decimal
    frais_transitaire: Decimal
    frais_portuaires: Decimal
    taxe_vehicule: Decimal
    cout_total: Decimal
    devise: str = "USD"  # devise du prix et du fret saisis
    taux_fret: Decimal = Decimal("0")  # taux appliqué au fret (0 = identique à achat)


def convert_to_dzd(montant_usd: Decimal, taux_usd_dzd: Decimal) -> Decimal:
    """Convertit un montant USD vers DZD : montant × taux."""
    return _q2(montant_usd * taux_usd_dzd)


def calculate_customs_rate(
    cylindree: Decimal,
    seuil: Decimal = Decimal("1.8"),
    taux_le_seuil: Decimal = Decimal("0.15"),
    taux_sup_seuil: Decimal = Decimal("0.30"),
) -> Decimal:
    """Taux de douane appliqué selon la cylindrée (fraction).

    Exemple : 1.5 L -> 0.15 (15 %) ; 2.0 L -> 0.30 (30 %).
    """
    if cylindree <= seuil:
        return taux_le_seuil
    return taux_sup_seuil


def calculate_customs_duty(valeur_douaniere: Decimal, taux_douane: Decimal) -> Decimal:
    """Droits de douane : valeur douanière × taux."""
    return _q2(valeur_douaniere * taux_douane)


def calculate_vat(base_tva: Decimal, taux_tva: Decimal) -> Decimal:
    """TVA : (valeur douanière + droits de douane) × taux de TVA."""
    return _q2(base_tva * taux_tva)


def calculate_total_cost(
    prix_dzd: Decimal,
    fret_dzd: Decimal,
    droits_douane: Decimal,
    tva: Decimal,
    frais_transitaire: Decimal,
    frais_portuaires: Decimal,
    taxe_vehicule: Decimal = Decimal("0"),
) -> Decimal:
    """Coût total rendu en Algérie (somme de toutes les composantes)."""
    return _q2(
        prix_dzd
        + fret_dzd
        + droits_douane
        + tva
        + frais_transitaire
        + frais_portuaires
        + taxe_vehicule
    )


def compute_cost(
    vehicle: Vehicle,
    prix_usd: Decimal,
    fret_usd: Decimal,
    taux_change: Decimal,
    params: CalculationParams | None = None,
    taxe_vehicule: Decimal = Decimal("0"),
    devise: str = "USD",
    taux_fret: Decimal | None = None,
) -> SimulationResult:
    """Calcule l'ensemble des composantes du coût d'importation.

    ``taux_change`` s'applique au prix d'achat, ``taux_fret`` au fret
    (par défaut : identique au taux d'achat).
    """
    params = params or CalculationParams.defaults()
    taux_fret = taux_change if taux_fret is None else taux_fret

    prix_dzd = convert_to_dzd(prix_usd, taux_change)
    fret_dzd = convert_to_dzd(fret_usd, taux_fret)
    valeur_douaniere = _q2(prix_dzd + fret_dzd)

    taux_douane = calculate_customs_rate(
        vehicle.cylindree,
        seuil=params.seuil_cylindree,
        taux_le_seuil=params.douane_taux_le_seuil,
        taux_sup_seuil=params.douane_taux_sup_seuil,
    )
    droits_douane = calculate_customs_duty(valeur_douaniere, taux_douane)

    base_tva = _q2(valeur_douaniere + droits_douane)
    tva = calculate_vat(base_tva, params.tva_taux)

    cout_total = calculate_total_cost(
        prix_dzd=prix_dzd,
        fret_dzd=fret_dzd,
        droits_douane=droits_douane,
        tva=tva,
        frais_transitaire=_q2(params.frais_transitaire),
        frais_portuaires=_q2(params.frais_portuaires),
        taxe_vehicule=_q2(taxe_vehicule),
    )

    return SimulationResult(
        marque=vehicle.marque,
        modele=vehicle.modele,
        annee=vehicle.annee,
        cylindree=vehicle.cylindree,
        prix_usd=_q2(prix_usd),
        fret_usd=_q2(fret_usd),
        taux_change=taux_change,
        taux_fret=_q2(taux_fret),
        prix_dzd=prix_dzd,
        fret_dzd=fret_dzd,
        valeur_douaniere=valeur_douaniere,
        taux_douane=taux_douane,
        droits_douane=droits_douane,
        base_tva=base_tva,
        tva=tva,
        frais_transitaire=_q2(params.frais_transitaire),
        frais_portuaires=_q2(params.frais_portuaires),
        taxe_vehicule=_q2(taxe_vehicule),
        cout_total=cout_total,
        devise=devise,
    )
