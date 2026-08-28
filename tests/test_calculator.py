"""Tests unitaires de la logique métier (sans interface).

Exécution :
    python tests/test_calculator.py
ou  pytest tests/test_calculator.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("VEHICLE_COST_DATA_DIR", tempfile.mkdtemp(prefix="vcc_tests_"))

from database.db import init_database
from database.repositories import (
    CatalogRepository,
    SettingsRepository,
    SimulationRepository,
)
from models.simulation import Simulation
from models.vehicle import Vehicle
from services.calculator import (
    DEFAULT_SETTINGS,
    CalculationParams,
    calculate_customs_duty,
    calculate_customs_rate,
    calculate_total_cost,
    calculate_vat,
    compute_cost,
    convert_to_dzd,
)
from services.price_history import compute_price_stats
from utils.currency import (
    decimal_to_str,
    format_dzd,
    format_number,
    format_percent,
    format_signed_percent,
    format_signed_usd,
    format_usd,
    parse_decimal,
)

D = Decimal

# Base de test initialisée une seule fois (dossier temporaire isolé)
init_database()


def test_customs_rate():
    assert calculate_customs_rate(D("1.5")) == D("0.15")
    assert calculate_customs_rate(D("1.8")) == D("0.15")   # ≤ 1.8 L
    assert calculate_customs_rate(D("1.81")) == D("0.30")
    assert calculate_customs_rate(D("2.0")) == D("0.30")


def test_example_from_spec():
    """Exemple du cahier des charges : Livan X3 Pro 2025, 1.5 L, 7 500 USD."""
    vehicle = Vehicle("Livan", "X3 Pro", 2025, D("1.5"))
    result = compute_cost(vehicle, D("7500"), D("1700"), D("250"), CalculationParams.defaults())
    assert result.prix_dzd == D("1875000.00")
    assert result.fret_dzd == D("425000.00")
    assert result.valeur_douaniere == D("2300000.00")
    assert result.taux_douane == D("0.15")
    assert result.droits_douane == D("345000.00")
    assert result.base_tva == D("2645000.00")
    assert result.tva == D("502550.00")
    assert result.cout_total == D("3347550.00")


def test_example_over_threshold():
    vehicle = Vehicle("Kia", "Sportage", 2025, D("2.0"))
    result = compute_cost(vehicle, D("7500"), D("1700"), D("250"), CalculationParams.defaults())
    assert result.taux_douane == D("0.30")
    assert result.droits_douane == D("690000.00")
    assert result.base_tva == D("2990000.00")
    assert result.tva == D("568100.00")
    assert result.cout_total == D("3758100.00")


def test_decimal_functions():
    assert convert_to_dzd(D("100"), D("250")) == D("25000.00")
    assert calculate_customs_duty(D("1000"), D("0.15")) == D("150.00")
    assert calculate_vat(D("1000"), D("0.19")) == D("190.00")
    total = calculate_total_cost(D("100"), D("100"), D("100"), D("100"), D("100"), D("100"))
    assert total == D("600.00")


def test_formatting():
    assert format_dzd(D("2487500")) == "2 487 500 DA"
    assert format_dzd(D("3347550.00")) == "3 347 550 DA"
    assert format_usd(D("8200")) == "8 200 USD"
    # Harmonisation Historique : toujours 2 décimales
    assert format_usd(D("8200"), 2) == "8 200,00 USD"
    assert format_dzd(D("3347550"), 2) == "3 347 550,00 DA"
    assert format_number(D("250"), 2) == "250,00"
    assert format_percent(D("0.15")) == "15 %"
    assert format_signed_usd(D("-500")) == "-500 USD"
    assert format_signed_usd(D("350")) == "+350 USD"
    assert format_signed_percent(D("-6.10")) == "-6,10 %"  # format de l'exemple du cahier des charges
    assert decimal_to_str(D("1.50")) == "1.5"


def test_parse_decimal():
    assert parse_decimal("1 234,56") == D("1234.56")
    assert parse_decimal("250") == D("250")
    assert parse_decimal("1.8") == D("1.8")
    # parse_decimal accepte les négatifs : c'est la couche validation qui les refuse.
    assert parse_decimal("-5") == D("-5")
    for bad in ("", "abc", None):
        try:
            parse_decimal(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"parse_decimal({bad!r}) aurait dû échouer")

    # La validation refuse les saisies négatives et vides
    from utils.validators import ValidationError, validate_simulation_input

    common = dict(
        marque="Livan", modele="X3 Pro", annee=2025, date_simulation=date(2026, 8, 12)
    )
    base = dict(common, cylindree="1.5", prix_usd="7500", fret_usd="1700", taux_change="250")
    for field, value in (
        ("cylindree", "-1.5"), ("cylindree", ""), ("cylindree", "0"),
        ("prix_usd", "-100"), ("prix_usd", ""),
        ("fret_usd", "-100"), ("fret_usd", ""),
        ("taux_change", "-10"), ("taux_change", "0"), ("taux_change", ""),
    ):
        kwargs = dict(base)
        kwargs[field] = value
        try:
            validate_simulation_input(**kwargs)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"La saisie {field}={value!r} aurait dû être refusée")
    try:
        validate_simulation_input(**{**base, "annee": 1900})
    except ValidationError:
        pass
    else:
        raise AssertionError("L'année 1900 aurait dû être refusée")


def test_settings_repository():
    init_database()
    repo = SettingsRepository()
    settings = repo.get_all()
    assert settings["taux_change"] == "250"
    assert settings["tva"] == "19"
    assert settings["frais_transitaire"] == "70000"
    assert settings["taxe_vehicule"] == "0"
    assert CalculationParams.from_settings(settings) == CalculationParams.defaults()

    repo.save({"taux_change": "260", "tva": "20"})
    settings = repo.get_all()
    assert settings["taux_change"] == "260"
    params = CalculationParams.from_settings(settings)
    assert params.tva_taux == D("0.20")
    repo.reset_defaults()
    assert repo.get_all()["taux_change"] == "250"


def test_simulation_roundtrip():
    init_database()
    repo = SimulationRepository()
    vehicle = Vehicle("Livan", "X3 Pro", 2025, D("1.5"))
    result = compute_cost(vehicle, D("7500"), D("1700"), D("250"))
    sim = Simulation.from_result(result, date(2026, 8, 12))

    sim_id = repo.save(sim)
    assert sim_id > 0
    loaded = repo.get(sim_id)
    assert loaded is not None
    assert loaded.marque == "Livan"
    assert loaded.modele == "X3 Pro"
    assert loaded.cout_total == result.cout_total
    assert loaded.taux_douane == D("15.00")  # stocké en pourcentage
    assert loaded.base_tva == D("2645000.00")

    loaded.prix_usd = D("7000")
    repo.save(loaded)
    assert repo.get(sim_id).prix_usd == D("7000")

    # Duplication
    copy = loaded.duplicate(date(2026, 8, 20))
    copy_id = repo.save(copy)
    assert copy_id != sim_id

    assert len(repo.list_all()) >= 2
    repo.delete(copy_id)
    assert repo.get(copy_id) is None


def test_vehicle_history_and_stats():
    repo = SimulationRepository()
    specs = [
        (date(2026, 8, 12), "8200"),
        (date(2026, 8, 20), "7950"),
        (date(2026, 8, 27), "7700"),
    ]
    for sim_date, prix in specs:
        vehicle = Vehicle("Chery", "Tiggo 4 Pro", 2024, D("1.5"))  # véhicule dédié au test
        result = compute_cost(vehicle, D(prix), D("1700"), D("250"))
        repo.save(Simulation.from_result(result, sim_date))

    sims = repo.find_vehicle_history("CHERY", "tiggo 4 pro", 2024)  # insensible à la casse
    stats = compute_price_stats(sims)
    assert stats.premier == D("8200.00")
    assert stats.dernier == D("7700.00")
    assert stats.variation == D("-500.00")
    assert stats.variation_pct == D("-6.10")
    assert stats.minimum == D("7700.00")
    assert stats.maximum == D("8200.00")
    assert stats.moyenne == D("7950.00")
    assert stats.count == 3

    assert compute_price_stats([]) is None


def test_catalog():
    repo = CatalogRepository()
    repo.add_brand("New Brand")
    repo.add_brand("New Brand")  # pas de doublon
    repo.add_model("New Brand", "Model A")
    repo.add_model("New Brand", "Model A")
    assert "New Brand" in repo.list_brands()
    assert repo.list_models("new brand") == ["Model A"]


def test_builtin_catalog():
    """Catalogue embarqué marques/modèles (téléchargé de NHTSA + complément)."""
    from services import vehicle_catalog

    brands = vehicle_catalog.builtin_brands()
    assert len(brands) >= 50                      # 58 marques téléchargées
    assert vehicle_catalog.meta().get("models", 0) >= 2000
    for expected in ("Kia", "Hyundai", "Livan", "Dacia", "Peugeot", "Renault"):
        assert expected in brands, f"marque manquante : {expected}"

    kia = vehicle_catalog.builtin_models("Kia")
    assert "Picanto" in kia and "Morning" in kia and "Sportage" in kia
    assert vehicle_catalog.builtin_models("livan") == vehicle_catalog.builtin_models("LIVAN")
    assert "X3 Pro" in vehicle_catalog.builtin_models("LIVAN")
    assert vehicle_catalog.builtin_models("Marque Inexistante") == []

    # Fusion sans doublon, insensible à la casse, triée
    merged = vehicle_catalog.merge_names(["kia", "MG"], ["Kia", "mg", "Dacia"])
    assert merged == ["Dacia", "kia", "MG"]

    combo_brands = vehicle_catalog.brands_for_combo(["Marque Perso", "kia"])
    assert "Marque Perso" in combo_brands
    # Pas de doublon Kia (la première occurrence, « kia » de la base, est conservée)
    assert sum(1 for b in combo_brands if b.casefold() == "kia") == 1
    combo_models = vehicle_catalog.models_for_combo("Kia", ["Mon Modèle"])
    assert "Mon Modèle" in combo_models and "Picanto" in combo_models


def test_backup_restore():
    """Sauvegarde/restauration de la base (v1.3)."""
    from database.backup import (
        backup_dir,
        create_backup,
        list_backups,
        prune_auto_backups,
        restore_backup,
    )

    repo = SimulationRepository()
    vehicle = Vehicle("Livan", "X3 Pro", 2025, D("1.5"))
    result = compute_cost(vehicle, D("7500"), D("1700"), D("250"))
    sim_id = repo.save(Simulation.from_result(result, date(2026, 8, 27)))

    # Sauvegarde manuelle
    backup_path = create_backup("manual")
    assert backup_path.exists() and backup_path.suffix == ".bak"
    assert backup_path in list_backups()

    # Modification des données…
    repo.delete(sim_id)
    assert repo.get(sim_id) is None

    # …puis restauration : la simulation revient
    restored = restore_backup(backup_path)
    assert restored.exists()
    assert repo.get(sim_id) is not None
    assert repo.get(sim_id).cout_total == D("3347550.00")

    # Une copie de sécurité de l'état avant restauration a été créée
    assert any("_avant_restauration" in p.name for p in list_backups())

    # Fichiers invalides refusés
    import tempfile

    from database.db import DatabaseError as _DbError

    for content in (b"pas une base", b""):
        _, name = tempfile.mkstemp(suffix=".bak")
        Path(name).write_bytes(content)
        try:
            restore_backup(name)
        except _DbError:
            pass
        else:
            raise AssertionError("Sauvegarde invalide acceptée")

    # Purge des sauvegardes automatiques (10 conservées)
    for _ in range(13):
        create_backup("auto")
    prune_auto_backups()
    autos = [p for p in list_backups() if p.stem.endswith("_auto")]
    assert len(autos) <= 10
    assert backup_dir().exists()


def test_multidevise():
    """Multi-devises (v1.3) : USD / EUR / CNY par simulation."""
    vehicle = Vehicle("Dacia", "Logan", 2025, D("1.5"))

    # USD (par défaut) : inchangé
    r = compute_cost(vehicle, D("7500"), D("1700"), D("250"))
    assert r.devise == "USD"

    # EUR : devise enregistrée, math identique (le taux est fourni)
    r_eur = compute_cost(vehicle, D("7500"), D("1700"), D("270"), devise="EUR")
    assert r_eur.devise == "EUR"
    assert r_eur.prix_dzd == D("2025000.00")
    assert r_eur.fret_dzd == D("459000.00")
    assert r_eur.valeur_douaniere == D("2484000.00")  # 2 025 000 + 459 000

    # CNY
    r_cny = compute_cost(vehicle, D("7500"), D("1700"), D("35"), devise="CNY")
    assert r_cny.devise == "CNY"
    assert r_cny.prix_dzd == D("262500.00")

    # Persistance de la devise
    repo = SimulationRepository()
    sim_id = repo.save(Simulation.from_result(r_eur, date(2026, 8, 27)))
    loaded = repo.get(sim_id)
    assert loaded.devise == "EUR"
    assert loaded.prix_usd == D("7500.00")

    # Validation : devise inconnue refusée
    from utils.validators import ValidationError, validate_simulation_input

    try:
        validate_simulation_input(
            marque="Dacia", modele="Logan", annee=2025, cylindree="1.5",
            prix_usd="7500", fret_usd="1700", taux_change="270",
            date_simulation=date(2026, 8, 27), devise="GBP",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Devise GBP aurait dû être refusée")

    # Paramètres : les taux EUR/CNY par défaut sont présents et éditables
    settings_repo = SettingsRepository()
    settings = settings_repo.get_all()
    assert settings["taux_eur"] == "270"
    assert settings["taux_cny"] == "35"
    settings_repo.save({"taux_eur": "280", "taux_cny": "36"})
    settings = settings_repo.get_all()
    assert settings["taux_eur"] == "280" and settings["taux_cny"] == "36"
    settings_repo.reset_defaults()


def test_schema_migrations():
    """Les bases créées par d'anciennes versions sont migrées au démarrage."""
    import sqlite3

    from database.db import connect, get_db_path, init_database

    # Simule une base « ancienne » sans taxe_vehicule, devise ni base_tva
    conn = sqlite3.connect(get_db_path())
    conn.executescript(
        """
        DROP TABLE IF EXISTS simulations;
        CREATE TABLE simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            marque TEXT NOT NULL,
            modele TEXT NOT NULL,
            annee INTEGER NOT NULL,
            cylindree REAL NOT NULL,
            prix_usd REAL NOT NULL,
            fret_usd REAL NOT NULL,
            taux_change REAL NOT NULL,
            prix_dzd REAL NOT NULL,
            fret_dzd REAL NOT NULL,
            valeur_douaniere REAL NOT NULL,
            taux_douane REAL NOT NULL,
            droits_douane REAL NOT NULL,
            tva REAL NOT NULL,
            frais_transitaire REAL NOT NULL,
            frais_portuaires REAL NOT NULL,
            cout_total REAL NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    init_database()  # doit ajouter les colonnes manquantes sans erreur

    conn = connect()
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(simulations)")}
    finally:
        conn.close()
    assert {"taxe_vehicule", "devise", "base_tva"} <= columns


def test_taux_fret_separe():
    """v1.4 : taux d'achat et taux de fret distincts (parallèle vs officiel)."""
    vehicle = Vehicle("Dacia", "Logan", 2025, D("1.5"))

    # Taux distincts : achat au parallèle (250), fret au bancaire (160)
    r = compute_cost(vehicle, D("9000"), D("1500"), D("250"), taux_fret=D("160"))
    assert r.prix_dzd == D("2250000.00")   # 9 000 × 250
    assert r.fret_dzd == D("240000.00")    # 1 500 × 160 (et non 375 000)
    assert r.valeur_douaniere == D("2490000.00")
    assert r.taux_fret == D("160.00")

    # Sans taux_fret : identique au taux d'achat (compatibilité)
    r2 = compute_cost(vehicle, D("9000"), D("1500"), D("250"))
    assert r2.fret_dzd == D("375000.00")

    # Persistance : le taux fret enregistré est rechargé
    repo = SimulationRepository()
    sim_id = repo.save(Simulation.from_result(r, date(2026, 8, 28)))
    loaded = repo.get(sim_id)
    assert loaded.taux_fret == D("160.00")

    # Validation : vide = taux d'achat ; invalide refusé
    from utils.validators import ValidationError, validate_simulation_input

    base = dict(
        marque="Dacia", modele="Logan", annee=2025, cylindree="1.5",
        prix_usd="9000", fret_usd="1500", taux_change="250",
        date_simulation=date(2026, 8, 28),
    )
    ok = validate_simulation_input(**base)
    assert ok.taux_fret == D("250")
    ok = validate_simulation_input(**base, taux_fret="160")
    assert ok.taux_fret == D("160")
    for bad in ("0", "-5", "abc"):
        try:
            validate_simulation_input(**base, taux_fret=bad)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"taux_fret={bad!r} aurait dû être refusé")

    # Paramètres : les 3 taux de fret par défaut existent et sont éditables
    settings_repo = SettingsRepository()
    settings = settings_repo.get_all()
    assert settings["taux_fret_usd"] == "250"
    assert settings["taux_fret_eur"] == "270"
    assert settings["taux_fret_cny"] == "35"
    settings_repo.save({"taux_fret_usd": "180"})
    assert settings_repo.get_all()["taux_fret_usd"] == "180"
    settings_repo.reset_defaults()


