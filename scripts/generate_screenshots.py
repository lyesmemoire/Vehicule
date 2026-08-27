"""Script de développement : test d'intégration de l'interface + captures d'écran.

Exécute l'application complète en mode « offscreen » (sans écran), vérifie les
flux principaux (calcul, enregistrement, historique, évolution, paramètres)
puis enregistre des captures dans docs/.

Utilisation :
    python scripts/generate_screenshots.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["VEHICLE_COST_DATA_DIR"] = tempfile.mkdtemp(prefix="vcc_smoke_")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from database.db import init_database  # noqa: E402
from database.repositories import SimulationRepository  # noqa: E402
from models.simulation import Simulation  # noqa: E402
from models.vehicle import Vehicle  # noqa: E402
from services.calculator import compute_cost  # noqa: E402

DOCS = PROJECT_ROOT / "docs"
DOCS.mkdir(exist_ok=True)


def seed_sample_data() -> None:
    """Données de démonstration pour l'historique et le graphique."""
    repo = SimulationRepository()
    samples = [
        ("Livan", "X3 Pro", 2025, Decimal("1.5"), Decimal("8200"), Decimal("1700"), date(2026, 8, 12)),
        ("Livan", "X3 Pro", 2025, Decimal("1.5"), Decimal("7950"), Decimal("1700"), date(2026, 8, 20)),
        ("Livan", "X3 Pro", 2025, Decimal("1.5"), Decimal("7700"), Decimal("1700"), date(2026, 8, 27)),
        ("Kia", "Picanto", 2024, Decimal("1.0"), Decimal("9500"), Decimal("1600"), date(2026, 8, 25)),
    ]
    for marque, modele, annee, cyl, prix, fret, sim_date in samples:
        vehicle = Vehicle(marque, modele, annee, cyl)
        result = compute_cost(vehicle, prix, fret, Decimal("250"))
        repo.save(Simulation.from_result(result, sim_date))


def main() -> int:
    init_database()
    seed_sample_data()

    app = QApplication([])
    from ui.styles import APP_STYLESHEET

    app.setStyleSheet(APP_STYLESHEET)  # même rendu que main.py

    from ui.main_window import MainWindow

    window = MainWindow(version="1.0.0")
    window.show()
    app.processEvents()

    # ---------- 1. Calculateur : calcul d'exemple (Geely Emgrand 2025, 1.5 L)
    calc = window.calc_page
    calc.marque_cb.setEditText("Geely")
    calc._refresh_model_combo("Geely", keep_text="Emgrand")
    calc.annee_sp.setValue(2025)
    calc.cylindree_edit.setText("1.5")
    calc.prix_edit.setText("8900")
    calc.fret_edit.setText("1800")
    window.tabs.setCurrentIndex(0)
    app.processEvents()

    calc.compute_clicked()
    app.processEvents()
    total = calc.total_value.text()
    # 2 675 000 (valeur douanière) + 401 250 (douane 15 %) + 584 487,50 (TVA) + 200 000 (frais fixes)
    assert total == "3 860 737,50 DA", f"Coût total inattendu : {total}"
    assert calc.value_labels["taux_douane"].text() == "15 %"
    print("✓ Calcul : total =", total)

    # Enregistrement (sans boîte de dialogue : pas en mode modification)
    calc.save_clicked()
    app.processEvents()
    assert len(window.sim_repo.list_all()) == 5
    print("✓ Enregistrement : 5 simulations en base")

    window.grab().save(str(DOCS / "screenshot_1_calculateur.png"))

    # ---------- 2. Historique
    window.history_page.refresh()
    app.processEvents()
    visible = window.history_page.proxy.rowCount()
    assert visible == 5, f"Historique : {visible} lignes affichées au lieu de 5"

    window.history_page.search_marque.setText("livan")
    app.processEvents()
    assert window.history_page.proxy.rowCount() == 3, "Filtre marque inopérant"
    window.history_page.search_marque.setText("")
    print("✓ Historique : tri, filtres et compteurs OK")

    window.tabs.setCurrentIndex(1)
    app.processEvents()
    window.grab().save(str(DOCS / "screenshot_2_historique.png"))

    # ---------- 3. Évolution des prix
    evolution = window.evolution_page
    window.tabs.setCurrentIndex(2)
    app.processEvents()
    evolution.marque_cb.setCurrentText("Livan")
    evolution.modele_cb.setCurrentText("X3 Pro")
    index = evolution.annee_cb.findData(2025)
    assert index >= 0
    evolution.annee_cb.setCurrentIndex(index)
    app.processEvents()

    from utils.currency import format_signed_usd

    assert evolution.stat_labels["premier"].text() == "8 200 USD"
    assert evolution.stat_labels["dernier"].text() == "7 700 USD"
    assert evolution.stat_labels["variation"].text() == "-500 USD"
    assert evolution.stat_labels["variation_pct"].text() in ("-6,1 %", "-6,10 %")
    print("✓ Évolution :", format_signed_usd(Decimal("-500")), "/ -6,1 % — graphique affiché")
    window.grab().save(str(DOCS / "screenshot_3_evolution.png"))

    # ---------- 4. Paramètres
    window.tabs.setCurrentIndex(3)
    app.processEvents()
    assert window.settings_page.fields["taux_change"].text() == "250"
    assert window.settings_page.fields["seuil_cylindree"].text() == "1.8"
    print("✓ Paramètres : valeurs par défaut chargées")
    window.grab().save(str(DOCS / "screenshot_4_parametres.png"))

    print("\nTous les tests d'intégration sont passés. Captures enregistrées dans docs/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
