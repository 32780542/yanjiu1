"""Retry only rate-limited DOI checks; retain the original acquisition record."""
from datetime import datetime, timezone
from difflib import SequenceMatcher
import html
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from build_catalog import normalize_title

ROOT = Path(__file__).resolve().parent
old = json.loads((ROOT / "crossref_checks.json").read_bytes())
papers = json.loads((ROOT / "papers.json").read_bytes())
retried = {}
for paper in papers:
    first = old.get(paper["doi"], {})
    if first.get("status") != "unavailable" or "429" not in first.get("error", ""):
        continue
    request = Request(first["api_url"], headers={"User-Agent": "formation-literature-review/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            value = json.load(response)["message"]
        title = html.unescape(re.sub("<[^>]+>", "", (value.get("title") or [""])[0]))
        record = dict(status="ok", api_url=first["api_url"], doi=value["DOI"], title=title,
                      title_similarity=SequenceMatcher(None, normalize_title(paper["title"]), normalize_title(title)).ratio(),
                      authors=[" ".join((a.get("given", ""), a.get("family", ""))).strip() for a in value.get("author", [])],
                      container_title=(value.get("container-title") or [""])[0],
                      published_online=value.get("published-online", {}).get("date-parts"),
                      published_print=value.get("published-print", {}).get("date-parts"),
                      issued=value.get("issued", {}).get("date-parts"), type=value.get("type"),
                      checked_utc=datetime.now(timezone.utc).isoformat(), first_attempt=first)
    except Exception as error:
        record = dict(first, retry_error=str(error), retry_utc=datetime.now(timezone.utc).isoformat())
    retried[paper["doi"]] = record
    time.sleep(1)
(ROOT / "crossref_retry.json").write_text(json.dumps(retried, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(dict(retried=len(retried), resolved=sum(r["status"] == "ok" for r in retried.values()))))
