# ─────────────────────────────────────────────
# tests/test_batch_custom_id.py  (v6.2)
# Les custom_id Batch API doivent être uniques même si feature_index est répété entre couches.
# ─────────────────────────────────────────────

from utils.api_utils import feature_custom_id, build_custom_id_map, build_batch_item_rows


def test_batch_custom_id_unique_with_same_feature_index():
    features = [
        {"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
        {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123},
    ]
    ids = [feature_custom_id(f) for f in features]
    assert len(ids) == len(set(ids))            # pas de collision


def test_custom_id_map_recupere_feature_uid():
    features = [
        {"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
        {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123},
    ]
    m = build_custom_id_map(features)
    assert m[feature_custom_id(features[0])] == "gpt2:res-jb:6:hook_resid_post:123"
    assert m[feature_custom_id(features[1])] == "gpt2:res-jb:9:hook_resid_post:123"


def test_submit_rejette_batch_items_incoherents():
    """Pré-vérification AVANT soumission : si les custom_id des requests ≠ batch_items,
    submit_and_poll_batch lève ValueError (avant tout appel réseau, donc avant facturation)."""
    import pytest
    from utils.api_utils import submit_and_poll_batch
    feats = [{"feature_uid": "gpt2:res-jb:6:hook_resid_post:123", "feature_index": 123},
             {"feature_uid": "gpt2:res-jb:9:hook_resid_post:123", "feature_index": 123}]
    requests = [{"custom_id": feature_custom_id(f), "params": {}} for f in feats]
    items    = build_batch_item_rows(feats[:1])   # incomplet : il manque la 2ᵉ feature
    with pytest.raises(ValueError):
        submit_and_poll_batch(requests, "r1", "p3", "encoder", 1, "m", {}, batch_items=items)
