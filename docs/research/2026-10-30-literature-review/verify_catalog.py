"""Offline checks for bibliographic consistency and the published handoff."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
read = lambda path: json.loads(path.read_text(encoding="utf-8"))
papers, audit = read(BASE / "papers.json"), read(BASE / "catalog_audit.json")
assert len(papers) == audit["unique_papers"] == 150
assert {p["id"] for p in papers} == {f"L{i:03d}" for i in range(1, 151)}
dois = [p["doi"] for p in papers if p["doi"]]
assert len(dois) == len(set(dois)) == 141
assert Counter(p["access_level"] for p in papers) == {"full_text": 31, "abstract": 116, "metadata": 3}
assert sum(len(p["source_ids"]) for p in papers) == 153
assert len({sid for p in papers for sid in p["source_ids"]}) == 153
assert all(p["primary_url"].startswith("http") and p["evidence_locator"] for p in papers)
assert not any("\ufffd" in json.dumps(p, ensure_ascii=False) for p in papers)
for group, record in audit["input_files"].items():
    raw = (BASE / group / "papers.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == record["sha256"]
    assert len(json.loads(raw)) == record["records"]
by_id = {p["id"]: p for p in papers}
assert by_id["L134"]["year"] == 2014 and by_id["L134"]["metadata_correction"]
resolved = [p for p in papers if p.get("crossref_verification", {}).get("status") == "ok"]
assert len(resolved) == 140
for paper in resolved:
    cr = paper["crossref_verification"]
    assert cr["doi"].lower() == paper["doi"]
    assert cr["title_similarity"] >= .88 or paper["doi"] == "10.3141/1999-09"
assert by_id["L078"]["publisher_verification"]["container_title"] == "Acta Automatica Sinica"

with (BASE / "papers.csv").open(encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == 150
for row, paper in zip(rows, papers):
    assert row["id"] == paper["id"] and row["title"] == paper["title"]
    assert row["year"] == str(paper["year"]) and row["doi"] == (paper["doi"] or "")
bib = (BASE / "references.bib").read_text(encoding="utf-8")
entries = re.findall(r"^@\w+\{(L\d{3}),", bib, re.MULTILINE)
assert len(entries) == 150 and set(entries) == set(by_id)
depth = 0
for index, char in enumerate(bib):
    if index and bib[index - 1] == "\\":
        continue
    depth += (char == "{") - (char == "}")
    assert depth >= 0
assert depth == 0

report = (BASE / "文献结论与方法建议.md").read_text(encoding="utf-8")
references = re.findall(r"\[(L\d{3})[^\]]*\]\(([^)]+)\)", report)
assert references
verified_alternate = {
    "L104": "https://akesting.de/download/MOBIL_TRR_2007.pdf",
    "L062": "https://pure.tue.nl/ws/portalfiles/portal/322278322/1-s2.0-S2405896323008261-main.pdf",
}
for key, url in references:
    paper = by_id[key]
    allowed = [paper["primary_url"], paper.get("abstract_url", ""), verified_alternate.get(key, "")]
    if paper["doi"]:
        allowed.append("https://doi.org/" + paper["doi"])
    assert url.lower() in [u.lower() for u in allowed], (key, url)
    assert paper["access_level"] != "metadata", key
local_links = 0
for document in [BASE / "README.md", BASE / "文献结论与方法建议.md", ROOT / "README.md"]:
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "#")):
            continue
        path = document.parent / unquote(target.split("#")[0])
        assert path.exists(), (str(document), str(path))
        local_links += 1

subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "runrun.py", "variants/phase5g_pure_formation"], cwd=ROOT, check=True)
result = dict(passed=True, unique_papers=150, source_records=153, removed_duplicates=3,
              body_sections=31, abstracts_or_previews=116, metadata_only=3,
              DOI_records=141, Crossref_confirmed=140, journal_confirmed=1,
              csv_records=150, BibTeX_records=150, report_citations_checked=len(references),
              local_links_checked=local_links, production_code_unchanged=True,
              simulations_run=False, bibliography_year_correction_checked=True)
(BASE / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
