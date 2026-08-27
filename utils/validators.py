"""Validation des saisies utilisateur avec messages d'erreur en français.

Module **sans aucune dépendance Qt** : réutilisable tel quel pour une future
version web ou mobile. Les motifs de saisie Qt (QValidator) sont définis
dans ``ui/components.py`` ; le contrôle final reste assuré ici.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from utils.currency import parse_decimal

MIN_YEAR = 1950
MAX_YEAR_MARGIN = 2  # année-modèle maximale : année courante + 2


class ValidationError(Exception):
    """Erreur de saisie avec message destiné à l'utilisateur."""



@dataclass(frozen=True)
class SimulationInput:
    """Données de simulation validées et normalisées."""

    marque: str
    modele: str
    annee: int
    cylindree: Decimal
    prix_usd: Decimal
    fret_usd: Decimal
    taux_change: Decimal
    date_simulation: date
    taxe_vehicule: Decimal = Decimal("0")  # optionnel : vide = 0


def _parse_positive(
    raw: str,
    empty_message: str,
    negative_message: str,
    *,
    allow_zero: bool = False,
) -> Decimal:
    try:
        value = parse_decimal(raw)
    except ValueError:
        raise ValidationError(empty_message) from None
    if value < 0:
        raise ValidationError(negative_message)
    if value == 0 and not allow_zero:
        raise ValidationError(empty_message)
    return value


def validate_simulation_input(
    *,
    marque: str,
    modele: str,
    annee: int,
    cylindree: str,
    prix_usd: str,
    fret_usd: str,
    taux_change: str,
    date_simulation: date,
    taxe_vehicule: str = "",
    require_identity: bool = False,
) -> SimulationInput:
    """Valide l'ensemble de la saisie et renvoie des valeurs normalisées.

    Lève :class:`ValidationError` avec un message clair en français.
    """
    marque = (marque or "").strip()
    modele = (modele or "").strip()

    if require_identity:
        if not marque:
            raise ValidationError("Veuillez saisir la marque du véhicule.")
        if not modele:
            raise ValidationError("Veuillez saisir le modèle du véhicule.")

    current_year = date.today().year
    try:
        annee_value = int(annee)
    except (TypeError, ValueError):
        raise ValidationError("Veuillez saisir une année valide.") from None
    if not (MIN_YEAR <= annee_value <= current_year + MAX_YEAR_MARGIN):
        raise ValidationError(
            f"Veuillez saisir une année valide (entre {MIN_YEAR} et "
            f"{current_year + MAX_YEAR_MARGIN})."
        )

    cylindree_value = _parse_positive(
        cylindree,
        "Veuillez saisir une cylindrée valide (supérieure à 0 litre).",
        "La cylindrée ne peut pas être négative.",
    )
    if cylindree_value > 20:
        raise ValidationError("Veuillez saisir une cylindrée valide (20 L maximum).")

    prix_value = _parse_positive(
        prix_usd,
        "Veuillez saisir un prix de véhicule valide.",
        "Le prix du véhicule ne peut pas être négatif.",
        allow_zero=True,
    )
    fret_value = _parse_positive(
        fret_usd,
        "Veuillez saisir un montant de fret valide.",
        "Le fret ne peut pas être négatif.",
        allow_zero=True,
    )
    taux_value = _parse_positive(
        taux_change,
        "Veuillez saisir un taux de change valide (supérieur à 0).",
        "Le taux de change doit être supérieur à 0.",
    )

    # Taxe véhicule : champ optionnel, vide = 0, jamais négatif
    taxe_value = Decimal("0")
    raw_taxe = (taxe_vehicule or "").strip()
    if raw_taxe:
        try:
            taxe_value = parse_decimal(raw_taxe)
        except ValueError:
            raise ValidationError(
                "Veuillez saisir un montant de taxe véhicule valide."
            ) from None
        if taxe_value < 0:
            raise ValidationError("La taxe véhicule ne peut pas être négative.")

    return SimulationInput(
        marque=marque,
        modele=modele,
        annee=annee_value,
        cylindree=cylindree_value,
        prix_usd=prix_value,
        fret_usd=fret_value,
        taux_change=taux_value,
        date_simulation=date_simulation,
        taxe_vehicule=taxe_value,
    )


