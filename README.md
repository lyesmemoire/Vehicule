# VehicleCostCalculator — Calculateur de coût de revient (véhicules importés en Algérie)

Application **desktop Windows** (extensible macOS/Linux), **hors ligne**, légère et autonome,
qui estime le coût total rendu en Algérie d'un véhicule importé :

```
Prix véhicule DZD + Fret DZD + Droits de douane + TVA + Transitaire
+ Frais portuaires + Taxe véhicule
```

- Interface française (PySide6 / Qt for Python)
- Calculs financiers en `Decimal` (arrondi comptable au centime)
- Historique local **SQLite** (créé automatiquement au premier démarrage)
- Suivi de l'évolution des prix d'un même véhicule avec graphique
- Export CSV / Excel + copie du résultat dans le presse-papiers
- Paramètres de calcul modifiables (taux, frais fixes) stockés en base

---

## 1. Installation (mode développement)

Prérequis : **Python 3.12+** (testé de 3.12 à 3.13).

```bat
cd vehicle_cost_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> Sous Windows, PySide6 embarque toutes les bibliothèques nécessaires : rien d'autre à installer.
> Sur Linux, les paquets système usuels de Qt peuvent être requis
> (`libxkbcommon0`, `libfontconfig1`, `libgl1`, …).

## 2. Lancement

```bat
python main.py
```

Au premier démarrage, la base SQLite est créée automatiquement dans le dossier
utilisateur (jamais dans `Program Files`) :

| OS      | Emplacement de la base                                          |
|---------|-----------------------------------------------------------------|
| Windows | `%APPDATA%\VehicleCostCalculator\vehicle_costs.db`              |
| macOS   | `~/Library/Application Support/VehicleCostCalculator/`          |
| Linux   | `~/.local/share/VehicleCostCalculator/`                         |

> Mode portable / tests : définir la variable d'environnement `VEHICLE_COST_DATA_DIR`
> pour choisir le dossier de données.

> **Catalogue véhicules** : la liste des marques/modèles (58 marques, 2 400+ modèles)
> est embarquée dans l'application — aucune connexion requise à l'usage. Pour la
> rafraîchir ponctuellement : `python scripts/update_vehicle_catalog.py` (Internet
> nécessaire uniquement à ce moment-là).

## 3. Construire l'exécutable Windows (`VehicleCostCalculator.exe`)

À faire **sur une machine Windows** (PyInstaller ne croise pas les plateformes) :

```bat
pip install -r requirements.txt pyinstaller

:: méthode simple (script dédié)
python scripts\build_windows.py

:: ou directement via le fichier .spec fourni
pyinstaller VehicleCostCalculator.spec

