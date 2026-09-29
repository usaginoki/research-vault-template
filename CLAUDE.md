# Research vault: instructions for Claude

This repo is an Obsidian vault for literature research. Conventions, properties, tags and the paper
workflow are in `_tools/README.md`; read it before creating or editing notes. Use the
`obsidian-markdown` and `obsidian-bases` skills (in `.claude/skills/`) for Obsidian syntax.

## Running a literature-review session
When the user gives a research question with sub-questions:

1. **Clarify & set up the topic.** Ask about scope (core vs adjacent), depth (number of papers to fully
   process), and anything ambiguous. Add the topic row to the *Topics* table in `_tools/README.md`
   (slug, question ids, what `core` means) and create one note per sub-question in `Questions/`
   (continue the global question numbering). Add topic-specific facet tags to the README if useful.
2. **Search in parallel strands.** Launch a few search subagents, each on one angle of the topic. Each
   returns a verified table (title, first author+year, arXiv/DOI, PDF URL, date, venue, core/adjacent,
   manipulation, outcome, why relevant, priority 1–3). Snowball through references and citing papers
   (Semantic Scholar API) and include the newest work.
3. **Create candidate notes** in `Backlog/` for every result (`Templates/Candidate.md`; merge
   duplicates by arXiv id, then by near-identical title; `found_by: [search/<strand>]`). Mark the ones
   chosen for full processing `status: processing`.
4. **Extract**: `uv run _tools/extract_all.py` (docling, CPU; ~1 min per paper, 2 in parallel).
5. **Write paper notes** with subagents, a few papers each, using the brief below. Promote each
   candidate note into `Papers/` (see README). Relevant references found in these papers become new
   candidate notes with `cited_by: ["[[<paper note>]]"]`.
6. **Citations**: `uv run _tools/citations.py` links papers and candidates (`cites`, `cited_by`,
   `cited_by_count`) and reports frequently cited papers missing from the vault; raise the priority of
   candidates cited by many processed papers and consider adding the reported ones.
7. **Synthesise**: write each question note from the papers' "Relevance to research questions"
   sections (cite with wikilinks, add comparison tables, gaps), then a session note in `Sessions/`
   from `Templates/Session.md`.
8. **Verify**: `python3 _tools/check_vault.py` must report no problems; spot-check a few numbers
   against `.cache/docling/<key>/<key>.md`.

## Brief for paper-note subagents
- Read `_tools/README.md`, `Templates/Paper.md` and one existing paper note (if any) as the style
  reference; match its structure and depth.
- Read the docling output (`.cache/docling/<key>/<key>.md`, `figures.md`, `tables.md`). Look at
  candidate figure PNGs to read exact numbers; copy 2–4 key figures with `_tools/pick_figure.sh` and
  embed them with an italic caption line; include the 1–2 most relevant tables as markdown.
- Verify metadata (title, authors, v1 date, venue, peer-review status) against arXiv/OpenReview.
- Write one "Relevance to research questions" subsection per tagged question, each ending with a link
  to the question note. `questions:` and `q/…` tags must agree. `relevance: core` only if the topic's
  definition of core is met.
- Be faithful: only numbers seen in the text/figures; mark values read off plots with "~"; quote the
  paper's own definitions.
- Final report: per paper the note path, questions tagged, 1-line key finding, then NEW CANDIDATES
  (relevant references not yet in the vault: title, first author+year, arXiv id, why).

## Git
PDFs and `.cache/` are git-ignored. Commit or push only when the user asks.
