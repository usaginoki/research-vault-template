"""Citation links between vault notes, from Semantic Scholar reference lists.

For every note in Papers/ it fetches the full reference list (cached in .cache/citations/), matches
references against Papers/ and Backlog/ notes by arXiv id, DOI or title, and writes:
  - Papers:   `cites` (vault notes it cites), `cited_by` + `cited_by_count` (processed papers citing it)
  - Backlog:  `cited_by` (merged with existing entries) + `cited_by_count`
These properties are owned by this script; re-running it recomputes them.

References come from Semantic Scholar plus a full-text scan of the local PDF (arXiv ids and titles of
vault notes), which covers papers whose S2 reference list is empty or incomplete.

It also reports references that are NOT in the vault but are cited by several processed papers
(backward snowballing) and, with --forward, papers citing several processed papers (forward
snowballing). `--add-min N` turns backward suggestions cited by >= N papers into candidate notes.

Usage:
    uv run _tools/citations.py                 # fetch missing, update properties, print report
    uv run _tools/citations.py --refresh       # re-fetch all reference lists
    uv run _tools/citations.py --forward       # also fetch citing papers (slow, more requests)
    uv run _tools/citations.py --add-min 3     # create candidates for refs cited by >= 3 papers
    uv run _tools/citations.py --dry-run       # report only, write nothing to notes

Set S2_API_KEY to use a Semantic Scholar API key (faster, fewer 429s); works without one.
"""

import argparse
import collections
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

VAULT = Path(__file__).resolve().parent.parent
CACHE = VAULT / ".cache" / "citations"
API = "https://api.semanticscholar.org/graph/v1/paper"
FIELDS = "title,externalIds,year"
KEY = os.environ.get("S2_API_KEY")
DELAY = 1.1 if KEY else 3.0  # seconds between requests
TODAY = datetime.date.today()

# ---------- notes ----------

def split(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    fm, _, body = text[4:].partition("\n---\n")
    return fm, body


def props(path: Path) -> dict:
    return yaml.safe_load(split(path.read_text())[0]) or {}


def norm_title(t: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (t or "").lower()))


def norm_arxiv(a) -> str:
    m = re.search(r"\d{4}\.\d{4,5}", str(a or ""))
    return m.group(0) if m else ""


def ext_arxiv(ext: dict) -> str:
    """arXiv id from S2 externalIds, including DOIs of the form 10.48550/arXiv.XXXX.XXXXX."""
    doi = str(ext.get("DOI") or "")
    return norm_arxiv(ext.get("ArXiv")) or (norm_arxiv(doi) if "arxiv" in doi.lower() else "")


def set_prop(text: str, key: str, value) -> str:
    """Replace (or insert before `tags:`) one frontmatter property, leaving the rest untouched."""
    fm, body = split(text)
    lines, out, skip = fm.split("\n"), [], False
    for ln in lines:  # drop the existing key and its list items
        if skip and (ln.startswith("- ") or ln.startswith("  ")):
            continue
        skip = False
        if re.match(rf"^{re.escape(key)}:", ln):
            skip = True
            continue
        out.append(ln)
    if value in (None, [], 0) and key != "cited_by_count":
        new = []
    elif isinstance(value, list):
        new = [f"{key}:"] + [f"  - \"{v}\"" for v in value]
    else:
        new = [f"{key}: {value}"]
    idx = next((i for i, ln in enumerate(out) if ln.startswith("tags:")), len(out))
    out[idx:idx] = new
    return "---\n" + "\n".join(out) + "\n---\n" + body


