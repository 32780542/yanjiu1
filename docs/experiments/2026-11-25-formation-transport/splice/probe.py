"""Compare a visible cluster anchor on identical fixed-cohort SUMO trials."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from random_cohorts import make_tape, SPANS
from run_study import REQUIRED, OPTIONAL, ROOT, ROADS

REVISION = "e186b8a"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(obj):
    return sha(json.dumps(obj, sort_keys=True).encode())


def prepare(out, models):
    files = (*REQUIRED, *OPTIONAL)
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)
        for name in files:
            p = source / name
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(subprocess.check_output(
                ["git", "show", f"{REVISION}:variants/phase5g_pure_formation/{name}"], cwd=ROOT))
        for mode in ("base", "unit", "group", "retained_front"):
            if mode == "unit":
                subprocess.run(["git", "apply", "--no-index", "--whitespace=nowarn",
                                str(HERE/"visible_anchor.patch")], cwd=source, check=True)
            elif mode == "group":
                path = source/"noa/native_rules.py"
                old = b"ANCHOR_WEIGHT_BY_GROUP = False"
                assert path.read_bytes().count(old) == 1
                path.write_bytes(path.read_bytes().replace(old, b"ANCHOR_WEIGHT_BY_GROUP = True"))
            elif mode == "retained_front":
                path = source/"noa/native_rules.py"
                lines = path.read_bytes().splitlines(keepends=True)
                i, = [i for i in range(1,len(lines)) if lines[i].strip()==b"if anchor is not None:"
                      and b"command, next_memory = _solo_follow" in lines[i-1]]
                lines[i] = lines[i].replace(b"if anchor is not None:", b"if anchor is not None and "
                                            b"command.reference is None and command.lane is None:")
                path.write_bytes(b"".join(lines))
            if mode in models:
                dest = out/"frozen"/mode
                shutil.copytree(source, dest)
                (dest/"tmp").mkdir()
    shutil.copyfile(HERE.parent/"measure.py", out/"frozen/measure.py")
    manifest = {mode: {name: sha((out/"frozen"/mode/name).read_bytes()) for name in files} for mode in models}
    manifest["evaluator_sha256"] = sha((out/"frozen/measure.py").read_bytes())
    manifest["patch_sha256"] = sha((HERE/"visible_anchor.patch").read_bytes())
    manifest["base_revision"] = REVISION
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2))


def tape_for(road, count, profile, seed):
    if profile in ("demo12", "chain24"):
        from run_study import cohort_tape
        lanes = int(road[0])
        assert count == (12 if profile=="demo12" else 24)
        tree = ast.parse((ROOT/"runrun.py").read_text(encoding="utf-8-sig"))
        table, = [node.value for node in tree.body if isinstance(node,ast.Assign) and
                  any(isinstance(t,ast.Name) and t.id=="DEMO_ENTRY_LANES" for t in node.targets)]
        # The two-lane table is written as a tuple multiplied by six.
        def literal(node):
            if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Mult):
                return literal(node.left)*literal(node.right)
            return ast.literal_eval(node)
        entry = {literal(k):literal(v) for k,v in zip(table.keys,table.values)}[lanes]
        return cohort_tape("stream" if profile=="demo12" else profile, lanes, entry)
    if road == "2to3" and profile == "compact":
        # Two lanes need at least 100 / 220 m for twelve / twenty-four cars
        # at the fixed same-lane 20 m floor. Leave room for uneven occupancy.
        SPANS[count]["two_lane_compact"] = 20*(count//2)+5
        return make_tape(seed, road, count, "two_lane_compact")
    if profile in ("compact", "long"):
        return make_tape(seed, road, count, profile)
    # Identical legal 3-lane blocks at cruise, with a controlled empty interval.
    assert road == "3to2" and count % 6 == 0 and profile in ("split100", "split260")
    gap = int(profile.removeprefix("split"))
    spacing = 5.5 + .85*28.8
    block = [dict(lane=i%3, x=650-spacing*(i//3 + (i%3 == 1)*.5), speed=28.8)
             for i in range(count//2)]
    offset = 650-min(v["x"] for v in block)+gap
    return block + [dict(v, x=v["x"]-offset) for v in block]


def gap_values(states):
    xs = sorted(s[0] for s in states.values())
    return [b-a for a,b in itertools.pairwise(xs)]


def run_cell(out, cell):
    mode, road, n, profile, seed, length = cell
    n, seed, length = map(int, (n, seed, length))
    source = out/"frozen"/mode
    sys.path.insert(0, str(source))
    from experiments import native_sumo as native, complete_layers
    from noa import native_rules, staggered, transport
    modules = (native, complete_layers, native_rules, staggered, transport)
    loaded = {m.__name__.replace(".", "/")+".py": Path(m.__file__).resolve() for m in modules}
    assert native.ROOT == source and all(p == source/name for name,p in loaded.items())
    scenario = ROADS[road][1]
    up, down, exits = native.ROAD_LAYOUT[scenario]
    assert (up, down) == (1600,1000)
    native.ROAD_LAYOUT[scenario] = length,down,exits
    tape = tape_for(road,n,profile,seed)
    home = out/"_".join(cell)
    folder = native.run_case(mode="transform", scenario=scenario, seed=seed, flow=1750, duration=8.,
                             initial=tape, output_base=home, gui=False)
    result = json.loads((folder/"result.json").read_bytes())
    source_sig = {name:sha(p.read_bytes()) for name,p in loaded.items()}
    manifest = json.loads((out/"manifest.json").read_bytes())
    assert all(source_sig[name] == manifest[mode][name] for name in loaded)
    assert all(val == result["source_sha256"][name] for name,val in source_sig.items()
               if name in result["source_sha256"])
    assert "noa/native_rules.py" in result["source_sha256"]
    spec = importlib.util.spec_from_file_location("fixed_measure", out/"frozen/measure.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    assert audit.road_layout(folder) == [(int(road[0]), length), (int(road[-1]),1000)]
    report = audit.measure(folder, cohort=True)
    row = dict(mode=mode, road=road, n=n, profile=profile, seed=seed, upstream_m=length,
               tape_sha=digest(tape), source_sha=digest(source_sig), status=result["status"],
               completed=result["completed"], collisions=result["collisions"], teleports=result["teleports"],
               net_lane_crossings=result["lane_changes"], same_ids_peak=report["paired_peak"]["size"])
    for side in ("upstream", "downstream"):
        for key in ("whole_hold_s", "first_whole_s", "peak_size"):
            row[side+"_"+key] = report[side][key]
    for stage in ("formation", "transform"):
        moves = report.get(stage+"_moves")
        for k in ("min_total_crossings","min_max_crossings"):
            row[stage+"_"+k] = moves[k] if moves else None
        for k in ("total","max_per_car"):
            row[stage+"_"+k] = moves["midpoint"][k] if moves else None
    vmax = 0.
    first_front = None
    row.update(first_connected_s=None, max_gap_initial_m=None, initial_gaps_50_100=None,
               initial_gaps_100_200=None, initial_gaps_over200=None, min_max_gap_up_m=None,
               last_max_gap_up_m=None, first_whole_travel_m=None)
    with gzip.open(folder/"positions.jsonl.gz","rt") as stream:
        entries = {}
        for frame in map(json.loads,stream):
            states, t = frame["states"],frame["time_s"]
            if profile=="demo12" and len(entries)<n:
                for key,state in states.items():
                    entries.setdefault(key,(t,*state))
            vmax = max([vmax]+[s[2] for s in states.values()])
            if len(states) != n:
                continue
            front = max(s[0] for s in states.values())
            if front >= length-200:
                continue
            gaps = gap_values(states)
            maximum = max(gaps)
            if first_front is None:
                first_front = front
                if profile=="demo12":
                    # The staggered GUI departures enter in successive real frames.
                    assert len(entries)==n
                    row["entry_states_sha"] = digest(entries)
                else:
                    assert all(max(abs(a-b) for a,b in zip(states[f"initial_{i}"][:3],
                         (v["x"],(v["lane"]+.5)*3.3,v["speed"]))) < 1.e-5 for i,v in enumerate(tape))
                row.update(first_frame_sha=digest(states), first_frame_s=t, max_gap_initial_m=round(maximum,3),
                           initial_gaps_50_100=sum(50<g<=100 for g in gaps),
                           initial_gaps_100_200=sum(100<g<=200 for g in gaps),
                           initial_gaps_over200=sum(g>200 for g in gaps), min_max_gap_up_m=round(maximum,3))
            row["min_max_gap_up_m"] = min(row["min_max_gap_up_m"],round(maximum,3))
            row["last_max_gap_up_m"] = round(maximum,3)
            if maximum <= 50 and row["first_connected_s"] is None:
                row["first_connected_s"] = t
            if t == row["upstream_first_whole_s"]:
                row["first_whole_travel_m"] = round(front-first_front,1)
    row["max_speed_m_s"] = round(vmax,4)
    assert first_front is not None
    (home/"row.json").write_text(json.dumps(row, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--models",nargs="+",choices=("base","unit","group","retained_front"),default=["base","unit","group"])
    p.add_argument("--roads",nargs="+",choices=ROADS,default=list(ROADS))
    p.add_argument("--seeds",nargs="+",default=["7607"])
    p.add_argument("--counts",nargs="+",default=["12","24"])
    p.add_argument("--lengths",nargs="+",default=["1600","2800","4000"])
    p.add_argument("--profiles",nargs="+",choices=("long","compact","split100","split260","demo12","chain24"),default=["long"])
    p.add_argument("--workers",type=int,default=8)
    p.add_argument("--cell",nargs=6,help=argparse.SUPPRESS)
    a=p.parse_args()
    out=a.out.resolve()
    if a.cell:
        return run_cell(out,a.cell)
    for road,n,profile,seed in itertools.product(a.roads,a.counts,a.profiles,a.seeds):
        tape_for(road,int(n),profile,int(seed))
    out.mkdir(parents=True,exist_ok=False)
    prepare(out,a.models)
    cells=list(itertools.product(a.models,a.roads,a.counts,a.profiles,a.seeds,a.lengths))
    def execute(cell):
        with (out/("_".join(cell)+".log")).open("wb") as f:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),"--out",str(out),"--cell",*cell],
                           check=True,stdout=f,stderr=subprocess.STDOUT)
        return json.loads((out/"_".join(cell)/"row.json").read_bytes())
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(execute,cells))
    for _, paired in itertools.groupby(sorted(rows,key=lambda r:tuple(r[k] for k in
             ("road","n","profile","seed","upstream_m"))),key=lambda r:tuple(r[k] for k in
             ("road","n","profile","seed","upstream_m"))):
        batch = list(paired)
        if batch[0]["profile"]=="demo12":
            assert len({(r["entry_states_sha"],r["tape_sha"]) for r in batch}) == 1
        else:
            assert len({(r["first_frame_sha"],r["first_frame_s"],r["tape_sha"]) for r in batch}) == 1
    with (out/"summary.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "runs, matched actual first frames")


if __name__=="__main__":
    main()
