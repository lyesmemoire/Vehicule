# Guide de développement & maintenance — VehicleCostCalculator

Ce document explique **comment faire évoluer l'application** : ajouter une composante
de coût, un paramètre, un écran, faire évoluer la base de données, livrer une
nouvelle version. Il est écrit pour être suivi **sans connaissance préalable du code**.

---

## 1. Prendre en main le projet

### 1.1 Installation de l'environnement (une fois)

```bat
:: Python 3.12+ requis
cd vehicle_cost_app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   :: dépendances app + outils (ruff, pyinstaller)
```

### 1.2 Commandes quotidiennes — `scripts/dev.py`

Tout passe par un point d'entrée unique :

| Commande | Effet |
|---|---|
| `python scripts/dev.py run` | Lance l'application |
| `python scripts/dev.py test` | Tests de la logique métier (rapide, sans interface) |
| `python scripts/dev.py ui-test` | Test d'intégration de l'UI + captures dans `docs/` (mode offscreen) |
| `python scripts/dev.py lint` | Analyse statique (ruff) |
| `python scripts/dev.py check` | lint + tests + test d'intégration — **à lancer avant chaque livraison** |
| `python scripts/dev.py catalog` | Rafraîchit le catalogue marques/modèles (Internet requis) |
| `python scripts/dev.py build` | Construit l'exécutable Windows (PyInstaller) |
| `python scripts/dev.py version` | Affiche la version courante |

### 1.3 Architecture et règles de dépendance

```
main.py ──► ui/ ──► services/ ──► models/
   │          │  └──► database/ ──► models/
   │          └──► utils/
   └──► database/ (initialisation)
```

**Règles strictes (à respecter pour garder le projet sain) :**

1. **Aucune formule financière dans `ui/`** : toute la logique est dans
   `services/calculator.py` (fonctions pures, `Decimal` uniquement, arrondi
   `ROUND_HALF_UP` au centime via `_q2()`).
2. **Aucun accès SQL hors de `database/repositories.py`** ; les erreurs SQLite sont
   toujours converties en `database.db.DatabaseError` avec un message français.
3. **`models/`, `services/`, `database/`, `utils/` n'importent jamais PySide6**
   (c'est ce qui permet les tests sans écran, la CI sans Qt et une future version
   web/mobile). Seule exception utilitaire : `utils/paths.py` (détection PyInstaller).