:: variante fichier unique
python scripts\build_windows.py --onefile
```

Résultat : `dist\VehicleCostCalculator\VehicleCostCalculator.exe`
(dossier autonome à copier tel quel sur n'importe quel PC Windows — **aucun Python requis**).

- Icône : `assets/icons/app.ico`
- Informations de version Windows : `assets/version_info.txt`
- Le chemin SQLite après compilation reste le dossier `%APPDATA%` de l'utilisateur (voir §2).

## 4. Utilisation

### Onglet « Calculateur »
1. Saisir marque, modèle, année, cylindrée (L), prix véhicule (USD), fret (USD).
   Les champs **Marque** et **Modèle** sont des rubans déroulants alimentés par un
   catalogue embarqué de **58 marques / 2 400+ modèles** (API NHTSA + complément
   marché algérien : Livan, Dacia, Jetour, Chery…), avec recherche instantanée.
   La saisie libre reste possible ; toute nouvelle marque/modèle est mémorisée
   et proposée à nouveau ensuite.
2. Le taux USD/DZD est pré-rempli avec la valeur des paramètres (défaut : **250**), modifiable.
3. Cliquer sur **Calculer** : le détail complet s'affiche à droite
   (valeur douanière, taux douanier appliqué, droits, TVA, frais fixes) et le
   **COÛT TOTAL ESTIMÉ** en vert.
4. **Enregistrer** conserve la simulation dans l'historique ; **Réinitialiser** vide le formulaire.
5. Boutons **Copier le résultat**, **Export CSV**, **Export Excel** pour la simulation affichée.

Le calcul se met à jour automatiquement (et silencieusement) quand un champ change
après un premier calcul.

Raccourcis clavier : **Ctrl+Entrée** = calculer, **Ctrl+S** = enregistrer,
**Entrée** dans un champ numérique = calculer. La géométrie de la fenêtre et le
dernier onglet utilisé sont mémorisés d'une session à l'autre ; la barre d'état
rappelle l'emplacement de la base de données.

### Règles de calcul (paramétrables)

| Élément | Valeur par défaut |
|---|---|
| Conversion | `montant USD × taux USD/DZD` |
| Valeur douanière | `prix véhicule DZD + fret DZD` |
| Droits de douane | `15 %` si cylindrée ≤ **1.8 L**, sinon `30 %` |
| TVA | `19 %` × (valeur douanière + droits) |
| Transitaire | `70 000 DZD` |
| Frais portuaires | `130 000 DZD` |
| Taxe véhicule (v1.1) | `0 DZD` — **éditable dans le formulaire** pour chaque simulation, et préréglable dans les Paramètres |

Exemple (Livan X3 Pro 2025, 1.5 L, 7 500 USD, fret 1 700 USD, taux 250) :
coût total = **3 347 550 DA**.

### Onglet « Historique »
- Tri par colonne (clic sur l'en-tête), recherche par marque / modèle, filtre par année.
- **Ouvrir / Modifier** (ou double-clic) : recharge la simulation dans le calculateur ;
  l'enregistrement propose alors *mettre à jour* ou *créer une nouvelle simulation*.
- **Dupliquer** : copie avec la date du jour.
- **Supprimer** : avec confirmation.
- **Export CSV / Excel** des lignes actuellement filtrées.

### Onglet « Évolution des prix »
Choisir marque + modèle + année : historique chronologique, graphique d'évolution
du prix (QtCharts, avec repli automatique sur un canvas interne si QtCharts est absent),
et statistiques : premier / dernier prix, variation USD et %, minimum, maximum, moyen.

### Onglet « Paramètres »
Taux USD/DZD, TVA, taux de douane (≤ seuil / > seuil), seuil de cylindrée,
transitaire, frais portuaires, **taxe véhicule (valeur par défaut du formulaire)**.
Bouton **Restaurer les valeurs par défaut**.
Les paramètres sont stockés en SQLite et appliqués immédiatement au calculateur.

## 5. Tests

```bat
python tests\test_calculator.py          :: 14 tests de la logique métier (sans Qt),
                                         :: dont l'éditabilité des 8 paramètres
python scripts\generate_screenshots.py   :: test d'intégration de l'UI (mode offscreen)