def main() -> int:
    tests = [value for key, value in sorted(globals().items()) if key.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"✗ {test.__name__} : {type(exc).__name__}: {exc}")
        else:
            print(f"✓ {test.__name__}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests réussis.")
    return 1 if failures else 0


def test_settings_validation():
    from utils.validators import ValidationError, validate_settings_input

    ok = validate_settings_input(
        taux_change="250", tva="19", douane_le_seuil="15", douane_sup_seuil="30",
        seuil_cylindree="1.8", frais_transitaire="70 000", frais_portuaires="130000",
    )
    assert ok.as_dict()["frais_transitaire"] == "70000"

    base = dict(
        taux_change="250", tva="19", douane_le_seuil="15", douane_sup_seuil="30",
        seuil_cylindree="1.8", frais_transitaire="70000", frais_portuaires="130000",
    )
    for field, value in (
        ("taux_change", "0"), ("taux_change", "-5"), ("tva", "150"),
        ("douane_le_seuil", "-1"), ("douane_sup_seuil", "101"),
        ("seuil_cylindree", "0.05"), ("seuil_cylindree", "25"),
        ("frais_transitaire", "-10"), ("frais_portuaires", "abc"),
    ):
        kwargs = dict(base)
        kwargs[field] = value
        try:
            validate_settings_input(**kwargs)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Paramètre invalide accepté : {field}={value!r}")


