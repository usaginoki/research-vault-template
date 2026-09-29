"""Integrity check: required properties, questions<->q/ tag agreement, candidate notes,
duplicate arXiv ids, and that wikilinks and embeds resolve.

Usage: python3 _tools/check_vault.py
"""
import collections, glob, os, re

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(VAULT)
notes = {os.path.basename(p)[:-3] for p in glob.glob("**/*.md", recursive=True) if not p.startswith((".", "_tools"))}
files = {os.path.basename(p) for p in glob.glob("**/*", recursive=True) if os.path.isfile(p)}
PAPER_REQ = ["title", "authors", "year", "published", "venue", "peer_reviewed", "url", "pdf", "pdf_url",
             "topics", "questions", "relevance", "tags"]
CAND_REQ = ["title", "topics", "status", "tags"]
STATUSES = {"candidate", "processing", "rejected"}
problems = []
arxiv_ids = collections.defaultdict(list)


def frontmatter(s):
    return s[4:].split("\n---\n", 1)[0] if s.startswith("---\n") else ""


def prop(fm, key):
    m = re.search(rf"^{key}:\s*['\"]?([^'\"\n]*)", fm, re.M)
    return m.group(1).strip() if m else None


scan = glob.glob("Papers/*.md") + glob.glob("Questions/*.md") + glob.glob("Sessions/*.md") + glob.glob("Backlog/*.md") + ["Backlog.md"]
for p in sorted(scan):
    if not os.path.exists(p):
        continue
    s = open(p).read()
    fm = frontmatter(s)
    if p.startswith("Papers/"):
        for k in PAPER_REQ:
            if prop(fm, k) is None:
                problems.append(f"{p}: missing property {k}")
        qs = re.search(r"^questions:\s*\[(.*)\]", fm, re.M)
        qs = {q.strip() for q in qs.group(1).split(",")} if qs else set()
        tags = {t.replace("-", ".").upper() for t in re.findall(r"q/([\d-]+)", fm)}
        if {q.upper() for q in qs} != {"Q" + t for t in tags}:
            problems.append(f"{p}: questions {sorted(qs)} vs q/ tags {sorted(tags)}")
    if p.startswith("Backlog/"):
        for k in CAND_REQ:
            if prop(fm, k) is None:
                problems.append(f"{p}: missing property {k}")
        st = prop(fm, "status")
        if st not in STATUSES:
            problems.append(f"{p}: status {st!r} not in {sorted(STATUSES)} (processed papers belong in Papers/)")
        if st == "candidate" and prop(fm, "priority") not in {"1", "2", "3"}:
            problems.append(f"{p}: candidate needs priority 1-3")
        if st == "rejected" and not prop(fm, "reason"):
            problems.append(f"{p}: rejected candidate needs a reason")
    if p.startswith(("Papers/", "Backlog/")):
        a = prop(fm, "arxiv")
        if a and re.fullmatch(r"\d{4}\.\d{4,5}", a):
            arxiv_ids[a].append(p)
    s = re.sub(r"`[^`\n]*`", "", s)  # links inside inline code are not links
    for emb, tgt in re.findall(r"(!?)\[\[([^\]|#]+)", s):
        tgt = tgt.strip().rstrip("\\").strip()  # "\|" is an escaped alias pipe inside tables
        ok = tgt in notes or tgt in files or os.path.basename(tgt) in files or tgt + ".md" in files
        if not ok:
            problems.append(f"{p}: unresolved {'embed' if emb else 'link'} [[{tgt}]]")

for a, ps in arxiv_ids.items():
    if len(ps) > 1:
        problems.append(f"duplicate arXiv {a}: " + " | ".join(ps))

print("\n".join(problems) or "OK: no problems")
print(f"{len(glob.glob('Papers/*.md'))} paper notes, {len(glob.glob('Backlog/*.md'))} candidate notes checked")
