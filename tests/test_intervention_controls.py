# ─────────────────────────────────────────────
# tests/test_intervention_controls.py  (v6.9.0 — contrôles d'intervention)
# Déterministe : sélecteurs/seed purs, FakeSAE/FakeModel légers, classifieurs via
# cs.CLASSIFIER_BY_PROPERTY, et insertions directes dans intervention_control_results pour le
# scoring. Aucun modèle réel n'est chargé (l'intégration live est opt-in, MORPHOREPR_RUN_DEV_CONTROLS).
# ─────────────────────────────────────────────
import json as _json
import sqlite3 as _sqlite3
import pytest as _pytest
import torch as _torch
import agents.steerer as stz
import agents.causal_scorer as cs
from agents.causal_scorer import load_intervention_control_pairs, score_intervention_controls

_CFG_IC = {
    "primary_split": "random",
    "seed": 42,
    "steering": {"magnitude_mode": "p99_relative", "primary_magnitude_rel": 1.0,
                 "legacy_absolute_magnitude": 5, "primary_probe_family": "neutral",
                 "exclude_ood_from_primary": True, "intervention_space": "residual_add_decoder",
                 "token_position": "all", "decoding": {"temperature": 0.0, "max_new_tokens": 8},
                 "n_probe_sentences": 1},
    "stats": {"bootstrap_resamples": 50},
    "thresholds": {"nim_delta": 0.05},
    "intervention_controls": {"run_in_pipeline": False, "strict_controls": True, "score_controls": True,
                              "controls_to_run": ["random_feature_same_layer", "matched_activation_freq",
                                                  "random_direction_same_norm", "negative_steering",
                                                  "prompt_only"],
                              "prompt_only_annotation_source": "nl_description",
                              "matched_activation_freq_log_eps": 1e-9},
    "_runtime": {"model_run_ids": {"primary": "mrP"}},
}


class _FakeModel:
    """Modèle factice : enregistre les prompts, ne supporte AUCUN hook (toute tentative de
    steering lèverait AttributeError → prouve prompt_only sans intervention résiduelle)."""
    def __init__(self): self.prompts = []
    def generate(self, prompt, **kw): self.prompts.append(prompt); return f"GEN::{prompt[:14]}"


class _FakeSAE:
    def __init__(self, n=8, d=4):
        self.W_dec = _torch.ones(n, d)
        class _C: hook_name = "blocks.3.hook_resid_post"
        self.cfg = _C()