def test_exporters():
    import csv as _csv
    import tempfile
    from pathlib import Path as _Path

    from utils.exporter import (
        export_simulations_csv,
        export_simulations_excel,
        simulation_summary_text,
    )

    vehicle = Vehicle("=Danger", "X3 Pro", 2025, D("1.5"))
    sim = Simulation.from_result(
        compute_cost(vehicle, D("7500"), D("1700"), D("250")), date(2026, 8, 12)
    )

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = export_simulations_csv(_Path(tmp) / "out.csv", [sim])
        rows = list(
            _csv.reader(csv_path.read_text(encoding="utf-8-sig").splitlines(), delimiter=";")
        )
        assert rows[0][-1] == "Coût total (DZD)"
        assert rows[1][1] == "'=Danger"  # injection de formule CSV neutralisée
        assert rows[1][-1] == "3347550"

        excel_path = export_simulations_excel(_Path(tmp) / "out.xlsx", [sim])
        assert excel_path.exists() and excel_path.stat().st_size > 1000

    summary = simulation_summary_text(sim)
    assert "Coût total estimé : 3 347 550 DA" in summary
    assert "Taxe véhicule : 0 DA" in summary


def test_taxe_vehicule():
    """Nouvelle case « Taxe véhicule » (v1.1) : éditable et intégrée au total."""
    vehicle = Vehicle("Livan", "X3 Pro", 2025, D("1.5"))

    # Sans taxe (par défaut) : total inchangé
    base = compute_cost(vehicle, D("7500"), D("1700"), D("250"))
    assert base.taxe_vehicule == D("0.00")
    assert base.cout_total == D("3347550.00")

    # Avec taxe : ajoutée telle quelle au coût total
    taxed = compute_cost(vehicle, D("7500"), D("1700"), D("250"),
                         taxe_vehicule=D("45000"))
    assert taxed.taxe_vehicule == D("45000.00")
    assert taxed.cout_total == D("3392550.00")  # 3 347 550 + 45 000

    # Fonction de somme isolée
    total = calculate_total_cost(D("100"), D("100"), D("100"), D("100"),
                                 D("100"), D("100"), D("250"))
    assert total == D("850.00")

    # Persistance : la taxe enregistrée est rechargée telle quelle
    repo = SimulationRepository()
    sim = Simulation.from_result(taxed, date(2026, 8, 27))
    sim_id = repo.save(sim)
    loaded = repo.get(sim_id)
    assert loaded.taxe_vehicule == D("45000.00")
    assert loaded.cout_total == D("3392550.00")


