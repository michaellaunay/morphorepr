# tests/test_parser.py
# ─────────────────────────────────────────────

import pytest
from utils.morphorepr_parser import (
    parse_expression, parse_word,
    is_valid_root, can_register_new_free_root
)


# Tous les exemples d'encodage du papier doivent parser correctement (cas mal/ne et infixes).
@pytest.mark.parametrize("word,root,prefixes,infixes,suffix", [
    ("ag-is",          "ag",   [],      [],      "-is"),
    ("mal-o",          "mal",  [],      [],      "-o"),   # mal comme RACINE
    ("ne-a",           "ne",   [],      [],      "-a"),   # ne comme RACINE
    ("mal-emo-a",      "emo",  ["mal"], [],      "-a"),   # mal comme PRÉFIXE
    ("ne-soc-a",       "soc",  ["ne"],  [],      "-a"),
    ("soc-ant-o",      "soc",  [],      ["ant"], "-o"),
    ("dat-ad-o",       "dat",  [],      ["ad"],  "-o"),
    ("ag-int-a",       "ag",   [],      ["int"], "-a"),
    ("pens-ad-is",     "pens", [],      ["ad"],  "-is"),
    ("mal-far-int-e",  "far",  ["mal"], ["int"], "-e"),
    ("mal-ne-o",       "ne",   ["mal"], [],      "-o"),   # préfixe mal + racine ne
])
def test_examples_from_paper(word, root, prefixes, infixes, suffix):
    t = parse_word(word, known_free_roots={"far", "pens"})
    assert t.is_valid, f"{word} devrait être valide : {t.parse_error}"
    assert t.root == root
    assert t.prefixes == prefixes
    assert t.infixes == infixes
    assert t.suffix == suffix


class TestParseWord:
    def test_verbal_simple(self):
        t = parse_word("ag-is")
        assert t.root == "ag" and t.suffix == "-is"
        assert t.suffix_type == "tense" and t.is_valid

    def test_prefix_root_suffix(self):
        t = parse_word("mal-emo-a")
        assert "mal" in t.prefixes
        assert t.root == "emo" and t.suffix == "-a"
        assert t.suffix_type == "syntactic" and t.is_valid

    def test_root_infix_suffix(self):
        t = parse_word("soc-ant-o")
        assert t.root == "soc" and "ant" in t.infixes and t.suffix == "-o"
        assert t.is_valid

    def test_sans_suffixe_invalide(self):
        t = parse_word("ag")
        assert not t.is_valid and t.parse_error is not None

    def test_racine_libre(self):
        t = parse_word("pens-is")
        assert t.root == "pens" and t.suffix == "-is" and t.is_valid


class TestParseExpression:
    def test_deux_termes_valides(self):
        e = parse_expression("0.86·mal-emo-a + 0.42·ne-soc-a")
        assert e.is_valid and len(e.terms) == 2
        assert e.roots == {"emo", "soc"}

    def test_ordre_decroissant_obligatoire(self):
        e = parse_expression("0.40·ag-is + 0.90·sci-o")
        assert not e.is_valid and "décroissant" in e.parse_error.lower()

    def test_coefficient_hors_plage(self):
        e = parse_expression("9.99·ag-is")
        assert not e.is_valid

    def test_expression_vide(self):
        assert not parse_expression("").is_valid


class TestRootValidation:
    def test_racine_libre_bien_formee_valide(self):
        assert is_valid_root("pens") and is_valid_root("far")

    def test_token_reserve_invalide_comme_racine(self):
        assert not is_valid_root("is")
        assert not is_valid_root("ad")
        assert not is_valid_root("pli")   # préfixe réservé, pas une racine

    def test_mal_ne_valides_comme_racines_predefinies(self):
        # mal et ne SONT des racines valides (prédéfinies)...
        assert is_valid_root("mal") and is_valid_root("ne")

    def test_mal_ne_non_enregistrables_comme_libres(self):
        # ...mais ne peuvent PAS être ré-enregistrées comme NOUVELLES racines libres.
        assert can_register_new_free_root("mal") is not None
        assert can_register_new_free_root("ne")  is not None

    def test_enregistrement_racine_libre_valide(self):
        assert can_register_new_free_root("pens") is None

    def test_enregistrement_token_reserve_rejete(self):
        assert can_register_new_free_root("ad") is not None

    def test_enregistrement_deja_enregistree_rejete(self):
        assert can_register_new_free_root("far", known_free_roots={"far"}) is not None

    def test_trop_long_rejete(self):
        assert not is_valid_root("toolong")
        assert can_register_new_free_root("toolong") is not None

    def test_majuscule_rejetee(self):
        assert not is_valid_root("Pens")
        assert can_register_new_free_root("Pens") is not None


# ─────────────────────────────────────────────
