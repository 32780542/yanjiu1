"""Read-only DOI metadata check against Crossref; abstracts are not copied."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
import html
import json
from pathlib import Path
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from build_catalog import normalize_title

ROOT = Path(__file__).resolve().parent
papers = json.loads((ROOT / "papers.json").read_bytes())
records = {}


def check(paper):
    url = "https://api.crossref.org/works/" + quote(paper["doi"], safe="/")
    try:
        request = Request(url, headers={"User-Agent": "formation-literature-review/1.0"})
        with urlopen(request, timeout=15) as response:
            value = json.load(response)["message"]
        title = html.unescape(re.sub("<[^>]+>", "", (value.get("title") or [""])[0]))
        result = dict(status="ok", api_url=url, doi=value.get("DOI"), title=title,
                      title_similarity=SequenceMatcher(None, normalize_title(paper["title"]), normalize_title(title)).ratio(),
                      authors=[" ".join((person.get("given", ""), person.get("family", ""))).strip()
                               for person in value.get("author", [])],
                      container_title=(value.get("container-title") or [""])[0],
                      published_online=value.get("published-online", {}).get("date-parts"),
                      published_print=value.get("published-print", {}).get("date-parts"),
                      issued=value.get("issued", {}).get("date-parts"), type=value.get("type"),
                      checked_utc=datetime.now(timezone.utc).isoformat())
    except Exception as error:
        result = dict(status="unavailable", api_url=url, error=str(error),
                      checked_utc=datetime.now(timezone.utc).isoformat())
    time.sleep(.15)
    return paper["doi"], result


with ThreadPoolExecutor(max_workers=3) as pool:
    futures = [pool.submit(check, p) for p in papers if p["doi"]]
    for future in as_completed(futures):
        doi, result = future.result()
        records[doi] = result
        if len(records) % 25 == 0:
            print(json.dumps(dict(checked=len(records))), flush=True)
(ROOT / "crossref_checks.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(checked=len(records), resolved=sum(r["status"] == "ok" for r in records.values()),
                      mismatches=[doi for doi, r in records.items() if r["status"] == "ok" and r["title_similarity"] < .88]), ensure_ascii=False))
