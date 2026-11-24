"""Hold the gate and arrival tape fixed while varying actual SUMO downstream road length."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from run_study import REQUIRED, OPTIONAL, ROADS, ROOT


def freeze_sources(dest, source=None):
    """Recover the archived candidate byte-for-byte, including the original Windows line endings."""
    hashes = {}
    with ZipFile(Path(__file__).with_name("moment_development_inputs.zip")) as archive:
        reference = json.loads(archive.read("manifest.json"))
        for name in (*REQUIRED, *OPTIONAL):
            if source is not None:
                payload = (source / name).read_bytes()
            elif name in archive.namelist():
                payload = archive.read(name)
            else:
                payload = subprocess.check_output(
                    ["git", "show", "7bdeaca:variants/phase5g_pure_formation/" + name], cwd=ROOT
                )
                if hashlib.sha256(payload).hexdigest() != reference[name]:
                    payload = payload.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            hashes[name] = hashlib.sha256(payload).hexdigest()
            if hashes[name] != reference[name]:
                raise ValueError(f"Frozen candidate fingerprint differs: {name}")
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    return hashes


def simulate(out, cell):
    road, raw_seed, raw_length = cell
    seed, length = int(raw_seed), int(raw_length)
    source = out / "source"
    sys.path.insert(0, str(source))
    from experiments import native_sumo as native
    from noa import native_rules, staggered, transport

    for module in (native, native_rules, staggered, transport):
        name = module.__name__.replace(".", "/") + ".py"
        if Path(module.__file__).resolve() != source / name:
            raise RuntimeError("Wrong runtime module: " + str(module.__file__))
    scenario = ROADS[road][0]
    up, old_down, retained = native.ROAD_LAYOUT[scenario]
    assert (up, old_down) == (1000, 200)
    native.ROAD_LAYOUT[scenario] = (up, length, retained)
    outside = out / "_".join(cell)
    folder = native.run_case(
        mode="transform",
        scenario=scenario,
        seed=seed,
        flow=1750,
        duration=1200,
        gui=False,
        output_base=outside,
    )
    report = json.loads((folder / "result.json").read_bytes())
    frozen = json.loads((out / "manifest.json").read_bytes())["source_sha256"]
    assert all(frozen[k] == v for k, v in report["source_sha256"].items())
    from measure import road_layout

    assert road_layout(folder) == [(int(road[0]), up), (int(road[-1]), length)]
    (outside / "complete.json").write_text(
        json.dumps(dict(folder=folder.name, status=report["status"]))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, help="Use an exact local copy of the archived moment candidate"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", default=["9301", "9302"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--case", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.case:
        return simulate(out, args.case)
    out.mkdir(parents=True, exist_ok=False)
    dest = out / "source"
    hashes = freeze_sources(dest, args.source)
    (dest / "tmp").mkdir()
    (out / "manifest.json").write_text(
        json.dumps(
            dict(
                source_sha256=hashes,
                seeds=args.seeds,
                flow=1750,
                demand_s=1200,
                up_m=1000,
                down_m=[200, 1000],
            ),
            indent=2,
        )
    )

    def launch(cell):
        with (out / ("_".join(cell) + ".log")).open("wb") as stream:
            subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--out", str(out), "--case", *cell],
                check=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )

    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(launch, itertools.product(("3to4", "4to3"), args.seeds, ("200", "1000"))))
    print("Completed fixed-demand road-length runs.")


if __name__ == "__main__":
    main()
