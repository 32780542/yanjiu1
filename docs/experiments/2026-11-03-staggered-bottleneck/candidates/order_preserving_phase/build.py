"""H: preserve observed head order; fixed E parent, no production edits."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[5]
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
E_PATH = REPO / "tmp/staggered_bottleneck/candidates/direct_gap/native_rules.py"
E_SHA = "04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274"
e_bytes, production = E_PATH.read_bytes(), (REPO / NAME).read_bytes()
assert hashlib.sha256(e_bytes).hexdigest() == E_SHA
original = e_bytes.decode("utf-8")
old = """    return (
        (peer.x + _physical_phase(peer, pair_lanes)) - (car.x + _physical_phase(car, pair_lanes))
    ), pair_lanes"""
new = """    dx = peer.x - car.x
    distance = abs(_physical_phase(peer, pair_lanes) - _physical_phase(car, pair_lanes))
    sign_source = dx or (_physical_phase(car, 3) - _physical_phase(peer, 3)) or (car.y - peer.y)
    return dx - copysign(distance, sign_source), pair_lanes"""
assert original.count(old) == 1 and original.count("from math import sqrt\n") == 1
source = original.replace(old, new).replace("from math import sqrt\n", "from math import copysign, sqrt\n")
compile(source, "order_preserving_phase/native_rules.py", "exec")
before, after = ast.parse(original).body, ast.parse(source).body
assert len(before) == len(after)
for a, b in zip(before, after):
    if isinstance(a, ast.FunctionDef) and a.name == "_pair_error":
        assert ast.dump(a) != ast.dump(b)
    elif isinstance(a, ast.ImportFrom) and a.module == "math":
        assert [x.name for x in b.names] == ["copysign", "sqrt"]
    else:
        assert ast.dump(a) == ast.dump(b)
destination = REPO / "tmp/staggered_bottleneck/candidates/order_preserving_phase/native_rules.py"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(source, encoding="utf-8", newline="\n")
patch = "".join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                    fromfile="E/" + NAME, tofile="H/" + NAME))
Path(__file__).with_name("native_rules.patch").write_text(patch, encoding="utf-8", newline="\n")
assert E_PATH.read_bytes() == e_bytes and (REPO / NAME).read_bytes() == production
metadata = dict(base_commit="177f7a32088fb69efcc94d9acb72863e7e00e787", parent_candidate="direct_gap",
                parent_sha256=E_SHA, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                changed_functions=["_pair_error"], import_added="math.copysign", lines=len(source.splitlines()),
                rules_path=str(destination), production_unchanged=True, parent_unchanged=True,
                noa_control_unchanged=True, same_lane_cth_unchanged=True)
Path(__file__).with_name("source.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata))
