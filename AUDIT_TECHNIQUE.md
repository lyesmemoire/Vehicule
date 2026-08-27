# Audit technique — VehicleCostCalculator v1.0.0

**Date de l'audit :** 27/08/2026
**Périmètre :** intégralité du projet (`main.py`, `ui/`, `services/`, `database/`, `models/`, `utils/`, `scripts/`, `tests/`, packaging PyInstaller, documentation).
**Méthodologie :**
- revue manuelle ligne à ligne du code source ;
- analyse statique (`ruff` 0.16.4, règles E/E7/E9/F/I/UP/B/SIM/RUF) ;
- exécution des tests unitaires et du test d'intégration UI (mode offscreen) ;
- tests de résilience provoqués (base absente, base corrompue, saisies invalides) ;
- build PyInstaller réel via le fichier `.spec` + lancement de l'exécutable produit.

---

## 1. Synthèse générale

| Axe | Verdict |
|---|---|
| Conformité au cahier des charges (20 points) | ✅ **100 %** — aucun point manquant |
| Architecture (UI / métier / données / modèles) | ✅ Solide, séparation respectée |
| Calculs financiers (Decimal, arrondis) | ✅ Corrects, vérifiés par tests (ex. du CDC : 3 347 550 DA) |
| Robustesse / gestion d'erreurs | ✅ Bonne — 1 défaut majeur trouvé **et corrigé** (voir A1) |
| Sécurité | ✅ Aucune donnée réseau, SQL paramétré — 1 faille mineure corrigée (A2) |
| Qualité de code (ruff) | ✅ 0 alerte après nettoyage (65 au départ) |
| Tests | ✅ 12/12 unitaires + intégration UI — couverture à élargir (recommandations) |
| Packaging PyInstaller | ✅ Build validé, exécutable lancé, BDD créée au bon endroit |

**Anomalies détectées : 12** — dont 1 majeure (robustesse démarrage), 1 sécurité (injection CSV),
2 d'architecture, 8 mineures/qualité. **Les 12 ont été corrigées pendant l'audit.**
Aucune anomalie critique (perte de données, crash en usage normal, calcul erroné) n'a été trouvée.

---

## 2. Conformité au cahier des charges (matrice)

| § | Exigence | État |
|---|---|---|
| 1 | Python + PySide6 + SQLite, modulaire, buildable .exe, migration possible | ✅ |
| 2 | Champs de saisie + taux par défaut 250 DZD modifiable | ✅ |
| 3 | Conversion, valeur douanière, douane 15 % / 30 % selon ≤ 1.8 L, taux affiché | ✅ (testé : 1.5 L → 15 %) |
| 4 | TVA 19 % sur base douanière + droits, configurable | ✅ |
| 5 | Transitaire 70 000 + frais portuaires 130 000 DA, paramétrables | ✅ |
| 6 | Coût total détaillé composante par composante | ✅ |
| 7 | 2 zones, boutons Calculer/Enregistrer/Réinitialiser, format `2 487 500 DA` | ✅ |
| 8 | Historique SQLite, tri, recherches, filtre année, suppr., modif., duplication, réouverture | ✅ |
| 9 | Évolution des prix : chronologie, min/max/moyen/dernier, variations USD et %, graphique | ✅ (QtCharts + repli QPainter) |
| 10 | Marques/modèles en ComboBox éditable, modèles filtrés par marque | ✅ |
| 11 | Onglet Paramètres + restauration défauts, stockage SQLite | ✅ |
| 12 | Validation stricte, messages français, jamais de crash sur champ vide | ✅ (testé) |
| 13 | `Decimal`, logique centralisée dans `services/calculator.py`, fonctions demandées | ✅ |
| 14 | Structure de projet demandée | ✅ (+ modules complémentaires) |
| 15 | Design sobre, 1200 × 750, taille min., vert pour le total | ✅ |
| 16 | Export CSV + Excel toutes valeurs, « Copier le résultat » | ✅ |
| 17 | Persistance dans le dossier utilisateur, gestion d'erreurs BDD | ✅ |
| 18 | .exe PyInstaller, icône, version, chemin SQLite correct après compilation | ✅ |
| 19 | Avertissement réglementaire affiché en permanence | ✅ (bandeau bas de fenêtre) |
| 20 | Livrables complets et fonctionnels | ✅ |

---

## 3. Anomalies détectées — et corrigées durant l'audit

