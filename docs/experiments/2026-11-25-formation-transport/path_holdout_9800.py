"""Reproduce the paired retained/continuous-path holdout on seeds 9801..9806."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
from run_study import REQUIRED, OPTIONAL, ROADS
from splice.probe import tape_for

ORIGINALS = {"retained":ROOT/"tmp/nov25study/retained_product_demo/source",
             "path":ROOT/"tmp/nov25-alternating-path/frozen/path"}
EVALUATOR = ROOT/"tmp/nov25-alternating-path/frozen/measure.py"
FILES = (*REQUIRED,*OPTIONAL)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def digest(obj):
    return sha(json.dumps(obj,sort_keys=True).encode())


def cell(out,model,road,n,profile,seed):
    key=f"{road}_{n}_{profile}_{seed}"
    source=out/"frozen"/model
    manifest=json.loads((out/"manifest.json").read_bytes())
    sys.path.insert(0,str(source))
    from experiments import native_sumo as native, complete_layers
    from noa import native_rules,staggered,transport
    for mod in (native,complete_layers,native_rules,staggered,transport):
        name=mod.__name__.replace(".","/")+".py"
        assert Path(mod.__file__).resolve()==source/name
        assert sha((source/name).read_bytes())==manifest[model][name]
    assert native.ROOT==source
    scenario=ROADS[road][1]
    old,down,exits=native.ROAD_LAYOUT[scenario]
    assert (old,down)==(1600,1000)
    native.ROAD_LAYOUT[scenario]=2800,down,exits
    tape=json.loads((out/"tapes"/(key+".json")).read_bytes())
    home=out/(model+"_"+key)
    folder=native.run_case(mode="transform",scenario=scenario,seed=seed,flow=1750,duration=8.,
                           initial=tape,output_base=home,gui=False)
    result=json.loads((folder/"result.json").read_bytes())
    assert all(manifest[model][k]==h for k,h in result["source_sha256"].items())
    with gzip.open(folder/"positions.jsonl.gz","rt") as f:
        first=json.loads(next(f))
    state=first["states"]
    assert len(state)==n and first["time_s"]==.1
    for i,car in enumerate(tape):
        assert max(abs(a-b) for a,b in zip(state[f"initial_{i}"][:3],(car["x"],(car["lane"]+.5)*3.3,car["speed"])))<1e-6
    sp=importlib.util.spec_from_file_location("path_holdout_measure",out/"frozen/measure.py")
    measure=importlib.util.module_from_spec(sp);sp.loader.exec_module(measure)
    assert measure.road_layout(folder)==[(int(road[0]),2800.),(int(road[-1]),1000.)]
    report=measure.measure(folder,cohort=True)
    (home/"measure.json").write_text(json.dumps(report),encoding="utf-8")
    (home/"index.json").write_text(json.dumps(dict(model=model,road=road,n=n,profile=profile,seed=seed,
        run=folder.name,tape_sha=digest(tape),frame_sha=digest(first),route_sha=sha((folder/"native.rou.xml").read_bytes()),
        network_shape=measure.road_layout(folder),complete=report["completed"],safe=report["safe"])))


def physical_cases():
    return list(itertools.product(("2to3","3to2"),(12,24),("long","compact"),range(9801,9807)))


def pack(out,archive):
    names=["manifest.json","frozen/measure.py"]
    names.extend(f"frozen/{model}/{name}" for model in ORIGINALS for name in FILES)
    names.extend(f"tapes/{road}_{n}_{profile}_{seed}.json" for road,n,profile,seed in physical_cases())
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(out/name,name)
    print("Packed frozen native runner, evaluator and all 48 physically indexed tapes:",archive)


def run(out,workers,archive=None,prepare_only=False):
    out.mkdir(parents=True,exist_ok=False)
    (out/"tapes").mkdir();manifest={}
    physical=physical_cases()
    z=zipfile.ZipFile(archive) if archive else None
    for model,original in ORIGINALS.items():
        dst=out/"frozen"/model
        manifest[model]={}
        for name in FILES:
            target=dst/name;target.parent.mkdir(exist_ok=True,parents=True)
            target.write_bytes(z.read(f"frozen/{model}/{name}") if z else (original/name).read_bytes())
            manifest[model][name]=sha(target.read_bytes())
        (dst/"tmp").mkdir(exist_ok=True)
    differences=[k for k in FILES if manifest["path"][k]!=manifest["retained"][k]]
    assert differences==["noa/staggered.py"]
    evaluator=z.read("frozen/measure.py") if z else EVALUATOR.read_bytes()
    (out/"frozen/measure.py").write_bytes(evaluator)
    manifest["evaluator_sha"]=sha(evaluator)
    if z:
        assert json.loads(z.read("manifest.json"))==manifest
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    for road,n,profile,seed in physical:
        name=f"tapes/{road}_{n}_{profile}_{seed}.json"
        if z:
            (out/name).write_bytes(z.read(name))
        else:
            (out/name).write_text(json.dumps(tape_for(road,n,profile,seed),indent=2))
    if z:
        z.close()
    if prepare_only:
        return
    jobs=[(model,*part) for part in physical for model in ORIGINALS]
    def one(job):
        name="_".join(map(str,job))
        with (out/(name+".log")).open("xb") as log:
            subprocess.run([sys.executable,"-E","-B",str(Path(__file__).resolve()),"--out",str(out),
                            "--cell",*map(str,job)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        print(name,flush=True)
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one,jobs))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--workers",type=int,default=6)
    p.add_argument("--cell",nargs=5)
    p.add_argument("--inputs",type=Path,help="Use the archived sources and fixed tapes")
    p.add_argument("--prepare-only",action="store_true",help="Verify and materialize the fixed inputs only")
    p.add_argument("--pack",type=Path,help="Archive an already prepared run")
    args=p.parse_args()
    if args.cell:
        model,road,n,profile,seed=args.cell
        cell(args.out.resolve(),model,road,int(n),profile,int(seed))
    elif args.pack:
        pack(args.out.resolve(),args.pack)
    else:
        run(args.out.resolve(),args.workers,args.inputs,args.prepare_only)
