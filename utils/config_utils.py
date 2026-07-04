# utils/config_utils.py
# v6.10.0 — chargement/hash de config (référencé par orchestrator.py).
# Cleanup v6.10.0 : hash_config() accepte un CHEMIN ou un dict et hashe le CONTENU
# YAML canonique. L'orchestrateur l'appelle avec args.config (un chemin) ; l'ancienne
# version hashait la chaîne du chemin elle-même, rendant inopérante la garde
# « config modifiée depuis le run original » (initialize_run, verify_resume_integrity).
import hashlib
import json
from pathlib import Path

import yaml


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def hash_config(path_or_config) -> str:
    """SHA256 canonique du CONTENU de la config (clés triées, UTF-8).

    Accepte un chemin vers un fichier YAML (str ou Path) ou un dict déjà chargé.
    Invariant : hash_config(path) == hash_config(load_config(path)).
    """
    if isinstance(path_or_config, (str, Path)):
        data = load_config(path_or_config)
    else:
        data = path_or_config
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
