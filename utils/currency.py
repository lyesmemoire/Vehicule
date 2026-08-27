"""Formatage et analyse des montants financiers (style français).

Convention d'affichage :
- séparateur de milliers : espace insécable classique -> « 1 450 000 DA »
- séparateur décimal     : virgule                       -> « 1,5 L »
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

THOUSANDS_SEP = " "
DECIMAL_SEP = ","


def parse_decimal(raw: object) -> Decimal:
    """Convertit une saisie utilisateur en ``Decimal``.

    Accepte les espaces (milliers) et la virgule décimale.
    Lève ``ValueError`` si la valeur est vide ou invalide.
    """
    if raw is None:
        raise ValueError("Valeur vide")
    text = (
        str(raw)
        .strip()
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace(" ", "")
    )
    if not text:
        raise ValueError("Valeur vide")
    text = text.replace(DECIMAL_SEP, ".")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Nombre invalide : {raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"Nombre non fini : {raw!r}")
    return value


def _quantize(value: Decimal, decimals: int) -> Decimal:
    quantum = Decimal(1).scaleb(-decimals)
    return Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def format_number(value: Decimal, decimals: int = 0) -> str:
    """Formate un nombre à la française : « 1 875 000 » ou « 1,5 »."""
    quantized = _quantize(value, decimals)
    sign = "-" if quantized < 0 else ""
    text = f"{abs(quantized):f}"
    if "." in text:
        int_part, frac_part = text.split(".")
    else:
        int_part, frac_part = text, ""
    # Groupement des milliers par tranches de 3, de droite à gauche
    groups = []
    while int_part:
        groups.append(int_part[-3:])
        int_part = int_part[:-3]
    grouped = THOUSANDS_SEP.join(reversed(groups))
    result = sign + grouped
    if frac_part:
        result += DECIMAL_SEP + frac_part
    return result


def format_amount(value: Decimal, suffix: str = "DA", decimals: int | None = None) -> str:
    """Formate un montant.

    ``decimals=None`` (défaut) : décimales affichées seulement si nécessaire.
    ``decimals=2`` : toujours deux décimales (tableaux de l'historique).
    """
    value = Decimal(value)
    if decimals is None:
        decimals = 0 if value == value.to_integral_value() else 2
    return f"{format_number(value, decimals)} {suffix}"


def format_dzd(value: Decimal, decimals: int | None = None) -> str:
    """Montant en dinars algériens : « 2 487 500 DA » (ou « … ,50 DA »)."""
    return format_amount(value, "DA", decimals)


def format_usd(value: Decimal, decimals: int | None = None) -> str:
    """Montant en dollars : « 8 200 USD » (ou « 8 200,00 USD »)."""
    return format_amount(value, "USD", decimals)


def format_signed_usd(value: Decimal) -> str:
    """Variation signée : « -500 USD » ou « +350 USD »."""
    value = Decimal(value)
    prefix = "+" if value > 0 else ""
    return f"{prefix}{format_usd(value)}"


def format_percent(fraction: Decimal) -> str:
    """Formate une fraction en pourcentage : 0.15 -> « 15 % », 0.0610 -> « 6,1 %»."""
    percent = _quantize(Decimal(fraction) * 100, 2)
    decimals = 0 if percent == percent.to_integral_value() else 2
    return f"{format_number(percent, decimals)} %"


def format_signed_percent(percent_value: Decimal) -> str:
    """Variation en pourcentage déjà exprimée en % : « -6,1 % »."""
    percent_value = _quantize(Decimal(percent_value), 2)
    prefix = "+" if percent_value > 0 else ""
    decimals = 0 if percent_value == percent_value.to_integral_value() else 2
    return f"{prefix}{format_number(percent_value, decimals)} %"


def decimal_to_str(value: Decimal) -> str:
    """Représentation compacte et canonique (sans zéros superflus) : 1.50 -> « 1.5 »."""
    text = f"{Decimal(value):f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
