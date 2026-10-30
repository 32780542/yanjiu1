"""Rebuild exact trial rules from one Git blob and six published patches."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[3]
DOCS = Path(__file__).resolve().parent
BASE = "8ed11d90ac457269b2175e20aec5ba1bbba8a318"
RULE = "variants/phase5g_pure_formation/noa/native_rules.py"
EXPECTED = {
    "T": "046f00aa397b7f4ff306f3fbb796c97565b743550a9dae608572e88f5a8cc02b",
    "M": "a23321ebae6f291994275e6239f47c585eeabd36b844d6b2879e81955340839c",
    "R": "cba7c9a1fb74c25192fed4765c75626bb78117c0a5c6e3f1a6dfb9b9166f722d",
    "T2": "5f452480f54b701fa564e8a45c6384bb4d432cdccbee24b285c7f3a4e589e34f",
    "TM": "65142b448412325357bab0bdcdc6fa6caaa75cddef2c6a498ab4d49454441317",
    "TR": "2acc9fb989801581ddc555c683eafb6c80916a12ab1810c45c2507cfd6c36f3a",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True)
    if result.returncode:
        raise SystemExit(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="fresh Git-ignored folder inside this repository")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = (args.output or REPO / "tmp/literature_trials/reproduce" / stamp).resolve()
    if not output.is_relative_to(REPO) or output == REPO:
        parser.error("--output must be inside this repository")
    if output.exists():
        parser.error("--output already exists; choose a fresh folder")
    relative = output.relative_to(REPO).as_posix()
    if subprocess.run(["git", "check-ignore", "-q", "--", relative], cwd=REPO).returncode:
        parser.error("--output must be Git-ignored, for example under tmp/")
    before = sha(REPO / RULE)
    base = git("show", BASE + ":" + RULE)
    output.mkdir(parents=True, exist_ok=False)
    candidates = {}
    for name, expected in EXPECTED.items():
        path = output / name / "noa/native_rules.py"
        path.parent.mkdir(parents=True)
        parent = base if name in ("T", "M", "R") else Path(candidates["T"]["path"]).read_bytes()
        path.write_bytes(parent)
        strip = 1 if name in ("T2", "TR") else 3
        git("apply", "--whitespace=nowarn", f"-p{strip}",
            "--directory=" + relative + "/" + name, str(DOCS / name / "rules.patch"))
        actual = sha(path)
        if actual != expected:
            raise SystemExit(f"{name}: SHA256 mismatch: expected {expected}, got {actual}")
        candidates[name] = dict(path=str(path), sha256=actual)
    after = sha(REPO / RULE)
    if after != before:
        raise SystemExit("Production rule hash changed during reconstruction")
    report = dict(base_commit=BASE, output=str(output), candidates=candidates,
                  core_sha256_before=before, core_sha256_after=after)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (output / "manifest.json").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