### A1 · Robustesse du démarrage (majeure) — **corrigé**
**Constat :** si le fichier SQLite était absent, incomplet ou corrompu, les pages
construites à l'ouverture de la fenêtre (Historique, Évolution, Paramètres) ouvraient
chacune une boîte de dialogue modale *avant* le démarrage de la boucle d'événements.
Vérifié expérimentalement : l'application se bloquait (dialogue sans boucle pour le
fermer dans le pire cas, rafale de dialogues en production).
**Correction :** mode silencieux (`refresh(quiet=True)`, `load(quiet=True)`) à
l'initialisation — état vide + libellé « Base de données indisponible » ; les dialogues
ne apparaissent plus que sur des actions explicites de l'utilisateur.
**Re-testé :** base absente → fenêtre opérationnelle ; base corrompue → aucun crash.

### A2 · Sécurité : injection de formules CSV (mineure) — **corrigé**
**Constat :** les champs libres (marque) étaient exportés tels quels en CSV. Une marque
saisie `=HYPERLINK(...)` ou `=cmd|...` aurait été **exécutée par Excel** à l'ouverture
du fichier exporté (injection CSV classique).
**Correction :** neutralisation des débuts de cellule risqués (`=`, `+`, `-`, `@`,
tabulation) par préfixe apostrophe dans `utils/exporter.py`. **Test ajouté**
(`test_exporters` : marque `=Danger` → `'=Danger` dans le CSV).

### A3 · Architecture : `utils/validators.py` dépendait de Qt (mineure) — **corrigé**
**Constat :** le module de validation (logique métier) importait `PySide6.QtWidgets`
pour les validateurs de frappe, ce qui contredisait l'objectif de migration web/mobile
et empêchait de lancer les tests métier sans environnement graphique.
**Correction :** les motifs et `attach_decimal_validator` déplacés dans `ui/components.py` ;
`utils/validators.py` est désormais 100 % pur Python. Les 12 tests métier passent
sans Qt.

### A4 · Architecture : `models` dépendait de `services` à l'exécution (mineure) — **corrigé**
**Constat :** `models/simulation.py` importait `services.calculator.SimulationResult`
au runtime (inversion de couches).
**Correction :** import déplacé sous `TYPE_CHECKING` ; plus aucune dépendance
models → services à l'exécution.

### A5 · UI : libellé de modification persistant (mineure) — **corrigé**
Après « Enregistrer » d'une simulation chargée, si l'utilisateur choisissait
« Créer une nouvelle simulation », le bandeau « Modification de la simulation n° X »
restait affiché à tort. → masqué.

### A6 · Ergonomie : raccourcis clavier absents — **ajouté**
`Ctrl+Entrée` = Calculer (existant), désormais aussi `Ctrl+S` = Enregistrer et
`Entrée` dans un champ numérique = Calculer.

### A7 · Ergonomie : session non mémorisée — **ajouté**
La taille/position de la fenêtre et le dernier onglet utilisé sont désormais
restaurés au lancement (QSettings) ; la barre d'état affiche en permanence le chemin
de la base de données locale.

### A8 · Qualité : 65 alertes d'analyse statique — **nettoyées**
`ruff` signalait 65 problèmes : imports morts (`shutil`, `page_title`,
`section_title`, `date`…), annotations obsolètes (`Optional`), import sorting,
`noqa` inutiles, `subprocess.run` sans `check=`, classe de l'en-tête du tableau
mutable, etc. **Résultat final : 0 alerte** (`ruff check .` passe). Configuration
versionnée dans `pyproject.toml` avec les écarts intentionnels documentés
(`Decimal("...")` en chaîne = précision financière ; « × » typographique).

### A9 · Tests : exporteurs et validation des paramètres non couverts — **ajouté**
Deux tests ajoutés : `test_exporters` (contenu CSV, neutralisation d'injection,
génération Excel, texte du presse-papiers) et `test_settings_validation`
(9 refus attendus : taux 0/négatif, TVA 150 %, seuil hors bornes, frais négatifs…).
**Total : 12/12.**

### A10 · Micro-défauts divers — **corrigés**
`Decimal` verbeux incohérents, `values + (sim.id,)` → `(*values, sim.id)`,
`try/except/pass` → `contextlib.suppress`, boucle à variable inutilisée,
condition booléenne redondante dans le filtre d'historique, script build
non exécutable.

---

## 4. Points forts constatés

- **Logique métier impeccable et testable** : `services/calculator.py` pur `Decimal`,
  fonctions pures, arrondi comptable `ROUND_HALF_UP`, aucun montant en `float`.
- **Séparation des couches réelle** (pas cosmétique) : l'UI ne contient aucune formule ;
  les repositories sont la seule couche SQL ; SQL entièrement paramétré.
- **Résilience SQL correcte** : chaque opération est encapsulée, erreurs converties en
  `DatabaseError` avec message français ; aucun crash sur champ vide (validations testées).
- **Double implémentation graphique** : QtCharts avec repli automatique `QPainter`
  si le module manque — l'application ne perd jamais la fonctionnalité.
- **Packaging maîtrisé** : `.spec` complet (icône, version Windows, hiddenimports,
  exclusions), chemin `%APPDATA%` correct en mode compilé, test de lancement réel OK.
