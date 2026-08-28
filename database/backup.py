"""Sauvegarde et restauration de la base SQLite locale.

Les sauvegardes sont stockées dans un sous-dossier ``backups/`` du dossier
de données utilisateur. Deux catégories :

- **automatiques** (suffixe ``_auto``) : créées au démarrage de l'application,
  purgées au-delà de :data:`MAX_AUTO_BACKUPS` ;
- **manuelles** : créées depuis l'onglet Paramètres, jamais purgées
  automatiquement (suffixe ``_avant_restauration`` pour la copie de sécurité
  réalisée juste avant une restauration).
"""

from __future__ import annotations

import contextlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from database.db import DatabaseError, connect, get_data_dir, get_db_path

BACKUP_DIR_NAME = "backups"
MAX_AUTO_BACKUPS = 10
_SQLITE_HEADER = b"SQLite format 3\x00"


def backup_dir() -> Path:
    """Dossier contenant les sauvegardes."""
    return get_data_dir() / BACKUP_DIR_NAME


def create_backup(reason: str = "manual") -> Path:
    """Sauvegarde la base courante, renvoie le chemin de la copie.

    Utilise l'API de sauvegarde SQLite (cohérente même si la base est ouverte
    ailleurs). ``reason`` : ``manual``, ``auto`` ou ``pre_restore``.
    """
    source = get_db_path()
    if not source.exists():
        raise DatabaseError("Aucune base de données à sauvegarder.")
    try:
        backup_dir().mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = {"auto": "_auto", "pre_restore": "_avant_restauration"}.get(reason, "")
        destination = backup_dir() / f"vehicle_costs_{stamp}{suffix}.bak"

        source_conn = sqlite3.connect(source)
        target_conn = sqlite3.connect(destination)
        try:
            source_conn.backup(target_conn)
        finally:
            source_conn.close()
            target_conn.close()
        return destination
    except sqlite3.Error as exc:
        raise DatabaseError(f"Échec de la sauvegarde : {exc}") from exc
    except OSError as exc:
        raise DatabaseError(f"Impossible d'écrire la sauvegarde : {exc}") from exc


def list_backups() -> list[Path]:
    """Liste les fichiers de sauvegarde (du plus récent au plus ancien)."""
    if not backup_dir().exists():
        return []
    files = [p for p in backup_dir().iterdir() if p.suffix in {".bak", ".db"}]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def prune_auto_backups(keep: int = MAX_AUTO_BACKUPS) -> None:
    """Supprime les sauvegardes automatiques excédentaires (les plus anciennes)."""
    autos = [p for p in list_backups() if p.stem.endswith("_auto")]
    for old in autos[keep:]:
        with contextlib.suppress(OSError):
            old.unlink()  # un fichier verrouillé ne doit pas bloquer le démarrage


def _validate_backup_file(path: Path) -> None:
    """Vérifie qu'un fichier est bien une base SQLite exploitable."""
    if not path.exists():
        raise DatabaseError(f"Fichier introuvable : {path}")
    try:
        with open(path, "rb") as handle:
            if handle.read(16) != _SQLITE_HEADER:
                raise DatabaseError(
                    "Ce fichier n'est pas une base de données valide.\n"
                    "Choisissez un fichier de sauvegarde créé par l'application."
                )
        conn = sqlite3.connect(path)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        if not result or result[0] != "ok":
            raise DatabaseError("La sauvegarde choisie est endommagée (intégrité).")
        if "simulations" not in tables:
            raise DatabaseError(
                "Ce fichier ne correspond pas à une base de l'application."
            )
    except sqlite3.Error as exc:
        raise DatabaseError(f"Sauvegarde illisible : {exc}") from exc


def restore_backup(path: str | Path) -> Path:
    """Restaure une sauvegarde en remplaçant la base courante.

    Une copie de sécurité de la base actuelle est créée avant l'opération
    (suffixe ``_avant_restauration``, jamais purgée automatiquement).
    Renvoie le chemin de la base restaurée.
    """
    source = Path(path)
    _validate_backup_file(source)

    # Copie de sécurité de l'état actuel (meilleure pratique avant écrasement)
    if get_db_path().exists():
        create_backup("pre_restore")

    try:
        get_data_dir().mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, get_db_path())
    except OSError as exc:
        raise DatabaseError(f"Impossible de restaurer la sauvegarde : {exc}") from exc

    # Contrôle final : la base restaurée doit s'ouvrir et contenir le schéma
    conn = connect()
    try:
        conn.execute("SELECT COUNT(*) FROM simulations")
    except sqlite3.Error as exc:
        raise DatabaseError(f"Base restaurée invalide : {exc}") from exc
    finally:
        conn.close()
    return get_db_path()
