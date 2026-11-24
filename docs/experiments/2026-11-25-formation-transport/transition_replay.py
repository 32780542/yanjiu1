"""Rebuild a transition stage from compact archived sources and replay fixed SUMO inputs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import itertools
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from path_holdout_9800 import FILES, cell

HERE = Path(__file__).resolve().parent


def prepare(out, stages, cases, source=None):
    out.mkdir(parents=True, exist_ok=False)
    (out / "tapes").mkdir()
    base_path = HERE / "path_holdout_9800_inputs.zip"
    manifest = {}
    with ZipFile(base_path) as base, ZipFile(HERE/"transition_overlays.zip") as archive:
        original = json.loads(base.read("manifest.json"))
        overlay = json.loads(archive.read("manifest.json"))
        assert sha256(base_path.read_bytes()).hexdigest() == overlay["base_zip_sha256"]
        for name in stages:
            directory = out/"frozen"/name
            (directory/"tmp").mkdir(parents=True)
            overlay_files = {} if source else overlay[name]
            hashes = dict(original["path"], **overlay_files)
            for key in FILES:
                if source:
                    data = (source/key).read_bytes()
                    hashes[key] = sha256(data).hexdigest()
                else:
                    data = (archive.read(name+"/"+key) if key in overlay_files else
                            base.read("frozen/path/"+key))
                assert sha256(data).hexdigest() == hashes[key]
                target = directory/key
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
            manifest[name] = hashes
        evaluator = base.read("frozen/measure.py")
        manifest["evaluator_sha"] = sha256(evaluator).hexdigest()
        assert manifest["evaluator_sha"] == original["evaluator_sha"]
        (out/"frozen/measure.py").write_bytes(evaluator)
        for road,n,profile,seed in cases:
            key = f"tapes/{road}_{n}_{profile}_{seed}.json"
            (out/key).write_bytes(base.read(key))
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out",type=Path)
    p.add_argument("--stage",choices=("cumulative","staged","subflow","current"),default="subflow")
    p.add_argument("--source",type=Path,help="Use with --stage current to test a new controller snapshot")
    p.add_argument("--roads",nargs="+",choices=("2to3","3to2"),default=["2to3","3to2"])
    p.add_argument("--sizes",nargs="+",type=int,choices=(12,24),default=[12,24])
    p.add_argument("--profiles",nargs="+",choices=("compact","long"),default=["compact","long"])
    p.add_argument("--seeds",nargs="+",type=int,choices=range(9801,9807),default=range(9801,9807))
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--cell",nargs=5)
    args = p.parse_args()
    out = args.out.resolve()
    if args.cell:
        stage,road,n,profile,seed = args.cell
        return cell(out,stage,road,int(n),profile,int(seed))
    if (args.stage == "current") != bool(args.source):
        p.error("--source and --stage current must be used together")
    cases = list(itertools.product(args.roads,args.sizes,args.profiles,args.seeds))
    prepare(out,[args.stage],cases,args.source)
    def run(case):
        key = "_".join(map(str,case))
        with (out/(key+".log")).open("x",encoding="utf8") as log:
            subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),str(out),"--cell",
                            args.stage,*map(str,case)],check=True,stdout=log,stderr=subprocess.STDOUT)
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(run,cases))
    print(len(cases),"native runs, see each measure.json")


if __name__ == "__main__":
    main()
