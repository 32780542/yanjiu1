"""Freeze only the authorized P forming/fill ablation and its fixed-state proof."""
import ast
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
P = ROOT / "tmp/common_pair_P_release"
OLD = ROOT / "tmp/H_strict_formation_ablation"

def read(path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def nodes(path):
    out={}
    for n in ast.parse(path.read_text(encoding="utf-8")).body:
        name=getattr(n,"name",None)
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="MODES" for t in n.targets):name="MODES"
        out[name or f"line{n.lineno}"]=ast.dump(n,include_attributes=False)
    return out

base=read(PACKAGE/"base_manifest.json"); anchor=read(ROOT/"tmp/P_analysis_expected.json")
assert sha(P/"freeze.json")==anchor["release_freeze_sha256"]
changed={}
for name,expected in base["source_sha256"].items():
    assert sha(P/name)==expected
    if (PACKAGE/name).read_bytes()!=(P/name).read_bytes():
        before,after=nodes(P/name),nodes(PACKAGE/name)
        changed[name]=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
assert changed=={"experiments/native_sumo.py":["MODES"],"noa/native_rules.py":["_decide"]},changed
cn,pn,on=nodes(PACKAGE/"noa/native_rules.py"),nodes(P/"noa/native_rules.py"),nodes(OLD/"noa/native_rules.py")
for name in ("_following","_pair_error","_fill"):
    assert cn[name]==pn[name]
for name in ("_make_room","_receiving","_receiving_distance","_merge_target","_join_speed","_mandatory_priority","_clear","safe_speed","_occupies","Memory","Vehicle"):
    assert cn[name]==pn[name]==on[name],name
for name,expected in base["configs_sha256"].items():assert sha(PACKAGE/name)==sha(P/name)==expected
evaluation=read(PACKAGE/"analysis_source/freeze.json")
for name,expected in evaluation["source_sha256"].items():assert sha(PACKAGE/"analysis_source"/name)==expected
inheritance=dict(label="C1_P straight behavior inherited from bound old C1_H/C0 evidence",
    reuse_H_noa_straight=True,C0_report_sha256=sha(OLD/"straight_equivalence_report.json"),
    copied_report_sha256=sha(PACKAGE/"straight_equivalence_report.json"),
    original_C1_H_freeze_sha256=sha(OLD/"freeze.json"),
    fixed_state_actions_and_Memory_identical=True,new_pair_following_fill_unexecuted=True,
    original_evidence_source=str(OLD/"straight_equivalence_report.json"),new_short_simulations=0)
assert inheritance["C0_report_sha256"]==inheritance["copied_report_sha256"]
(PACKAGE/"straight_equivalence_inheritance.json").write_text(json.dumps(inheritance,indent=2)+"\n",encoding="utf-8")
manifest=dict(label="C1_P strict formation ablation",source_parent=str(P),source_sha256={n:sha(PACKAGE/n) for n in base["source_sha256"]},
    P_source_sha256=base["source_sha256"],P_source_root=str(P),P_release_freeze_sha256=sha(P/"freeze.json"),
    old_C1_H_root=str(OLD),old_C1_H_source_sha256=read(OLD/"freeze.json")["source_sha256"],
    configs_sha256=base["configs_sha256"],changed_AST_nodes=changed,mode="cooperative",normal_overtake=False,
    group_following=False,layer_fill=False,seeds=[6,7,8,9,10],flows=[500.0,750.0,1000.0,1500.0],jobs=2,duration_s=600,max_time_s=900,
    numeric_parameters_added=0,Memory_fields_added=0,shared_helpers_and_guards_exact_P_and_old_C1_H=True,
    pair_error_following_fill_definitions_exact_P_but_unexecuted=True,
    tests=dict(red="20261029T034234279474Z_C1_P-static-red_8fdf1985",red_failures=6,
               green="20261029T034309864908Z_C1_P-static-green_fe0820d5",green_tests=8),
    wrapper_sha256=sha(PACKAGE/"run_flow_study.py"),evaluator_source_exact_old_C1=True,
    straight_equivalence_inheritance=inheritance,parameter_pairing="Raw parameters_sha256 must equal P, including float types; no normalization exception")
(PACKAGE/"freeze.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
print(json.dumps(dict(label=manifest["label"],rules_sha256=manifest["source_sha256"]["noa/native_rules.py"],wrapper_sha256=manifest["wrapper_sha256"],changes=changed)))