class Vault:
    def __init__(self):
        self.notes = {}  # note name -> (path, props)
        self.by_arxiv, self.by_doi, self.by_title = {}, {}, {}
        for folder in ("Papers", "Backlog"):
            for p in sorted((VAULT / folder).glob("*.md")):
                fm = props(p)
                name = p.stem
                self.notes[name] = (p, fm)
                if a := norm_arxiv(fm.get("arxiv")):
                    self.by_arxiv[a] = name
                if d := str(fm.get("doi") or "").lower():
                    self.by_doi[d] = name
                if t := norm_title(fm.get("title")):
                    self.by_title[t] = name

    def match(self, ref: dict) -> str | None:
        ext = ref.get("externalIds") or {}
        if (a := ext_arxiv(ext)) and a in self.by_arxiv:
            return self.by_arxiv[a]
        if (d := str(ext.get("DOI") or "").lower()) and d in self.by_doi:
            return self.by_doi[d]
        return self.by_title.get(norm_title(ref.get("title")))

    def in_text(self, key: str, self_name: str) -> set[str]:
        """Vault notes cited in the paper's PDF text: arXiv ids, or titles of >= 5 words."""
        pdf = VAULT / "Attachments" / key / f"{key}.pdf"
        if not pdf.exists():
            return set()
        import pypdfium2
        doc = pypdfium2.PdfDocument(str(pdf))
        raw = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
        text = " " + norm_title(raw.replace("-\n", "")) + " "
        hits = {self.by_arxiv[a] for a in re.findall(r"\d{4}\.\d{4,5}", raw) if a in self.by_arxiv}
        hits |= {n for t, n in self.by_title.items() if len(t.split()) >= 5 and f" {t} " in text}
        hits.discard(self_name)
        return hits

    def papers(self):
        return [(n, p, fm) for n, (p, fm) in self.notes.items() if p.parent.name == "Papers"]


# ---------- Semantic Scholar ----------

def s2_id(fm: dict) -> str | None:
    if a := norm_arxiv(fm.get("arxiv")):
        return f"arXiv:{a}"
    if d := fm.get("doi"):
        return f"DOI:{d}"
    return None


_last = [0.0]


def get(url: str) -> dict | None:
    for attempt in range(6):
        wait = _last[0] + DELAY - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"x-api-key": KEY} if KEY else {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(60, 5 * 2 ** attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(min(60, 5 * 2 ** attempt))
    print(f"  giving up on {url}", file=sys.stderr)
    return None


def fetch_all(pid: str, edge: str) -> list[dict] | None:
    """edge = 'references' (citedPaper) or 'citations' (citingPaper); follows pagination."""
    inner = "citedPaper" if edge == "references" else "citingPaper"
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"fields": FIELDS, "limit": 1000, "offset": offset})
        data = get(f"{API}/{urllib.parse.quote(pid, safe=':')}/{edge}?{q}")
        if data is None:
            return None if not out else out
        out += [d[inner] for d in data.get("data") or [] if d.get(inner)]
        if data.get("next") is None:
            return out
        offset = data["next"]


