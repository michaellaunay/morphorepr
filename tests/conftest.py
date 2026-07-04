# tests/conftest.py
# v6.10.0 — stub des dépendances lourdes OPTIONNELLES : les tests unitaires tournent sans clé API,
# sans téléchargement de modèle et sans accès réseau. (transformer_lens/sae_lens ne sont touchés que
# par le test slow opt-in, gardé par MORPHOREPR_RUN_SLOW_STEERING.)
import sys as _sys, types as _types
for _n in ("anthropic", "transformer_lens", "sae_lens", "spacy", "transformers"):
    if _n not in _sys.modules:
        try:
            __import__(_n)
        except Exception:
            _sys.modules[_n] = _types.ModuleType(_n)
_anth = _sys.modules.get("anthropic")
if isinstance(_anth, _types.ModuleType):
    for _a, _v in (("Anthropic", object), ("APIError", Exception),
                   ("APIStatusError", Exception), ("RateLimitError", Exception)):
        if not hasattr(_anth, _a):
            setattr(_anth, _a, _v)
_tf = _sys.modules.get("transformers")
if isinstance(_tf, _types.ModuleType) and not hasattr(_tf, "pipeline"):
    _tf.pipeline = lambda *a, **k: (_ for _ in ()).throw(
        NotImplementedError("transformers.pipeline stubbed in tests"))
_sp = _sys.modules.get("spacy")
if isinstance(_sp, _types.ModuleType) and not hasattr(_sp, "load"):
    _sp.load = lambda *a, **k: (_ for _ in ()).throw(
        NotImplementedError("spacy.load stubbed in tests"))

import os
import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """DB temporaire isolée injectée via env var. Aucune DB de production touchée."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("MORPHOREPR_DB_PATH", str(db_path))
    schema = Path("db/schema.sql").read_text()
    conn   = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    return db_path


# ─────────────────────────────────────────────

