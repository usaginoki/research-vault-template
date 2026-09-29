"""Download + docling-extract every paper that needs it, reading PDF URLs from the notes themselves.

Targets: all notes in Papers/, plus Backlog/ notes with `status: processing`.
A note is skipped if it has no `pdf_url` or its docling cache already exists.

Usage:
    uv run _tools/extract_all.py                 # everything that is missing
    uv run _tools/extract_all.py Smith2024 …  # only these citekeys (re-extracts if cache exists)
"""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

VAULT = Path(__file__).resolve().parent.parent
MAX_PAGES = "45"
WORKERS = 2


def props(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}
    return yaml.safe_load(text[4:].split("\n---\n", 1)[0]) or {}


def targets(only: set[str]) -> list[tuple[str, str]]:
    notes = list((VAULT / "Papers").glob("*.md"))
    notes += [p for p in (VAULT / "Backlog").glob("*.md") if props(p).get("status") == "processing"]
    out = []
    for p in notes:
        fm = props(p)
        key, url = fm.get("citekey"), fm.get("pdf_url")
        if not key or not url:
            print(f"skip (no citekey/pdf_url): {p.name}")
            continue
        if only and key not in only:
            continue
        if not only and (VAULT / ".cache/docling" / key / "figures.md").exists():
            continue
        out.append((key, url))
    return out


def run(job: tuple[str, str]) -> str:
    key, url = job
    log = VAULT / ".cache" / f"log-{key}.txt"
    log.parent.mkdir(exist_ok=True)
    with open(log, "w") as f:
        rc = subprocess.run(["uv", "run", "_tools/extract.py", key, url, "--max-pages", MAX_PAGES],
                            cwd=VAULT, stdout=f, stderr=subprocess.STDOUT).returncode
    return f"{'OK  ' if rc == 0 else 'FAIL'} {key}" + ("" if rc == 0 else f"  (see {log.relative_to(VAULT)})")


if __name__ == "__main__":
    jobs = targets(set(sys.argv[1:]))
    print(f"{len(jobs)} paper(s) to extract")
    with ThreadPoolExecutor(WORKERS) as ex:
        for line in ex.map(run, jobs):
            print(line, flush=True)
