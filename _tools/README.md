# Vault conventions & workflow

## Folders
| folder / file | contents |
|---|---|
| `Papers/` | one note per processed paper (`Templates/Paper.md`) |
| `Questions/` | one note per research question, the living answer (`Templates/Question.md`) |
| `Sessions/` | one summary per research session, a dated snapshot (`Templates/Session.md`) |
| `Backlog/` + `Backlog.md` | one properties-only note per candidate paper (`Templates/Candidate.md`) + hub with views |
| `Attachments/<citekey>/` | PDFs (git-ignored) and the figures embedded in paper notes |
| `Papers.base`, `Backlog.base` | Obsidian Bases: live tables of papers / candidates, embedded in other notes |
| `.cache/docling/<citekey>/` | full docling extraction (hidden from Obsidian, git-ignored) |
| `_tools/` | extraction and checking scripts (excluded from Obsidian) |

## Processing a paper (candidate → paper)
Papers enter the vault as candidate notes in `Backlog/` (see *Backlog*). To process one:
1. In its candidate note set `status: processing`, check `citekey` (`FirstAuthorSurnameYEAR`, ASCII,
   add `a`/`b` if the key is already used in `Papers/`) and `pdf_url`.
2. `uv run _tools/extract_all.py` → PDF in `Attachments/<key>/`, docling output in `.cache/docling/<key>/`
   (`<key>.md` full text, `figures.md` caption index, `tables.md` all tables, `figs/*.png`).
   Long PDFs are cut at 45 pages. Pass citekeys as arguments to (re-)extract specific papers.
3. Pick figures: `_tools/pick_figure.sh <key> fig-03-p5.png` → prints the `![[...]]` embed.
4. **Promote the same note**: move it to `Papers/`, rename to `<key> - <Short title>`, replace
   `type/candidate` with `type/paper` (+ `relevance/…`, facet tags), delete `status`/`priority`/`why`,
   add the remaining `Templates/Paper.md` properties (`questions`, `pdf`, `peer_reviewed`…) and body.
   Keep `found_by`/`cited_by`: they record where the paper came from. Obsidian updates links on rename.
5. Link it from the relevant `Questions/*.md` and summarise the session in `Sessions/` (see below).
6. `python3 _tools/check_vault.py` to verify properties, links and embeds.

## Paper note properties
| property | values |
|---|---|
| `title`, `citekey`, `authors`, `year` | |
| `published` | `YYYY-MM-DD` (arXiv v1 or journal date) |
| `venue` | e.g. `ICLR 2026`, `Nature`, `arXiv preprint` |
| `peer_reviewed` | `true` / `false` / `workshop` |
| `url`, `arxiv`/`doi`, `pdf`, `pdf_url` | `pdf: "[[<key>.pdf]]"`; `pdf_url` is what `extract_all.py` downloads |
| `topics` | list of topic slugs (a paper can serve several topics) |
| `questions` | list of question ids, e.g. `[Q1, Q2]` |
| `relevance` | `core` / `adjacent`; what counts as core is defined per topic (see Topics) |

## Topics
A topic is a research thread with its own questions. Every paper, question, session and candidate
note carries `topics: [...]`. Start a new topic by adding a row here and creating its question notes
from `Templates/Question.md`.

| topic slug | questions | `core` means |
|---|---|---|
| *(add your first topic)* | Q1–… | *(e.g. "X is manipulated **and** Y is measured")* |

## Tags (nested; add new leaves freely, keep the prefixes)
Generic (every topic):
- `type/` paper · candidate · question · session · backlog
- `relevance/` core · adjacent
- `q/` 1 · 2 · 3-1 … (question `Q3.1` → tag `q/3-1`; new question → new `q/…` + note in `Questions/`)
- `subject/` what was studied (e.g. `llm`, `agent`, `human`)

Topic-specific facets: add a prefix per topic when useful (e.g. `method/`, `dataset/`, `stressor/`)
and list its values here so later notes reuse them.

## Question notes
`Questions/Qx <short name>.md` from `Templates/Question.md`, properties `id: Qx`, `topics`, tags
`type/question`, `q/x`. Question ids are global across topics: keep numbering upward. Cite papers inline as
`[[<citekey> - <short title>|Author et al. YEAR]]` (inside tables escape the pipe: `\|`). Each embeds
`![[Papers.base#This question]]`, which lists every paper whose `questions` contains the note's `id`.

## Session notes
Each research session gets a summary in `Sessions/YYYY-MM-DD <Topic> - <kind>.md` from
`Templates/Session.md`: properties `date`, `session`, `topics`, `questions` plus matching `q/…` tags
and `type/session`, and a "Questions addressed" callout at the top. Session notes are snapshots; the
living answers are in `Questions/`.

## Backlog
One note per candidate in `Backlog/`, properties only (`Templates/Candidate.md`), browsed through the
views in `Backlog.base` (embedded in `Backlog.md`, in session notes and in every paper note).

| property | values |
|---|---|
| `status` | `candidate` → `processing` → *(promoted to `Papers/`)* · `rejected` (+ `reason`) |
| `priority` | 1 = process next · 2 = relevant · 3 = peripheral / background |
| `topics`, `relevance` | as for papers; `relevance` is the first guess (core / adjacent) |
| `manipulation`, `outcome`, `why` | what the paper varies, what it measures, one-line reason |
| `found_by` | provenance tags such as `search/<strand>` |
| `cited_by` | links to processed papers whose reference lists include it (feeds the *Cited by this paper* view) |
| `pdf_url`, `url`, `arxiv`, `citekey`, `published`, `added` | |

Filenames are `<citekey> - <short title>`. Rejected candidates stay with `status: rejected` so later
searches don't resurface them. Before adding a candidate, search the vault for its arXiv id
(`check_vault.py` also flags duplicate arXiv ids). `Backlog/` is hidden from the graph (`-path:Backlog`).

## Citations
`uv run _tools/citations.py` fetches each paper's full reference list from Semantic Scholar (cached in
`.cache/citations/`) and matches it against `Papers/` and `Backlog/` by arXiv id, DOI or title. It owns
these properties (recomputed on every run, don't edit by hand):
- papers: `cites` (vault notes it cites), `cited_by` + `cited_by_count` (processed papers citing it)
- candidates: `cited_by` (merged with hand-added entries) + `cited_by_count`

It also prints references *not* in the vault that several processed papers cite (backward snowball;
`--add-min N` turns those cited by ≥ N papers into candidate notes with `found_by: [citations/backward]`),
and with `--forward` papers citing several processed papers. Views: `Backlog.base#Most cited`,
`Papers.base#Most cited in vault`. Rerun after processing new papers. Set `S2_API_KEY` (in `~/.zshrc` or a
git-ignored `.env`) to use a Semantic Scholar API key; without one it paces requests at 1 per 3 s.


## Git
PDFs (`Attachments/**/*.pdf`) and the docling cache (`.cache/`) are git-ignored (most papers may not be
redistributed). After a fresh clone run `uv sync && uv run _tools/extract_all.py` to re-download and
re-extract them from each note's `pdf_url`. PDFs behind bot protection (e.g. SSRN) must be saved
manually to `Attachments/<key>/<key>.pdf` first; the script then reuses them.