def test_params_editability():
    """Vérification demandée : TOUS les paramètres sont modifiables et appliqués
    aux calculs (taux de change, TVA, douane ≤/> seuil, seuil, frais, taxe)."""
    repo = SettingsRepository()
    vehicle_15 = Vehicle("Livan", "X3 Pro", 2025, D("1.5"))
    vehicle_20 = Vehicle("Kia", "Sportage", 2025, D("2.0"))
    checks = []

    def compute_with(**overrides):
        repo.save(dict(DEFAULT_SETTINGS))  # état propre avant chaque vérification
        repo.save({k: (decimal_to_str(v) if isinstance(v, Decimal) else str(v))
                   for k, v in overrides.items()})
        params = CalculationParams.from_settings(repo.get_all())
        return compute_cost(vehicle_15, D("7500"), D("1700"), D("250"), params)

    # 1) Taux USD/DZD : la conversion suit le taux passé au calcul
    r = compute_cost(vehicle_15, D("7500"), D("1700"), D("300"))
    assert r.prix_dzd == D("2250000.00")
    checks.append("taux_change")

    # 2) TVA 19 % -> 20 %
    r = compute_with(tva=20)
    assert r.tva == D("529000.00")  # 2 645 000 × 20 %
    checks.append("tva")

    # 3) Douane ≤ seuil 15 % -> 22 %
    r = compute_with(douane_le_seuil=22)
    assert r.taux_douane == D("0.22")
    assert r.droits_douane == D("506000.00")  # 2 300 000 × 22 %
    checks.append("douane_le_seuil")

    # 4) Douane > seuil 30 % -> 40 %
    repo.save(dict(DEFAULT_SETTINGS))
    params = CalculationParams.from_settings(repo.get_all())
    r = compute_cost(vehicle_20, D("7500"), D("1700"), D("250"), params)
    assert r.taux_douane == D("0.30")
    r = compute_with(douane_sup_seuil=40)
    assert r.taux_douane == D("0.15")  # le véhicule 1.5 L reste ≤ seuil
    params = CalculationParams.from_settings(repo.get_all())
    r20 = compute_cost(vehicle_20, D("7500"), D("1700"), D("250"), params)
    assert r20.taux_douane == D("0.40")
    assert r20.droits_douane == D("920000.00")  # 2 300 000 × 40 %
    checks.append("douane_sup_seuil")

    # 5) Seuil de cylindrée 1.8 -> 1.4 : le 1.5 L passe dans la tranche haute
    repo.save(dict(DEFAULT_SETTINGS))
    r = compute_with(seuil_cylindree=1.4)
    assert r.taux_douane == D("0.30")
    checks.append("seuil_cylindree")

    # 6) Transitaire 70 000 -> 85 000
    r = compute_with(frais_transitaire=85000)
    assert r.frais_transitaire == D("85000.00")
    checks.append("frais_transitaire")

    # 7) Frais portuaires 130 000 -> 160 000
    r = compute_with(frais_portuaires=160000)
    assert r.frais_portuaires == D("160000.00")
    checks.append("frais_portuaires")

    # 8) Taxe véhicule (défaut) 0 -> 25 000 : la valeur préréglée alimente le
    #    formulaire, qui la transmet au calcul (comme pour l'utilisateur).
    r = compute_with(taxe_vehicule=25000)
    params = CalculationParams.from_settings(repo.get_all())
    assert params.taxe_vehicule_defaut == D("25000.00")
    r = compute_cost(vehicle_15, D("7500"), D("1700"), D("250"), params,
                     taxe_vehicule=params.taxe_vehicule_defaut)
    assert r.taxe_vehicule == D("25000.00")
    assert r.cout_total == D("3347550.00") + D("25000.00")
    checks.append("taxe_vehicule")

    # Retour aux valeurs par défaut
    repo.reset_defaults()
    params = CalculationParams.from_settings(repo.get_all())
    assert params == CalculationParams.defaults()

    print(f"      ({len(checks)} paramètres vérifiés appliqués aux calculs : "
          + ", ".join(checks) + ")")


if __name__ == "__main__":
    raise SystemExit(main())
