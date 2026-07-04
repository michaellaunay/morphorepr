# tests/test_config_hash.py
# v6.10.0 cleanup — garde d'intégrité de config : hash du CONTENU, pas du chemin.
import pytest
from utils.config_utils import load_config, hash_config


@pytest.fixture
def cfg_yaml(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("run_id_prefix: dev\nlexicon_version: v1.0\nseed: 42\n", encoding="utf-8")
    return p


def test_chemin_et_dict_donnent_le_meme_hash(cfg_yaml):
    assert hash_config(cfg_yaml) == hash_config(load_config(cfg_yaml))
    assert hash_config(str(cfg_yaml)) == hash_config(cfg_yaml)


def test_modifier_le_yaml_change_le_hash(cfg_yaml):
    before = hash_config(cfg_yaml)
    cfg_yaml.write_text("run_id_prefix: dev\nlexicon_version: v1.0\nseed: 43\n", encoding="utf-8")
    assert hash_config(cfg_yaml) != before


def test_le_hash_ne_depend_pas_du_nom_ni_de_l_ordre_des_cles(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("x: 1\ny: deux\n", encoding="utf-8")
    b.write_text("y: deux\nx: 1\n", encoding="utf-8")
    assert hash_config(a) == hash_config(b)


def test_deux_contenus_differents_hashs_differents(tmp_path):
    a = tmp_path / "a.yaml"; a.write_text("x: 1\n", encoding="utf-8")
    b = tmp_path / "b.yaml"; b.write_text("x: 2\n", encoding="utf-8")
    assert hash_config(a) != hash_config(b)


def test_dict_directement(cfg_yaml):
    d = load_config(cfg_yaml)
    h1 = hash_config(d)
    d2 = dict(reversed(list(d.items())))
    assert hash_config(d2) == h1  # clés triées => insensible à l'ordre d'insertion
