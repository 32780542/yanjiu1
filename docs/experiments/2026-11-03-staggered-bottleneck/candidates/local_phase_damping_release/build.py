"""Compose fixed M and N edits; prove the two paths byte-identical."""
import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
DOC = Path(__file__).resolve().parent
BASE = ROOT / "tmp/staggered_bottleneck/candidates"
PARENTS = {
    "L": (BASE / "local_vacancy_bridge/native_rules.py", "e0707d0e8443e074a24de27524618417d0f8d8daff36b703a9a3a9066c47605a"),
    "M": (BASE / "local_phase_velocity_damping/native_rules.py", "a286110cf2e14904152b63c9a66f960496f5f7f04ab0097b8d7ed00353db4762"),
    "N": (BASE / "local_conflict_release/native_rules.py", "5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6"),
}
NEW = BASE / "local_phase_damping_release/native_rules.py"
assert not NEW.exists()
raw = {name: path.read_bytes() for name, (path, _) in PARENTS.items()}
assert all(hashlib.sha256(raw[name]).hexdigest() == sha for name, (_, sha) in PARENTS.items())
sources = {name: data.decode("utf-8") for name, data in raw.items()}
production = ROOT / "variants/phase5g_pure_formation/noa/native_rules.py"
production_before = production.read_bytes()
m_old = "                error += difference / max(1, pair_lanes - 1)\n"
m_new = "                error += (difference + (peer.speed - ego.speed) / POSITION_GAIN) / max(1, pair_lanes - 1)\n"
n_old = """    if organized and not memory.joining:
        lane = _fill(ego, rows, 2 if preparing else lanes)
"""
n_new = """    if organized and not memory.joining:
        if not moving and preparing and ego.lane == 1 and _clear(ego, rows, 0) and any(
            c.lane == 2 and c.x >= drop_x - 360.0 and abs(c.x - ego.x) <= 50.0
            and not _clear(c, (ego, *rows), 1) and _clear(c, rows, 1)
            for c in rows
        ):
            memory = Memory(lane_target=0, joining=True)
            speed, target, memory = _join_speed(ego, rows, memory, 0)
            return action(speed, 0, "release_ending", target), memory
        lane = _fill(ego, rows, 2 if preparing else lanes)
"""
assert sources["L"].count(m_old) == sources["L"].count(n_old) == 1
assert sources["L"].replace(m_old, m_new) == sources["M"]
assert sources["L"].replace(n_old, n_new) == sources["N"]
source = sources["M"].replace(n_old, n_new)
assert source == sources["N"].replace(m_old, m_new)
assert source.replace(n_new, n_old) == sources["M"]
assert source.replace(m_new, m_old) == sources["N"]
changed = [a.name for a, b in zip(ast.parse(sources["L"]).body, ast.parse(source).body) if ast.dump(a) != ast.dump(b)]
assert changed == ["_following", "_decide"]
memory_asts = [ast.dump(next(n for n in ast.parse(s).body if isinstance(n, ast.ClassDef) and n.name == "Memory"))
               for s in (*sources.values(), source)]
assert len(set(memory_asts)) == 1
compile(source, str(NEW), "exec")
NEW.parent.mkdir(parents=True)
NEW.write_text(source, encoding="utf-8", newline="\n")
for name in ("L", "M", "N"):
    patch = "".join(difflib.unified_diff(sources[name].splitlines(True), source.splitlines(True),
                                        fromfile=name + "/noa/native_rules.py", tofile="MN/noa/native_rules.py"))
    (DOC / ("native_rules.patch" if name == "L" else name + "_to_MN.patch")).write_text(patch, encoding="utf-8", newline="\n")
meta = dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(), lines=len(source.splitlines()),
            parents={name: sha for name, (_, sha) in PARENTS.items()}, changed_functions=changed,
            M_plus_N_equals_N_plus_M_bytes=True, reverse_to_either_parent_exact=True,
            memory_ast_sha256=hashlib.sha256(memory_asts[0].encode()).hexdigest(), memory_unchanged=True,
            rules_path=str(NEW), production_and_parent_sources_unchanged=True)
(DOC / "source.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
assert all(path.read_bytes() == raw[name] for name, (path, _) in PARENTS.items())
assert production.read_bytes() == production_before
print(json.dumps(meta))
