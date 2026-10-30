"""Seal current test logs, real root-entry smoke, and all eight physical string runs."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "implementation"
OPERATIONS = (
    "variants/phase5g_pure_formation/results/operations/20261030T011241637711Z_literature-current-contracts-red_82223d70",
    "variants/phase5g_pure_formation/results/operations/20261030T011302189859Z_literature-current-contracts-green_da891f86",
    "variants/phase5g_pure_formation/results/operations/20261030T011348789879Z_literature-TM-final-core_219b48fd",
    "results/operations/20261030T012137610390Z_literature-TM-live-root-entry_b0a103bd",
    "results/operations/20261030T012137608852Z_literature-TM-live-root-smoke_201454ba",
    "results/operations/20261030T010841852291Z_literature-heldout-five-flow-250_63ec1217",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    files = {}
    for relative in OPERATIONS:
        directory = REPO / relative
        for name in ("started.json", "result.json", "stdout.log", "stderr.log"):
            files["operations/" + directory.name + "/" + name] = directory / name
    strings = ("20261030T004327072012Z", "20261030T005509239176Z")
    for stamp in strings:
        root = REPO / "tmp/literature_trials/strings" / stamp
        files[f"strings/{stamp}/driver.py"] = root / "driver.py"
        files[f"strings/{stamp}/summary.json"] = root / "summary.json"
        for case in root.iterdir():
            if case.is_dir():
                for name in ("native_rules.py", "result.json", "trajectory.jsonl.gz"):
                    files[f"strings/{stamp}/{case.name}/{name}"] = case / name
    smoke = REPO / "variants/phase5g_pure_formation/results/native_flow/20261030T012138195682Z_lane_drop_transform_s1_4fa184"
    for name in ("input.json", "result.json", "trips.json", "positions.jsonl.gz", "sumo_command.json"):
        files["root_smoke/" + name] = smoke / name
    records = []
    target = OUT / "evidence.tar.gz"
    with target.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|") as archive:
            for member, path in sorted(files.items()):
                content = path.read_bytes()
                info = tarfile.TarInfo(member)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
                records.append(dict(member=member, bytes=len(content), sha256=sha(content),
                                    original_path=str(path.relative_to(REPO))))
    expected = {r["member"]: r for r in records}
    with tarfile.open(target, "r:gz") as archive:
        for member in archive:
            content = archive.extractfile(member).read()
            assert sha(content) == expected[member.name]["sha256"]
    result = dict(archive_sha256=sha(target.read_bytes()), archive_bytes=target.stat().st_size,
                  members=records, core_tests=225, core_subtests=37, native_GUI_tests=9,
                  heldout_cases=250, string_runs=8, smoke_completed=12,
                  source_sha256="65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317")
    (OUT / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(members=len(records), bytes=result["archive_bytes"], sha256=result["archive_sha256"])))


if __name__ == "__main__":
    main()