pip install ruff && ruff check .         :: analyse statique — 0 alerte
```

## 6. Architecture

```
vehicle_cost_app/
├── main.py                     # point d'entrée (QApplication, init BDD, style)
├── requirements.txt
├── pyproject.toml              # configuration de l'analyse statique (ruff)
├── VehicleCostCalculator.spec  # build PyInstaller
├── ui/
│   ├── main_window.py          # fenêtre principale + onglets + avertissement
│   ├── calculator_page.py      # saisie + résultat du calcul
│   ├── history_page.py         # tableau de l'historique (modèle/vue + filtres)
│   ├── price_history_page.py   # évolution des prix + graphique
│   ├── settings_page.py        # paramètres de calcul
│   ├── simple_chart.py         # graphe de secours (QPainter, sans QtCharts)
│   ├── components.py           # panneaux, titres, helpers
│   └── styles.py               # feuille de style globale (QSS)
├── services/
│   ├── calculator.py           # TOUTE la logique financière (Decimal)
│   ├── vehicle_catalog.py      # catalogue embarqué marques/modèles (fusion base)
│   └── price_history.py        # statistiques d'évolution
├── database/
│   ├── db.py                   # connexion, schéma, migration légère, dossier userData
│   └── repositories.py         # simulations, paramètres, catalogue marques/modèles
├── models/
│   ├── vehicle.py              # véhicule (marque, modèle, année, cylindrée)
│   └── simulation.py           # ligne de simulation persistée
├── utils/
│   ├── currency.py             # formatage/analyse « 1 450 000 DA », « 1,5 »
│   ├── validators.py           # validation + messages d'erreur français
│   ├── exporter.py             # CSV / Excel / résumé presse-papiers
│   └── paths.py                # chemins de ressources (mode compilé PyInstaller)
├── scripts/
│   ├── build_windows.py        # build PyInstaller en une commande
│   ├── update_vehicle_catalog.py  # (re)télécharge le catalogue marques/modèles
│   └── generate_screenshots.py # test d'intégration UI + captures
├── tests/
│   └── test_calculator.py
├── assets/
│   ├── icons/                  # icônes (app.ico, app.png, flèches QSS)
│   └── data/brands_models.json # 58 marques / 2 400+ modèles (NHTSA + complément)
```

Principes :
- **Interface / logique métier / données** strictement séparées : les formules ne vivent
  que dans `services/calculator.py` (`calculate_customs_rate`, `calculate_customs_duty`,
  `calculate_vat`, `calculate_total_cost`, `compute_cost`), ce qui permet de faire évoluer
  les règles sans toucher à l'UI, voire de migrer vers le web/mobile en réutilisant
  `services`, `models`, `database` et `utils` tels quels (la validation de
  `utils/validators.py` est volontairement **sans dépendance Qt**).
- Montants manipulés en `Decimal`, arrondis comptables au centime (`ROUND_HALF_UP`).
- La base SQLite n'utilise `REAL` que pour le stockage ; les valeurs sont reconverties
  en `Decimal` via `Decimal(str(valeur))` sans perte d'affichage.
- Toutes les erreurs de base de données sont interceptées et affichées proprement
  (aucun crash) ; à l'ouverture de la fenêtre, les erreurs sont traitées en mode
  silencieux (état vide) pour ne jamais bloquer le démarrage.

## 7. Maintenir et faire évoluer l'application

Le projet est préparé pour les évolutions futures :

| Ressource | Contenu |
|---|---|
| **`docs/DEVELOPPEMENT.md`** | Guide complet : architecture, règles de dépendance, **recettes pas-à-pas** (ajouter une composante de coût, un paramètre, un écran, faire évoluer la base…), checklist de livraison, feuille de route |
| **`scripts/dev.py`** | Point d'entrée unique : `run`, `test`, `ui-test`, `lint`, `check`, `catalog`, `build`, `version` |
| **`CHANGELOG.md`** | Historique des versions (tenir à jour à chaque livraison) |
| **`.github/workflows/ci.yml`** | CI GitHub Actions prête (ruff + tests, sans Qt) |
| **`requirements-dev.txt`** | Outils de développement (ruff, pyinstaller) |
| **`AUDIT_TECHNIQUE.md`** | État des lieux + recommandations priorisées (R1–R13) |

Exemple — vérifier l'intégralité du projet en une commande :

```bat
python scripts\dev.py check
```

Le code est volontairement découplé (interface / métier / données / utilitaires,
sans Qt dans la logique) : les règles de calcul se modifient dans un seul fichier
(`services/calculator.py`), et la couche métier est réutilisable telle quelle pour
une future version web ou mobile.

## 8. Avertissement

Les taux présents dans cette application sont des **paramètres de calcul définis par
l'utilisateur** et non une garantie de conformité réglementaire. *Les résultats sont des
estimations. Les droits, taxes, valeurs douanières et autres frais doivent être vérifiés
auprès des autorités et professionnels compétents avant toute opération d'importation.*