def cached(key: str, pid: str, edge: str, refresh: bool) -> list[dict] | None:
    f = CACHE / f"{key}.{edge}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text())
    items = fetch_all(pid, edge)
    if items is not None:
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(items, indent=1))
    return items


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--forward", action="store_true")
    ap.add_argument("--add-min", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    v = Vault()
    papers = v.papers()
    print(f"{len(papers)} papers, {len(v.notes) - len(papers)} candidates; "
          f"{'API key' if KEY else 'no API key'} ({DELAY}s between requests)")

    cites = {}                                   # paper note -> set(vault notes)
    external = collections.defaultdict(set)      # external ref id -> citing paper notes
    ext_info = {}
    forward = collections.defaultdict(set)
    missing = []
    for i, (name, path, fm) in enumerate(papers, 1):
        key, pid = fm.get("citekey") or name.split(" - ")[0], s2_id(fm)
        refs = (cached(key, pid, "references", a.refresh) if pid else None) or []
        text_hits = v.in_text(key, name)
        if not refs and not text_hits:
            missing.append(name)
            print(f"[{i}/{len(papers)}] {key}: no reference data")
            continue
        s2_hits = {m for r in refs if (m := v.match(r)) and m != name}
        hit = s2_hits | text_hits
        cites[name] = hit
        for r in refs:
            if v.match(r):
                continue
            ext = r.get("externalIds") or {}
            rid = ext_arxiv(ext) or str(ext.get("DOI") or "").lower() or norm_title(r.get("title"))
            if rid and (ext_arxiv(ext) or ext.get("DOI") or len(rid.split()) >= 4):
                external[rid].add(name)
                ext_info[rid] = r
        print(f"[{i}/{len(papers)}] {key}: {len(refs)} S2 refs -> {len(s2_hits)} in vault; "
              f"PDF text -> {len(text_hits)}; total {len(hit)}")
        if a.forward and pid:
            for c in cached(key, pid, "citations", a.refresh) or []:
                if v.match(c):
                    continue
                ext = c.get("externalIds") or {}
                cid = ext_arxiv(ext) or str(ext.get("DOI") or "").lower() or norm_title(c.get("title"))
                if cid:
                    forward[cid].add(name)
                    ext_info[cid] = c

    # reverse edges
    cited_by = collections.defaultdict(set)
    for src, tgts in cites.items():
        for t in tgts:
            cited_by[t].add(src)

    if not a.dry_run:
        changed = 0
        for name, (path, fm) in v.notes.items():
            text = path.read_text()
            new = text
            link = lambda ns: [f"[[{n}]]" for n in sorted(ns)]
            if path.parent.name == "Papers":
                if name in cites:
                    new = set_prop(new, "cites", link(cites[name]))
                new = set_prop(new, "cited_by", link(cited_by[name]))
                new = set_prop(new, "cited_by_count", len(cited_by[name]))
            else:
                old = {re.sub(r"^\[\[|\]\]$", "", str(x)) for x in fm.get("cited_by") or []}
                allc = old | cited_by[name]
                if allc:
                    new = set_prop(new, "cited_by", link(allc))
                new = set_prop(new, "cited_by_count", len(allc))
            if new != text:
                path.write_text(new)
                changed += 1
        print(f"\nupdated {changed} notes")

    # report
    def show(title, table):
        rows = sorted(table.items(), key=lambda kv: -len(kv[1]))[: a.top]
        rows = [r for r in rows if len(r[1]) >= 2]
        print(f"\n## {title} ({len(rows)} shown, cited by >= 2 processed papers)")
        for rid, srcs in rows:
            r = ext_info[rid]
            print(f"  {len(srcs):>2}x  {r.get('title')} ({r.get('year')})  [{rid}]")

    ranked = sorted(((n, len(cited_by[n])) for n, (p, _) in v.notes.items() if p.parent.name == "Backlog"),
                    key=lambda x: -x[1])
    print("\n## Backlog candidates most cited by processed papers")
    for n, c in ranked[:15]:
        if c:
            print(f"  {c:>2}x  {n}")
    show("Not in vault: cited by processed papers (backward)", external)
    if a.forward:
        show("Not in vault: citing processed papers (forward)", forward)
    if missing:
        print("\nno reference data (add manually):", ", ".join(missing))

    if a.add_min and not a.dry_run:
        made = 0
        for rid, srcs in external.items():
            if len(srcs) < a.add_min:
                continue
            r = ext_info[rid]
            ext = r.get("externalIds") or {}
            arx = ext_arxiv(ext)
            surname = "Anon"  # author names are not fetched; rename after checking
            year = r.get("year") or ""
            short = re.sub(r'[\[\]#^|\\/:?*"<>]', " ", (r.get("title") or rid).split(":")[0])[:60].strip()
            fname = VAULT / "Backlog" / f"{surname}{year} - {short}.md"
            if fname.exists():
                continue
            fm = {"title": r.get("title"), "year": year or None,
                  "url": f"https://arxiv.org/abs/{arx}" if arx else (f"https://doi.org/{ext['DOI']}" if ext.get("DOI") else None),
                  "arxiv": arx or None, "doi": ext.get("DOI"), "pdf_url": f"https://arxiv.org/pdf/{arx}" if arx else None,
                  "topics": [], "status": "candidate", "priority": 2,
                  "why": f"cited by {len(srcs)} processed papers", "found_by": ["citations/backward"],
                  "cited_by": [f"[[{s}]]" for s in sorted(srcs)], "cited_by_count": len(srcs),
                  "added": TODAY, "tags": ["type/candidate"]}
            fm = {k: x for k, x in fm.items() if x not in (None, "")}
            fname.write_text("---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000) + "---\n")
            made += 1
        print(f"\ncreated {made} candidate notes (set topics/citekey/author before processing)")


if __name__ == "__main__":
    main()