4. **La validation se fait à deux niveaux** : frappe contrôlée dans l'UI
   (`ui/components.py`, motifs regex) + contrôle métier complet dans
   `utils/validators.py` (pur Python, messages d'erreur en français).
5. **Tous les textes visibles sont en français** ; les montants sont formatés via
   `utils/currency.py` uniquement (`format_dzd`, `format_usd`, `format_number`).

### 1.4 Où est quoi ?

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée : QApplication, style, init base, fenêtre. `APP_VERSION` ici. |
| `ui/main_window.py` | Onglets, câblage inter-pages, avertissement, mémorisation fenêtre |
| `ui/calculator_page.py` | Formulaire + panneau résultat du Calculateur |
| `ui/history_page.py` | Tableau Historique (modèle/vue Qt + filtres) |
| `ui/price_history_page.py` | Évolution des prix (graphique QtCharts, repli `simple_chart.py`) |
| `ui/settings_page.py` | Onglet Paramètres |
| `services/calculator.py` | **Toutes** les formules + `DEFAULT_SETTINGS` + `CalculationParams` |
| `services/price_history.py` | Statistiques d'évolution (min/max/moyenne/variations) |
| `services/vehicle_catalog.py` | Fusion catalogue embarqué ↔ marques/modèles utilisateur |
| `database/db.py` | Connexion, schéma, **migrations**, dossier de données (`%APPDATA%`) |
| `database/repositories.py` | Requêtes (simulations, paramètres, catalogue) |
| `models/vehicle.py`, `models/simulation.py` | Structures de données métier |
| `utils/currency.py` | Formatage/analyse des nombres (« 1 450 000 DA », « 1,5 ») |
| `utils/validators.py` | Validation des saisies et des paramètres |
| `utils/exporter.py` | CSV / Excel / résumé presse-papiers (avec anti-injection) |
| `assets/data/brands_models.json` | Catalogue véhicules embarqué (généré, ne pas éditer à la main) |
| `tests/test_calculator.py` | 15 tests métier (s'exécutent sans Qt) |

---

## 2. Recettes d'évolution

### Recette A — Ajouter une composante de coût (exemple réel : la Taxe véhicule, v1.1)

Suivre les 8 étapes dans l'ordre — chaque étape est petite et testable :

1. **`services/calculator.py`**
   - Ajouter la valeur par défaut dans `DEFAULT_SETTINGS` (ex. `"taxe_vehicule": "0"`).
   - Ajouter le champ dans `CalculationParams` (et dans `from_settings`) **si** la
     composante a un préréglage ; l'ajouter à `SimulationResult`.
   - Étendre `calculate_total_cost()` et `compute_cost()` avec le nouveau paramètre.
2. **`models/simulation.py`** : ajouter le champ `taxe_vehicule: Decimal` + mapping
   dans `from_result()`.
3. **`database/db.py`** : colonne dans `SCHEMA` (pour les nouvelles bases) **et**
   entrée dans `MIGRATIONS` (pour les bases existantes — la migration est appliquée
   automatiquement au démarrage) :
   ```python
   ("simulations", "taxe_vehicule",
    "ALTER TABLE simulations ADD COLUMN taxe_vehicule REAL NOT NULL DEFAULT 0"),
   ```
4. **`database/repositories.py`** : colonne dans `_COLUMNS`, dans les `values` de
   `save()` et dans `_row_to_simulation()`.
5. **`utils/validators.py`** : paramètre optionnel dans `validate_simulation_input`
   (vide = 0, refus des négatifs) avec message français.
6. **`ui/calculator_page.py`** : le `QLineEdit` du formulaire, la ligne dans
   `_RESULT_ROWS` (elle s'affichera automatiquement), branchement dans
   `_collect_inputs()`, `reset_clicked()`, `on_settings_changed()` et `load_for_edit()`.
7. **`utils/exporter.py`** : colonne dans `HEADERS`, `_row_from_sim()`,
   `simulation_summary_text()` (et largeur Excel).
8. **Tests** (`tests/test_calculator.py`) : nouveau `test_xxx` vérifiant le calcul
   avec et sans la composante, et la persistance. Puis `python scripts/dev.py check`.

> La réplique web `docs/apercu_interactif.html` est un livrable de démonstration :
> si vous la maintenez, répercuter la même composante dans `compute()` et le HTML.

### Recette B — Ajouter un paramètre dans l'onglet Paramètres

1. `services/calculator.py` : entrée dans `DEFAULT_SETTINGS` (+ champ `CalculationParams`).
2. `ui/settings_page.py` : une ligne dans la liste `_FIELDS`
   `(clé, libellé, unité, exemple, motif)` — c'est tout, la page se construit seule.
3. `utils/validators.py` : règle de validation dans `validate_settings_input`.
4. Test : ajouter le paramètre à `test_params_editability` (il vérifie que la
   modification est bien appliquée au calcul).

### Recette C — Modifier une règle de calcul (ex. tranches de douane multiples)

Tout se passe dans `services/calculator.py` : remplacer `calculate_customs_rate()`
par la nouvelle logique (table de tranches, paramètres supplémentaires dans
`CalculationParams`…). L'UI, la base et les exports n'ont **rien** à changer :
ils consomment `SimulationResult`. Ajouter/mettre à jour les tests correspondants.

### Recette D — Faire évoluer le schéma SQLite

Ajouter une entrée dans `MIGRATIONS` (`database/db.py`) : tuple
`(table, colonne, ALTER TABLE ...)`. La migration s'applique seule au premier
démarrage de la nouvelle version. Pour des changements structurants (renommage de
table, changement de type), écrire une fonction de migration par version dans
`db.py` et l'appeler dans `init_database()` — et **incrémenter la version dans le
CHANGELOG**.

### Recette E — Rafraîchir le catalogue véhicules

```bat
python scripts/dev.py catalog
```
Éditer `scripts/update_vehicle_catalog.py` pour ajouter/retirer des marques
(dictionnaire `BRANDS`) ou des modèles du complément algérien (`SUPPLEMENT`).
Le fichier `assets/data/brands_models.json` est embarqué dans l'exécutable
(déjà configuré dans le `.spec` et le script de build).

### Recette F — Ajouter un écran/onglet

1. Créer `ui/nouvelle_page.py` (s'inspirer de `settings_page.py` : `QWidget` +
   `Panel` + composants de `ui/components.py`).
2. L'instancier dans `ui/main_window.py` et `self.tabs.addTab(...)`.
3. Si la page doit réagir à un enregistrement, la brancher sur
   `simulation_saved` / `_refresh_data_pages()`.

---

## 3. Versionner et livrer

### 3.1 Checklist de livraison

1. Mettre à jour `APP_VERSION` dans **4 fichiers** :
   `main.py`, `scripts/build_windows.py`, `assets/version_info.txt` (2 lignes),
   et l'en-tête de `docs/apercu_interactif.html` (aperçu web).
2. Ajouter une entrée dans `CHANGELOG.md` (Ajouts / Modifiés / Corrigés / Supprimés).
3. `python scripts/dev.py check` → tout doit être vert (lint + tests + UI).
4. `python scripts/dev.py build` → tester `dist\VehicleCostCalculator\…exe` sur un
   PC Windows **sans Python** *(ou laisser la CI le faire, étape 6)*.
5. Reconstruire l'archive de diffusion (ZIP du dossier projet sans `__pycache__`).
6. **Publication automatique** : pousser un tag — la CI GitHub construit l'exécutable
   sur Windows et crée la Release avec le `.zip` + SHA-256 :
   ```bat
   git tag v1.3.1
   git push origin main --tags
   ```
   (le tag doit être identique à `APP_VERSION`, sinon le build échoue — garde-fou
   intentionnel ; voir `.github/workflows/release.yml`).

### 3.2 Git (recommandé)

Le projet contient déjà le `.gitignore` adapté (exclut `build/`, `dist/`,
`__pycache__/`, `.venv/`). Sur votre machine :

```bat
cd vehicle_cost_app
git init
git add .
git commit -m "v1.2.0 : rubans marque/modèle + catalogue téléchargé"
:: puis, si vous créez un dépôt distant :
git remote add origin <url> && git push -u origin master
```

La CI GitHub Actions (`.github/workflows/ci.yml`) est prête : à chaque push, elle
lance `ruff check` et les tests métier **sans Qt** (grâce au découplage).

---

## 4. Tests et qualité

- **Structure** : un test = une fonction `test_xxx` dans
  `tests/test_calculator.py` (lanceur intégré, compatible `pytest` aussi).
  L'isolation est assurée par `VEHICLE_COST_DATA_DIR` (base temporaire).
- **Ajouter un test** : écrire la fonction, elle est découverte automatiquement.
  S'appuyer sur `test_taxe_vehicule` (calcul + persistance) et
  `test_params_editability` (application des paramètres).
- **Test d'UI** : `scripts/generate_screenshots.py` pilote la vraie fenêtre en
  mode offscreen et échoue si un flux se casse — il sert aussi à régénérer les
  captures du README.
- **Lint** : configuration dans `pyproject.toml`. Les écarts intentionnels y sont
  documentés (typographie française `×`/«», `Decimal("...")` obligatoire pour la
  précision). Ne pas désactiver de règle dans le code sans justification ici.

## 5. Feuille de route suggérée

Issues classées du plus rentable (voir `AUDIT_TECHNIQUE.md` §5 pour le détail) :

1. ~~Sauvegarde/restauration de la base~~ → **livré en v1.3.0**.
2. Renommage de la colonne SQL `date` → `simulation_date` (mot réservé).
3. Stockage monétaire en centimes entiers (portabilité maximale).
4. Gestion du catalogue utilisateur (renommage/suppression marques/modèles).
5. Export PDF / impression d'une simulation.
6. Comparateur multi-véhicules dans l'onglet Évolution.
7. Tests UI `pytest-qt` + couverture ; signature de code Windows ; i18n.
8. Alertes prix cible dans l'onglet Évolution ; notes + frais divers par simulation.
9. Vrai installateur Windows (Inno Setup) en complément du `.zip` de Release.

## 6. Migration future web / mobile

Le découplage est déjà en place : `services/` (formules), `models/`, `database/`
(SQLite ↔ remplacable par une API) et `utils/` (validation, formatage, exports)
sont **purs Python, sans Qt**. Une version web peut les réutiliser tels quels
(FastAPI/Flask côté serveur) en ne réécrivant que la couche `ui/`.