def _mk_run(c, r="r1"): c.execute("""INSERT INTO runs (run_id,git_commit,config_hash,prompt_hashes,lexicon_version,lexicon_hash,corpus_hash,models_json,use_temperature,temperature,seed,proxy_model,started_at,completed_at,status,last_phase,total_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (r,'c','h','{}','v1','lh','ch','{}',0,None,42,None,'2026-01-01',None,'running',None,0.0))
def _mk_mr(c, r, mrid, nm="primary", t="B_open_weight"): c.execute("""INSERT INTO model_runs (model_run_id,run_id,provider_name,provider_tier,backend,model_name,generation_params_json,created_at) VALUES (?,?,?,?,?,?,'{}','2026-01-01')""", (mrid,r,"p",t,"vllm",nm))
def _mk_feat(c, idx, split="random", layer_index=3, freq=0.05, p99=2.0):
    uid=f"gpt2:res-jb:{layer_index}:hook_resid_post:{idx}"
    c.execute("""INSERT INTO features (feature_uid,model_name,sae_release,layer_index,hook_name,feature_index,split,nl_description,top_examples,score_interp,activation_freq,activation_p99,activation_mean,activation_std,layer,neuronpedia_url,loaded_at) VALUES (?, 'gpt2','res-jb',?,'hook_resid_post',?,?,'negation feature','[]',0.8,?,?,0.8,0.4,?,'x','2026-01-01')""",(uid,layer_index,idx,split,freq,p99,str(layer_index)))
    return uid
def _mk_pred(c, r, mrid, uid, idx, props, agent="predictor"):
    c.execute("""INSERT INTO agent_outputs (output_id,run_id,model_run_id,feature_uid,feature_index,agent_name,run_number,output_json,raw_output,status,error_msg,tokens_input,tokens_output,batch_id,cost_usd,coefficient_type,created_at) VALUES (?,?,?,?,?,?,1,?,?,'ok',NULL,1,1,NULL,0.0,'confidence','2026-01-01')""",(f"p-{mrid}-{idx}-{agent}",r,mrid,uid,idx,agent,_json.dumps({"status":"ok","predictions":[{"property":k,"direction":v} for k,v in props.items()]}),"raw"))
def _mk_steer(c, r, mrid, uid, idx):
    c.execute("""INSERT INTO steering_results (result_id,run_id,model_run_id,feature_uid,feature_index,intervention_space,magnitude,magnitude_rel,magnitude_key,probe_id,probe_family,probe_category,generation_index,text_before,text_after,layer,token_position,activation_before,activation_after,achieved_delta,ood_flag,created_at) VALUES (?,?,?,?,?,'residual_add_decoder',2.0,1.0,'rel:1.0',?,'neutral',NULL,0,'a','b','3','all',1.0,2.0,1.0,0,'2026-01-01')""",(f"s-{mrid}-{idx}",r,mrid,uid,idx,idx))
def _mk_control(c, r, mrid, tuid, idx, name, space, before, after, ood=0, probe_id=1, gen=0, cuid=None):
    c.execute("""INSERT INTO intervention_control_results (control_result_id,run_id,model_run_id,target_feature_uid,target_feature_index,control_name,control_feature_uid,control_feature_index,intervention_space,magnitude,magnitude_rel,magnitude_key,probe_id,probe_family,probe_category,generation_index,text_before,text_after,activation_before,activation_after,achieved_delta,ood_flag,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'2026-01-01')""",(f"c-{mrid}-{idx}-{name}-{probe_id}-{gen}",r,mrid,tuid,idx,name,cuid,None,space,2.0,1.0,'rel:1.0',probe_id,'neutral',None,gen,before,after,1.0,2.0,1.0,ood,None))
def _C(p): c=_sqlite3.connect(p); c.row_factory=_sqlite3.Row; return c


# 1. no-op quand run_in_pipeline=false
def test_controls_noop_disabled(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); c.commit(); c.close()
    res = stz.run_intervention_controls("r1", _json.loads(_json.dumps(_CFG_IC)))
    assert res["status"] == "disabled"
    c=_C(test_db); assert c.execute("SELECT COUNT(*) FROM intervention_control_results").fetchone()[0]==0; c.close()


# 2. sélection feature aléatoire de même couche
def test_select_random_feature_same_layer(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP")
    t=_mk_feat(c,1,layer_index=3); _mk_feat(c,2,layer_index=3); _mk_feat(c,3,layer_index=3); _mk_feat(c,9,layer_index=4)
    c.commit(); c.close()
    cands = stz._load_layer_candidates(3, t)
    assert cands and all(x["layer_index"]==3 for x in cands) and all(x["feature_uid"]!=t for x in cands)
    sel = stz._select_random_feature_same_layer({"feature_uid":t}, cands, 42)
    assert sel["layer_index"]==3 and sel["feature_uid"]!=t


# 3. matched activation frequency = plus proche en distance log
def test_select_matched_activation_freq():
    target={"activation_freq":0.05}
    cands=[{"feature_uid":"a","activation_freq":0.051},{"feature_uid":"b","activation_freq":0.5},
           {"feature_uid":"c","activation_freq":0.0001}]
    best,d = stz._select_matched_activation_freq(target, cands, 1e-9)
    assert best["feature_uid"]=="a" and d < 0.1


# 4. random direction déterministe + norme cible
def test_random_direction_deterministic_and_norm():
    h1,n1 = stz._make_random_direction_hook(4, 3.0, 1.0, "all", 123)
    h2,n2 = stz._make_random_direction_hook(4, 3.0, 1.0, "all", 123)
    h3,_  = stz._make_random_direction_hook(4, 3.0, 1.0, "all", 999)
    def apply(h):
        r=_torch.zeros(1,2,4); return h(r, None)[0,0].clone()
    v1,v2,v3 = apply(h1),apply(h2),apply(h3)
    assert _torch.allclose(v1,v2) and not _torch.allclose(v1,v3)
    assert abs(float(v1.norm())-3.0) < 1e-4 and abs(n1-3.0) < 1e-4


# 5. negative steering : magnitude primaire rel:1.0 → contrôle rel:-1.0, magnitude absolue négative
def test_negative_steering_magnitude(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); _mk_feat(c,1,p99=2.0); c.commit(); c.close()
    monkeypatch.setattr(stz, "_get_sae", lambda cfg, layer: _FakeSAE())
    target={"feature_uid":"gpt2:res-jb:3:hook_resid_post:1","feature_index":1,"layer_index":3,
            "activation_p99":2.0,"activation_mean":0.8,"activation_std":0.4,"nl_description":"x"}
    mag_abs,rel,key = stz._primary_magnitude(_CFG_IC, target)
    assert key=="rel:1.0" and mag_abs==2.0
    plan = stz._build_control_plan("r1","mrP","negative_steering",target,_CFG_IC)
    assert plan["mag_key"]=="rel:-1.0" and plan["magnitude"]==-2.0 and plan["mag_rel"]==-1.0


# 6. prompt_only : aucun hook de steering, text_after via prompt enrichi
def test_prompt_only_no_hook(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); c.commit(); c.close()
    fake=_FakeModel()
    target={"feature_uid":"gpt2:res-jb:3:hook_resid_post:1","feature_index":1,"layer_index":3,
            "activation_p99":2.0,"activation_mean":0.8,"activation_std":0.4,"nl_description":"negation"}
    conn=_C(test_db)
    n = stz._run_control_for_target(conn,fake,"r1","mrP","prompt_only",target,
                                    [("neutral",None,["the cat sat on the mat"])],1,_CFG_IC)
    conn.commit()
    assert n==1 and len(fake.prompts)==2 and "Consider the concept" in fake.prompts[1]
    row=conn.execute("SELECT * FROM intervention_control_results WHERE control_name='prompt_only'").fetchone()
    conn.close()
    assert row["intervention_space"]=="prompt_only" and row["text_before"]!=row["text_after"]


# 7. insertion idempotente
def test_control_insert_idempotent(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); _mk_feat(c,1); c.commit()
    target={"feature_uid":"gpt2:res-jb:3:hook_resid_post:1","feature_index":1}
    a = stz._insert_intervention_control_result(c,"r1","mrP",target,"negative_steering",None,
            "residual_add_decoder",-2.0,-1.0,"rel:-1.0","neutral",None,1,0,"a","b",1.0,2.0,1.0,0,{})
    b = stz._insert_intervention_control_result(c,"r1","mrP",target,"negative_steering",None,
            "residual_add_decoder",-2.0,-1.0,"rel:-1.0","neutral",None,1,0,"a","b",1.0,2.0,1.0,0,{})
    c.commit()
    assert a is True and b is False
    assert c.execute("SELECT COUNT(*) FROM intervention_control_results").fetchone()[0]==1
    c.close()


# 8. model-aware : le primaire ne charge jamais les contrôles du secondaire
def test_control_pairs_model_aware(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); _mk_mr(c,"r1","mrS","sec","C_proprietary_api")
    u=_mk_feat(c,1)
    _mk_pred(c,"r1","mrP",u,1,{"negation_presence":"INCREASE"})
    _mk_control(c,"r1","mrP",u,1,"negative_steering","residual_add_decoder","a","b")
    _mk_control(c,"r1","mrS",u,1,"negative_steering","residual_add_decoder","a","b")
    c.commit(); c.close()
    monkeypatch.setattr(cs,"CLASSIFIER_BY_PROPERTY",{"negation_presence":lambda tb,ta:{"direction":"INCREASE"}})
    pairs = load_intervention_control_pairs("r1","negative_steering",config=_CFG_IC,model_run_id="mrP",split="random")
    assert len(pairs)==1 and pairs[0]["control_name"]=="negative_steering"


# 9. split-aware
def test_control_pairs_split_aware(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP")
    ur=_mk_feat(c,1,"random"); ue=_mk_feat(c,2,"easy")
    for u,i in ((ur,1),(ue,2)):
        _mk_pred(c,"r1","mrP",u,i,{"negation_presence":"INCREASE"})
        _mk_control(c,"r1","mrP",u,i,"negative_steering","residual_add_decoder","a","b")
    c.commit(); c.close()
    monkeypatch.setattr(cs,"CLASSIFIER_BY_PROPERTY",{"negation_presence":lambda tb,ta:{"direction":"INCREASE"}})
    pairs = load_intervention_control_pairs("r1","negative_steering",config=_CFG_IC,model_run_id="mrP",split="random")
    assert {p["feature_uid"] for p in pairs}=={ur}


# 10. OOD exclu si exclude_ood_from_primary=true
def test_control_pairs_ood_excluded(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); u=_mk_feat(c,1)
    _mk_pred(c,"r1","mrP",u,1,{"negation_presence":"INCREASE"})
    _mk_control(c,"r1","mrP",u,1,"negative_steering","residual_add_decoder","a","b",ood=1)   # OOD → exclu
    c.commit(); c.close()
    monkeypatch.setattr(cs,"CLASSIFIER_BY_PROPERTY",{"negation_presence":lambda tb,ta:{"direction":"INCREASE"}})
    with _pytest.raises(RuntimeError, match="No intervention-control observations"):
        load_intervention_control_pairs("r1","negative_steering",config=_CFG_IC,model_run_id="mrP",split="random")


# 11. load_intervention_control_pairs : couple produit
def test_load_control_pairs(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); u=_mk_feat(c,1)
    _mk_pred(c,"r1","mrP",u,1,{"negation_presence":"INCREASE"})
    _mk_control(c,"r1","mrP",u,1,"random_feature_same_layer","residual_add_decoder","a","b",cuid="gpt2:res-jb:3:hook_resid_post:2")
    c.commit(); c.close()
    monkeypatch.setattr(cs,"CLASSIFIER_BY_PROPERTY",{"negation_presence":lambda tb,ta:{"direction":"DECREASE"}})
    pairs = load_intervention_control_pairs("r1","random_feature_same_layer",config=_CFG_IC,model_run_id="mrP",split="random")
    assert len(pairs)==1 and pairs[0]["predicted"]=="INCREASE" and pairs[0]["observed"]=="DECREASE"


# 12-13. scoring contrôle : métriques secondaires + paired diff, model_run_id renseigné
def test_score_intervention_controls(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP")
    for i in (1,2,3):
        u=_mk_feat(c,i)
        _mk_pred(c,"r1","mrP",u,i,{"negation_presence":"INCREASE"})
        _mk_steer(c,"r1","mrP",u,i)                                   # primaire
        _mk_control(c,"r1","mrP",u,i,"negative_steering","residual_add_decoder","a","b")
    c.commit(); c.close()
    monkeypatch.setattr(cs,"CLASSIFIER_BY_PROPERTY",{"negation_presence":lambda tb,ta:{"direction":"INCREASE"}})
    cfg=_json.loads(_json.dumps(_CFG_IC)); cfg["intervention_controls"]["controls_to_run"]=["negative_steering"]
    res = score_intervention_controls("r1", cfg)
    assert res["primary"]["macro_f1"]==1.0 and "negative_steering" in res["controls"]
    assert res["controls"]["negative_steering"]["coverage"]["n_shared_features"]==3
    c=_C(test_db)
    mf=c.execute("SELECT value,model_run_id FROM metrics WHERE metric_name='intervention_control_macro_f1:negative_steering'").fetchone()
    pd=c.execute("SELECT COUNT(*) FROM metrics WHERE metric_name='intervention_control_paired_diff:negative_steering'").fetchone()[0]
    nn=c.execute("SELECT COUNT(*) FROM metrics WHERE phase='p4_controls' AND model_run_id IS NULL").fetchone()[0]
    c.close()
    assert mf["model_run_id"]=="mrP" and pd==1 and nn==0


# 14. contrôle activé mais non implémenté → NotImplementedError (avant toute génération)
def test_diffmean_reft_not_implemented(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); c.commit(); c.close()
    cfg=_json.loads(_json.dumps(_CFG_IC))
    cfg["intervention_controls"]["run_in_pipeline"]=True
    cfg["intervention_controls"]["controls_to_run"]=["diffmean_reft"]
    with _pytest.raises(NotImplementedError, match="diffmean_reft"):
        stz.run_intervention_controls("r1", cfg)


# 15. absence de steering_results primaire → erreur claire
def test_ready_missing_primary_steering(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); u=_mk_feat(c,1)
    _mk_pred(c,"r1","mrP",u,1,{"negation_presence":"INCREASE"})       # prédiction mais PAS de steering
    c.commit(); c.close()
    with _pytest.raises(RuntimeError, match="steering_results primaire"):
        stz.assert_intervention_controls_ready("r1", _CFG_IC)


# 16. absence de prédictions MorphoRepr → erreur claire
def test_ready_missing_predictions(test_db):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); u=_mk_feat(c,1); _mk_steer(c,"r1","mrP",u,1)
    c.commit(); c.close()
    with _pytest.raises(RuntimeError, match="prédiction MorphoRepr"):
        stz.assert_intervention_controls_ready("r1", _CFG_IC)


# 17. absence de candidates même couche : strict raise / non strict skip
def test_no_candidates_strict_vs_lax(test_db, monkeypatch):
    c=_C(test_db); _mk_run(c); _mk_mr(c,"r1","mrP"); _mk_feat(c,1,layer_index=7); c.commit(); c.close()
    monkeypatch.setattr(stz, "_get_sae", lambda cfg, layer: _FakeSAE())
    target={"feature_uid":"gpt2:res-jb:7:hook_resid_post:1","feature_index":1,"layer_index":7,
            "activation_p99":2.0,"activation_mean":0.8,"activation_std":0.4,"nl_description":"x"}
    strict=_json.loads(_json.dumps(_CFG_IC))            # strict_controls=true
    with _pytest.raises(RuntimeError, match="aucune feature candidate"):
        stz._build_control_plan("r1","mrP","random_feature_same_layer",target,strict)
    lax=_json.loads(_json.dumps(_CFG_IC)); lax["intervention_controls"]["strict_controls"]=False
    assert stz._build_control_plan("r1","mrP","random_feature_same_layer",target,lax) is None
