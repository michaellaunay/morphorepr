# utils/config_utils.py
# v6.10.0 — chargement/hash de config (référencé par orchestrator.py). Implémentation minimale.
import hashlib, json
import yaml

def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def hash_config(config) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()
