# utils/model_policy.py
"""Gardes de la Règle 11 : exécutabilité par tier, admissibilité des claims primaires,
exigence d'artefacts pour un full run, et reporting/robustesse cross-modèle."""

TIER_OPEN = {"A_fully_open", "B_open_weight"}
_REQUIRED_FULL_RUN_ARTIFACTS = ("model_revision", "tokenizer_revision",
                                "weights_sha256", "tokenizer_sha256", "inference_env_hash")


def normalize_tier(tier: str) -> str:
    return {"A_or_B_open": "A_fully_open"}.get(tier, tier)


def validate_model_providers(config: dict, run_mode: str):
    """Vérifie la politique de tiers selon le run_mode.
      - dev   : aucun modèle ouvert requis (résultats non scientifiques).
      - pilot : au moins un modèle ouvert (Tier A/B) doit être déclaré.
      - full  : un primary_reproducible Tier A/B est OBLIGATOIRE, avec TOUS les artefacts
                d'archivage renseignés (révisions, hashes, env). Tier C ⇒ jamais primaire.
    Lève ValueError en cas de violation."""
    mp = config.get("model_providers", {})
    primary = mp.get("primary_reproducible")
    secondary = mp.get("secondary_proprietary")

    if secondary and normalize_tier(secondary.get("tier", "")) == "C_proprietary_api":
        if secondary.get("use_for_primary_claims", False):
            raise ValueError("secondary_proprietary (Tier C) ne peut pas avoir use_for_primary_claims=true (Règle 11).")

    if run_mode == "dev":
        return
    # pilot/full : il faut au moins un modèle ouvert
    open_models = []
    if primary and normalize_tier(primary.get("tier", "")) in TIER_OPEN:
        open_models.append(primary)
    for m in mp.get("optional_cross_model_replication", {}).get("models", []):
        if normalize_tier(m.get("tier", "")) in TIER_OPEN:
            open_models.append(m)
    if not open_models:
        raise ValueError(f"run_mode={run_mode} exige au moins un modèle ouvert (Tier A/B).")

    if run_mode == "full":
        if not primary or normalize_tier(primary.get("tier", "")) not in TIER_OPEN:
            raise ValueError("full run : primary_reproducible (Tier A/B) obligatoire.")
        missing = [k for k in _REQUIRED_FULL_RUN_ARTIFACTS
                   if not primary.get(k) or str(primary.get(k)).startswith("FILL")]
        if missing:
            raise ValueError(
                f"full run : artefacts d'archivage manquants pour le modèle primaire ouvert : {missing}. "
                f"Renseigner révisions/hashes/env avant le gel (Règle 11)."
            )


def assert_primary_claim_allowed(model_run: dict):
    """Garde du reporter : refuse de marquer une métrique comme claim PRIMAIRE si elle ne
    provient pas d'un modèle admissible (Tier A/B avec use_for_primary_claims=1)."""
    tier = normalize_tier(model_run.get("provider_tier", ""))
    if tier not in TIER_OPEN or not model_run.get("use_for_primary_claims"):
        raise ValueError(
            f"Claim primaire refusé : modèle {model_run.get('model_name')} "
            f"(tier={tier}, use_for_primary_claims={model_run.get('use_for_primary_claims')}). "
            f"Les claims primaires sont restreints aux modèles Tier A/B (Règle 11)."
        )


def classify_cross_model_effect(per_model: dict, threshold: float = 0.0) -> str:
    """Classe un effet à partir d'un dict {model_run_id: {'tier':…, 'significant':bool}}.
      - model-invariant : significatif sur ≥ 2 modèles (dont ≥ 1 ouvert)
      - open-model-only : significatif uniquement sur des modèles ouverts
      - proprietary-only: significatif uniquement sur des modèles propriétaires
      - unstable        : aucun des cas ci-dessus (effet non robuste)."""
    sig_open  = [m for m in per_model.values() if m["significant"] and normalize_tier(m["tier"]) in TIER_OPEN]
    sig_prop  = [m for m in per_model.values() if m["significant"] and normalize_tier(m["tier"]) == "C_proprietary_api"]
    n_sig = len(sig_open) + len(sig_prop)
    if n_sig >= 2 and sig_open:
        return "model-invariant"
    if sig_open and not sig_prop:
        return "open-model-only"
    if sig_prop and not sig_open:
        return "proprietary-only"
    return "unstable"
