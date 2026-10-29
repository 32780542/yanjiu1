"""Merge the three screened lists and render a traceable literature catalogue."""
from collections import Counter
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
GROUPS = ("A_acc", "B_formation", "C_merge")
RANK = {"metadata": 0, "abstract": 1, "full_text": 2}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_title(value):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", html.unescape(value)).encode("ascii", "ignore").decode().lower())


def normalize_doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", (value or "").strip(), flags=re.I).lower()


def build():
    groups, duplicates, inputs = [], [], {}
    correction_path = ROOT / "catalog_corrections.json"
    corrections = read(correction_path) if correction_path.exists() else {}
    for folder in GROUPS:
        path = ROOT / folder / "papers.json"
        rows = read(path)
        inputs[folder] = dict(records=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for row in rows:
            row = dict(row, source_group=folder)
            row.update(corrections.get(row["local_id"], {}))
            if isinstance(row["authors"], list):
                row["authors"] = "; ".join(row["authors"])
            row["doi"] = normalize_doi(row.get("doi")) or None
            if row["doi"]:
                assert re.fullmatch(r"10\.\d{4,9}/\S+", row["doi"]), row
            assert row["access_level"] in RANK and row["primary_url"].startswith("http"), row
            assert 1900 <= row["year"] <= 2026, row
            assert "\ufffd" not in json.dumps(row, ensure_ascii=False), row["local_id"]
            match = next((group for group in groups if any(
                row["doi"] and row["doi"] == existing["doi"] or
                not (row["doi"] and existing["doi"]) and
                normalize_title(row["title"]) == normalize_title(existing["title"])
                for existing in group)), None)
            if match is None:
                groups.append([row])
            else:
                match.append(row)

    papers = []
    for index, versions in enumerate(groups, 1):
        best = max(versions, key=lambda row: (RANK[row["access_level"]], len(row["evidence_locator"])))
        paper = {key: value for key, value in best.items() if key not in ("source_group", "local_id")}
        paper.update(id=f"L{index:03d}", source_ids=[r["local_id"] for r in versions],
                     source_groups=sorted({r["source_group"] for r in versions}),
                     reading_provenance=[{key: r.get(key) for key in (
                         "source_group", "local_id", "primary_url", "abstract_url", "access_level",
                         "reading_scope", "evidence_locator", "information_requirement", "transfer_idea_zh"
                     )} for r in versions])
        paper["doi"] = next((r["doi"] for r in versions if r["doi"]), None)
        paper["information_requirements"] = sorted({r["information_requirement"] for r in versions})
        if len(versions) > 1:
            duplicates.append(dict(retained_id=paper["id"], source_ids=paper["source_ids"], title=paper["title"]))
        papers.append(paper)

    checks_path = ROOT / "crossref_checks.json"
    checks = read(checks_path) if checks_path.exists() else {}
    retry_path = ROOT / "crossref_retry.json"
    if retry_path.exists():
        checks.update(read(retry_path))
    for paper in papers:
        evidence = checks.get(paper["doi"])
        if evidence:
            paper["crossref_verification"] = evidence
        if paper["doi"] == "10.3141/1999-09":
            paper["metadata_note"] = "Crossref/出版社短题名不含NGSIM副标题；DOI、作者、年份和正文主题一致，非错配。"
        if paper["doi"] == "10.16383/j.aas.c190052":
            paper["publisher_verification"] = dict(
                url="https://aas.net.cn/cn/article/doi/10.16383/j.aas.c190052?viewType=HTML",
                container_title="Acta Automatica Sinica", authors=["Li Gao", "Li-Ping Lu", "Duan-Feng Chu", "Yong Zhang", "Chao-Zhong Wu"],
                verified="自动化学报2020,46(1):117–126；中英文题名、作者及DOI已在期刊官网核对。",
                note="Crossref API 404；期刊官网可读，不能把Crossref无记录理解为DOI无效。")
    (ROOT / "papers.json").write_text(json.dumps(papers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = dict(unique_papers=len(papers), input_records=sum(x["records"] for x in inputs.values()),
                 duplicates_removed=sum(x["records"] for x in inputs.values()) - len(papers),
                 duplicate_groups=duplicates, input_files=inputs,
                 reading_levels=dict(Counter(p["access_level"] for p in papers)),
                 with_DOI=sum(bool(p["doi"]) for p in papers),
                 metadata_only=[p["id"] for p in papers if p["access_level"] == "metadata"],
                 crossref_resolved=sum(p.get("crossref_verification", {}).get("status") == "ok" for p in papers))
    (ROOT / "catalog_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ("id", "title", "authors", "year", "doi", "primary_url", "access_level", "information_requirement",
              "relevance", "abstract_summary_zh", "transfer_idea_zh", "limitation_zh", "evidence_locator")
    with (ROOT / "papers.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in papers)
    levels = {"metadata": "仅书目", "abstract": "摘要/预览", "full_text": "正文重点章节"}
    catalogue = ["# 去重文献目录", "", f"共{len(papers)}篇；正文重点章节、摘要/预览和仅书目分别标注。完整内容及阅读定位见papers.json或papers.csv。", ""]
    for row in papers:
        catalogue.extend([f"## {row['id']} · {row['title']}", "",
            f"{row['authors']}，{row['year']}。[{row['doi'] or '原始来源'}]({row['primary_url']})。阅读：{levels[row['access_level']]}；信息条件：{', '.join(row['information_requirements'])}。", "",
            row["abstract_summary_zh"], "", "与当前方法的联系：" + row["transfer_idea_zh"], "",
            "适用边界：" + row["limitation_zh"], ""])
    (ROOT / "文献目录.md").write_text("\n".join(catalogue), encoding="utf-8")
    bib = []
    for row in papers:
        cr = row.get("crossref_verification", {})
        if cr.get("status") != "ok":
            cr = row.get("publisher_verification", cr)
        people = cr.get("authors") or row["authors"].split(";")
        authors = " and ".join(p.strip().replace("et al.", "and others") for p in people)
        title = html.unescape(row["title"]).replace("&", "\\&")
        kind = {"proceedings-article": "inproceedings", "book-chapter": "incollection"}.get(cr.get("type"), "article" if row["doi"] else "misc")
        bib.extend([f"@{kind}{{{row['id']},", f"  title = {{{{{title}}}}},",
                    f"  author = {{{authors}}},", f"  year = {{{row['year']}}},"])
        container = "booktitle" if kind in ("inproceedings", "incollection") else "journal"
        for key, value in ((container, cr.get("container_title")), ("doi", row["doi"]), ("url", row["primary_url"])):
            if value:
                text = html.unescape(str(value))
                if key in ("journal", "booktitle"):
                    text = text.replace("&", r"\&")
                bib.append(f"  {key} = {{{text}}},")
        bib.extend(["}", ""])
    (ROOT / "references.bib").write_text("\n".join(bib), encoding="utf-8")
    print(json.dumps({key: audit[key] for key in ("unique_papers", "input_records", "duplicates_removed", "reading_levels", "with_DOI", "crossref_resolved")}, ensure_ascii=False))


if __name__ == "__main__":
    build()