@dataclass(frozen=True)
class SettingsInput:
    """Paramètres de calcul validés."""

    taux_change: Decimal
    tva: Decimal
    douane_le_seuil: Decimal
    douane_sup_seuil: Decimal
    seuil_cylindree: Decimal
    frais_transitaire: Decimal
    frais_portuaires: Decimal
    taxe_vehicule: Decimal

    def as_dict(self) -> dict[str, str]:
        from utils.currency import decimal_to_str

        return {
            "taux_change": decimal_to_str(self.taux_change),
            "tva": decimal_to_str(self.tva),
            "douane_le_seuil": decimal_to_str(self.douane_le_seuil),
            "douane_sup_seuil": decimal_to_str(self.douane_sup_seuil),
            "seuil_cylindree": decimal_to_str(self.seuil_cylindree),
            "frais_transitaire": decimal_to_str(self.frais_transitaire),
            "frais_portuaires": decimal_to_str(self.frais_portuaires),
            "taxe_vehicule": decimal_to_str(self.taxe_vehicule),
        }


def validate_settings_input(
    *,
    taux_change: str,
    tva: str,
    douane_le_seuil: str,
    douane_sup_seuil: str,
    seuil_cylindree: str,
    frais_transitaire: str,
    frais_portuaires: str,
    taxe_vehicule: str = "0",
) -> SettingsInput:
    def parse_or(raw: str, message: str) -> Decimal:
        try:
            return parse_decimal(raw)
        except ValueError:
            raise ValidationError(message) from None

    taux = parse_or(taux_change, "Veuillez saisir un taux de change valide (supérieur à 0).")
    if taux <= 0:
        raise ValidationError("Le taux de change doit être supérieur à 0.")

    tva_value = parse_or(tva, "Veuillez saisir un taux de TVA valide.")
    if not (0 <= tva_value <= 100):
        raise ValidationError("Le taux de TVA doit être compris entre 0 et 100 %.")

    douane_le = parse_or(
        douane_le_seuil, "Veuillez saisir un taux de douane valide (≤ seuil)."
    )
    douane_sup = parse_or(
        douane_sup_seuil, "Veuillez saisir un taux de douane valide (> seuil)."
    )
    for taux_douane, message in (
        (douane_le, "Le taux de douane (≤ seuil) doit être compris entre 0 et 100 %."),
        (douane_sup, "Le taux de douane (> seuil) doit être compris entre 0 et 100 %."),
    ):
        if not (0 <= taux_douane <= 100):
            raise ValidationError(message)

    seuil = parse_or(seuil_cylindree, "Veuillez saisir un seuil de cylindrée valide.")
    if not (Decimal("0.1") <= seuil <= 20):
        raise ValidationError("Le seuil de cylindrée doit être compris entre 0.1 et 20 litres.")

    transitaire = parse_or(
        frais_transitaire, "Veuillez saisir un montant de prestation transitaire valide."
    )
    portuaires = parse_or(
        frais_portuaires, "Veuillez saisir un montant de frais portuaires valide."
    )
    taxe_vehicule_value = parse_or(
        taxe_vehicule, "Veuillez saisir un montant de taxe véhicule valide."
    )
    if transitaire < 0 or portuaires < 0 or taxe_vehicule_value < 0:
        raise ValidationError("Les frais et taxes ne peuvent pas être négatifs.")

    return SettingsInput(
        taux_change=taux,
        tva=tva_value,
        douane_le_seuil=douane_le,
        douane_sup_seuil=douane_sup,
        seuil_cylindree=seuil,
        frais_transitaire=transitaire,
        frais_portuaires=portuaires,
        taxe_vehicule=taxe_vehicule_value,
    )