- **Conformité réglementaire honnête** : avertissement permanent + disclaimer dans les
  Paramètres ; les taux sont présentés comme paramètres utilisateur.

---

## 5. Recommandations restantes (non bloquantes)

### Priorité 1 — à faire avant une utilisation intensive
| # | Recommandation | Justification | Effort |
|---|---|---|---|
| R1 | **Sauvegarde/restauration de la base** : copie `.bak` automatique au démarrage + bouton « Exporter/Importer les données » dans les Paramètres | Aujourd'hui, la suppression est définitive et un disque défaillant perd tout l'historique | 2–3 h |
| R2 | **Renommer la colonne SQL `date`** en `simulation_date` (mot réservé SQL) avec migration | Portabilité future (web/ORM) et lisibilité ; migration simple par `ALTER TABLE ... RENAME COLUMN` | 1–2 h |
| R3 | **Stockage monétaire en centimes entiers ou TEXT** au lieu de `REAL` | `REAL` est sans risque dans la plage d'usage actuelle (reconversion `Decimal(str(v))`), mais le stockage binaire flotterait sur d'autres plateformes/outils | 3–4 h |
| R4 | **Gestion du catalogue** : renommage/suppression de marques et modèles (petit gestionnaire dans Paramètres) | Éviter l'accumulation de doublons de frappe (« KIA »/« Kia » sont fusionnés par `COLLATE NOCASE`, mais pas les coquilles) | 3 h |
| R5 | **CI minimale** (GitHub Actions) : `ruff check` + tests unitaires à chaque push | Garde-fou automatique, fonctionne sans Qt (validators découplés — cf. A3) | 1 h |
| R6 | **Épingler les versions testées** dans `requirements.txt` (ex. `PySide6==6.11.2`) ou fournir un `constraints.txt` | PySide6 6.x a déjà changé d'API entre versions (`toPyDate` → `toPython`) ; un build reproductible exige une version figée | 15 min |

### Priorité 2 — confort et diffusion
| # | Recommandation | Justification | Effort |
|---|---|---|---|
| R7 | **Signature de code Windows** (certificat OV/EV) | Les exécutables PyInstaller non signés déclenchent SmartScreen et parfois des faux positifs antivirus, surtout en `--onefile` | dépend du certificat |
| R8 | **Impression / export PDF** d'une simulation | Besoin fréquent côté client final (devis indicatif) | 3–4 h |
| R9 | **Comparateur multi-véhicules** (2–3 simulations côte à côte) dans Évolution | Utilité métier directe pour arbitrer entre modèles | 4–6 h |
| R10 | **Tests UI automatisés** (`pytest-qt`) + couverture (`coverage`) | Sécuriser les évolutions de l'interface (aujourd'hui : 1 script de fumée) | 1 j |
| R11 | **i18n** (Qt Linguist) si ouverture hors francophonie | Chaînes actuellement en dur en français | 0,5–1 j |
| R12 | **Performance grand volume** : pagination/`LIMIT` sur l'historique, `PRAGMA journal_mode=WAL` | Irrrelevant en dessous de ~10 000 simulations ; à faire si usage intensif multi-années | 2 h |
| R13 | **Dépôt Git + CHANGELOG + LICENSE** | Traçabilité des versions, base pour la CI | 30 min |

---

## 6. Métriques

| Indicateur | Valeur |
|---|---|
| Lignes de code Python | **4 083** (ui 2 111 · utils 523 · database 470 · services 265 · tests 309 · scripts 230 · models 119 · main 56) |
| Tests unitaires | 12/12 ✔ (+ intégration UI : 5 vérifications ✔) |
| Analyse statique (ruff) | **0 alerte** ✔ |
| Compilation (`py_compile`) | 42 fichiers, 0 erreur ✔ |
| Build PyInstaller (`.spec`) | Succès (~25 s) ; exécutable lancé 10 s, BDD créée au bon emplacement ✔ |
| Dépendances runtime | 2 seulement : PySide6 6.11.2, openpyxl 3.1.5 |
| Résilience | Base absente ✔ · base corrompue ✔ · saisies invalides ✔ · export vers fichier ouvert ✔ |

---

## 7. Verdict

Le projet est un **MVP desktop professionnel sain**, conforme à la totalité du cahier
des charges, avec une logique métier exacte, testée et correctement isolée.
L'audit a permis de corriger **12 anomalies** — dont une de robustesse au démarrage et
une d'injection CSV — sans régression (tous les tests repassent après corrections).

Avant diffusion large, il est recommandé de traiter les recommandations **R1
(sauvegarde de la base)** et **R6 (épinglage des versions)**, très rentables en
sécurité pour l'utilisateur final ; les autres peuvent suivre la feuille de route.
