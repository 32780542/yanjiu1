"""Verify the current method, published tables, local links and exact artifact hashes."""
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RULE = "variants/phase5g_pure_formation/noa/native_rules.py"
EXPECTED = "65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    current = (REPO / RULE).read_bytes()
    assert digest(current) == EXPECTED
    base = subprocess.check_output(["git", "show", "8ed11d9:" + RULE], cwd=REPO)
    nodes = lambda raw: {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(raw).body
                         if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    before, after = nodes(base), nodes(current)
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"_following", "_fill", "_decide"}
    assert set(after) - set(before) == {"_front_following", "cf_speed"}
    data = json.loads((HERE / "results/summary.json").read_text(encoding="utf-8"))
    assert data["cases"] == data["eligible"] == 250
    lookup = {(r["profile"], int(r["flow"])): r for r in data["profiles"] if r["scenario"] == "lane_drop"}
    report = (HERE / "研究结果与采用说明.md").read_text(encoding="utf-8")
    checks = 0

    def check_table(header, columns, tolerance):
        nonlocal checks
        lines = report.splitlines()
        start = lines.index(header) + 2
        for offset, flow in enumerate((500, 750, 1000, 1250, 1500)):
            values = [float(cell.strip()) for cell in lines[start + offset].strip("|").split("|")]
            assert int(values[0]) == flow
            assert len(values) == len(columns) + 1
            for actual, (profile, metric, scale) in zip(values[1:], columns):
                assert abs(actual - lookup[profile, flow][metric] * scale) <= tolerance
                checks += 1

    check_table("| 流量 | 原编队时间 | 新编队时间 | 原编队燃油 | 新编队燃油 |", [
        ("base/transform", "mean_travel_time_s", 1), ("TM/transform", "mean_travel_time_s", 1),
        ("base/transform", "fuel_g_per_km", 1), ("TM/transform", "fuel_g_per_km", 1)], .000051)
    check_table("| 流量 | 新NOA时间 | 新编队时间 | 新NOA燃油 | 新编队燃油 |", [
        ("TM/noa", "mean_travel_time_s", 1), ("TM/transform", "mean_travel_time_s", 1),
        ("TM/noa", "fuel_g_per_km", 1), ("TM/transform", "fuel_g_per_km", 1)], .000051)
    check_table("| 流量 | 原编队参与率 / % | 新编队参与率 / % | 原平均连续1 / s | 新平均连续1 / s |", [
        ("base/transform", "flag_participation_rate", 100), ("TM/transform", "flag_participation_rate", 100),
        ("base/transform", "flag_mean_episode_s", 1), ("TM/transform", "flag_mean_episode_s", 1)], .000051)
    check_table("| 流量 | 新编队平均同时参与人数 | 各种子峰值人数的均值 |", [
        ("TM/transform", "flag_mean_participants", 1), ("TM/transform", "flag_peak_participants", 1)], .00051)
    cases = list(csv.DictReader((HERE / "evidence/heldout250_analysis/analysis_per_case.csv").open(encoding="utf-8-sig")))
    assert len(cases) == 250
    assert all(row["eligible"] == "True" for row in cases)
    artifact_checks = 0
    evidence = json.loads((HERE / "evidence/manifest.json").read_text(encoding="utf-8"))
    for name, expected in evidence["files"].items():
        path = HERE / "evidence" / name
        assert digest(path.read_bytes()) == expected["sha256"], name
        artifact_checks += 1
    implementation = json.loads((HERE / "implementation/manifest.json").read_text(encoding="utf-8"))
    archive_path = HERE / "implementation/evidence.tar.gz"
    assert digest(archive_path.read_bytes()) == implementation["archive_sha256"]
    expected_members = {r["member"]: r for r in implementation["members"]}
    implementation_checks = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            content = archive.extractfile(member).read()
            assert digest(content) == expected_members[member.name]["sha256"]
            assert len(content) == expected_members[member.name]["bytes"]
            if "final-core" in member.name and member.name.endswith("stdout.log"):
                assert b"225 passed, 37 subtests passed" in content
            if "live-root-entry" in member.name and member.name.endswith("stderr.log"):
                assert b"Ran 9 tests" in content and b"OK" in content
            if member.name == "root_smoke/result.json":
                smoke = json.loads(content)
                assert smoke["status"] == "drained" and smoke["completed"] == 12
                assert smoke["collisions"] == smoke["teleports"] == 0
                assert smoke["source_sha256"]["noa/native_rules.py"] == EXPECTED
            implementation_checks += 1
    assert implementation_checks == len(expected_members)
    documents = [REPO / "README.md", REPO / "docs/原生SUMO编队变换系统说明.md",
                 HERE / "README.md", HERE / "研究结果与采用说明.md"]
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO).decode("utf-8").split("\0"))
    link_checks = 0
    for path in documents:
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if link.startswith(("http:", "https:", "#")):
                continue
            target = (path.parent / unquote(link.split("#")[0])).resolve()
            assert target.exists(), (path, link)
            relative = target.relative_to(REPO).as_posix()
            assert relative in tracked or any(name.startswith(relative + "/") for name in tracked), (path, link, "not indexed")
            link_checks += 1
    png = (HERE / "figures/string_response.png").read_bytes()
    assert struct.unpack(">II", png[16:24]) == (3300, 2100)
    result = dict(passed=True, source_sha256=EXPECTED, changed_functions=sorted(changed),
                  cases=250, eligible=250, report_numeric_cells=checks,
                  evidence_file_hashes=artifact_checks, implementation_members=implementation_checks,
                  local_links=link_checks, figure_dimensions=[3300, 2100])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
