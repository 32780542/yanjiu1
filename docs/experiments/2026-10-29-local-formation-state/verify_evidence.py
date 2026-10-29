"""Verify the compact evidence and recount the included 0/1 trace with stdlib."""
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

BASE = Path(__file__).resolve().parent
manifest = json.loads((BASE / "manifest.json").read_bytes())
archive = (BASE / "evidence.tar.gz").read_bytes()
assert hashlib.sha256(archive).hexdigest() == manifest["archive_sha256"]
assert hashlib.sha256((BASE / "summary.json").read_bytes()).hexdigest() == manifest["summary_sha256"]
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as stream:
    files = {m.name: stream.extractfile(m).read() for m in stream.getmembers() if m.isfile()}
assert set(files) == set(manifest["members"])
for name, raw in files.items():
    assert hashlib.sha256(raw).hexdigest() == manifest["members"][name], name

prefix = "cases/lane_drop_transform/"
def frames(version):
    return [json.loads(line) for line in gzip.decompress(files[prefix + version + "/positions.jsonl.gz"]).splitlines()]

old, new = frames("baseline"), frames("current")
assert len(old) == len(new)
vehicle_seconds = participating_seconds = 0.0
starts, episodes, peak = {}, [], 0
for index, (before, after) in enumerate(zip(old, new)):
    now, flags = after["time_s"], after["formation_states"]
    assert before["time_s"] == now and before["states"] == after["states"]
    assert set(flags) == set(after["states"])
    assert all(type(value) is int and value in (0, 1) for value in flags.values())
    if index:
        dt = now - new[index - 1]["time_s"]
        previous = new[index - 1]["formation_states"]
        vehicle_seconds += dt * len(previous)
        participating_seconds += dt * sum(previous.values())
    for key in tuple(starts):
        if not flags.get(key):
            episodes.append(now - starts.pop(key))
    for key, value in flags.items():
        if value:
            starts.setdefault(key, now)
    peak = max(peak, sum(flags.values()))
episodes.extend(new[-1]["time_s"] - start for start in starts.values())
actual = dict(vehicle_seconds=vehicle_seconds, participating_vehicle_seconds=participating_seconds,
              participation_rate=participating_seconds / vehicle_seconds,
              mean_participants=participating_seconds / (new[-1]["time_s"] - new[0]["time_s"]),
              peak_participants=peak, episodes=len(episodes), mean_episode_s=sum(episodes) / len(episodes),
              max_episode_s=max(episodes))
expected = json.loads(files[prefix + "current/result.json"])["formation_state"]
for key, value in actual.items():
    assert math.isclose(value, expected[key], rel_tol=1e-9, abs_tol=1e-8), key
assert files[prefix + "baseline/trips.json"] == files[prefix + "current/trips.json"]
for label in ("core_final", "root_GUI", "physical_pairs"):
    assert json.loads(files[f"operations/{label}/result.json"])["returncode"] == 0
print(json.dumps(dict(passed=True, archive_members=len(files), physical_pair_frames=len(new),
                      direct_state_summary=actual, simulation_run=False)))
