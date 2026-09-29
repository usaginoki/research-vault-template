# Research vault template

An Obsidian vault for literature research with Claude Code: candidate papers in a backlog,
PDF → docling extraction of text, figures and tables, one note per paper, living answers per research
question, and dated session summaries. Everything is plain markdown + properties, browsed through
Obsidian Bases.

## Start a new research vault
1. On GitHub: **Use this template → Create a new repository**, then clone it.
2. `uv sync` (installs docling with CPU-only torch; ~1.5 GB in `.venv/`).
3. Open the folder as a vault in Obsidian (Bases is a core plugin; no community plugins needed).
4. In Claude Code, describe your research question and sub-questions. `CLAUDE.md` tells Claude how to
   run a literature-review session (clarify → parallel search → backlog → extraction → paper notes →
   question notes → session summary).

## Layout
```
Papers/       processed papers          Templates/   Paper, Candidate, Question, Session
Questions/    one note per question      _tools/      extract_all.py, extract.py, pick_figure.sh,
Sessions/     research-session summaries              check_vault.py, citations.py,
                                         README.md (conventions)
Backlog/      candidate papers           Papers.base, Backlog.base   live tables
Attachments/  PDFs (ignored) + figures   Backlog.md   backlog hub
```

Conventions (properties, tags, topics, workflow): [`_tools/README.md`](_tools/README.md).

## Tools
| command | does |
|---|---|
| `uv run _tools/extract_all.py [citekey …]` | download + extract every paper note / `status: processing` candidate missing from the cache |
| `_tools/pick_figure.sh <key> <fig.png>` | copy an extracted figure into `Attachments/<key>/` and print its embed |
| `uv run _tools/citations.py [--forward] [--add-min N]` | fill `cites` / `cited_by` / `cited_by_count` from Semantic Scholar + PDF text; report papers cited by several of yours but not in the vault |
| `python3 _tools/check_vault.py` | check properties, question tags, candidate status, duplicate arXiv ids, links and embeds |

## Obsidian settings included
- `Templates/`, `_tools/`, `.venv/` are excluded files; `Backlog/` is filtered out of the graph and
  unresolved links are hidden, so the graph shows papers, questions and sessions.
- Graph colour groups by note type; attachment folder `Attachments/`; templates folder `Templates/`.
- Obsidian skills from [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) in `.claude/skills/`.
