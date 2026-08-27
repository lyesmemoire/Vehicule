# Journal des versions — VehicleCostCalculator

Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ;
versionnement [sémantique](https://semver.org/lang/fr/) : `MAJEUR.MINEUR.CORRECTIF`.

## [1.2.0] — 2026-08-27

### Ajouts
- **Rubans Marque / Modèle** : listes déroulantes arrondies avec recherche instantanée,
  alimentées par un catalogue embarqué **58 marques / 2 413 modèles** téléchargé
  depuis l'API NHTSA vPIC et enrichi du marché algérien (Livan, Dacia, Jetour,
  Haval, Omoda…). Script de rafraîchissement : `scripts/update_vehicle_catalog.py`.
- **Harmonisation de l'Historique** : tous les montants du tableau affichés avec
  2 décimales (`8 200,00 USD`, `250,00`, `3 415 975,25 DA`).
- **Outils de maintenance** : `scripts/dev.py` (test/lint/run/build/catalog/check),
  `docs/DEVELOPPEMENT.md` (guide complet), `CHANGELOG.md`, CI GitHub Actions,
  `requirements-dev.txt`.

## [1.1.0] — 2026-08-27

### Ajouts
- **Taxe véhicule** éditable : case dans le formulaire (par simulation) + valeur
  par défaut dans les Paramètres ; intégrée au coût total, à l'historique,
  aux exports et au résumé presse-papiers. Migration SQLite automatique
  (colonne `taxe_vehicule`).
- Test `test_params_editability` : vérifie que les **8 paramètres** (taux de change,
  TVA, douane ≤/> seuil, seuil, transitaire, frais portuaires, taxe) sont bien
  modifiables et appliqués aux calculs.

## [1.0.1] — 2026-08-27

### Corrigé / durci (audit technique)
- Démarrage résilient : plus aucun dialogue modal bloquant si la base SQLite est
  absente ou corrompue (mode silencieux à l'ouverture).
- Sécurité : neutralisation de l'injection de formules CSV (`=`, `+`, `-`, `@`).
- Architecture : `utils/validators.py` et `models/` sans dépendance Qt/services
  à l'exécution (réutilisables pour une version web/mobile).
- 65 alertes d'analyse statique corrigées (0 aujourd'hui) ; configuration `pyproject.toml`.
- Ergonomie : raccourcis Ctrl+S / Entrée, géométrie de fenêtre et dernier onglet
  mémorisés, barre d'état avec chemin de la base.

## [1.0.0] — 2026-08-27

### Version initiale
- Calcul du coût de revient complet (conversion, valeur douanière, droits de
  douane 15 %/30 % selon ≤ 1.8 L, TVA 19 %, transitaire, frais portuaires),
  montants en `Decimal`.
- Historique SQLite (tri, filtres, recherche, modification, duplication,
  suppression, export CSV/Excel), Évolution des prix avec graphique QtCharts,
  Paramètres restaurables, interface française PySide6, build PyInstaller.
