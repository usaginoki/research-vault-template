"""Download a paper PDF and extract text, tables and figures with docling.

Usage:
    uv run _tools/extract.py <citekey> <pdf_url_or_path> [--max-pages N]

Outputs:
    Attachments/<citekey>/<citekey>.pdf          original PDF (kept in the vault)
    .cache/docling/<citekey>/<citekey>.md        full markdown, figures referenced as PNGs
    .cache/docling/<citekey>/figures.md          index: figure file -> page -> caption
    .cache/docling/<citekey>/tables.md           every table as markdown with its caption

Figures worth embedding in a note are then copied manually from the cache into
Attachments/<citekey>/ (see _tools/pick_figure.sh).
"""

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent


def download(src: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(src).exists():
        shutil.copy(src, dest)
        return
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 (thesis-lit-review)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    if dest.read_bytes()[:4] != b"%PDF":
        dest.unlink()
        sys.exit(f"Downloaded file from {src} is not a PDF")


def convert(pdf: Path, out: Path, key: str, max_pages: int | None) -> None:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

    opts = PdfPipelineOptions()
    opts.do_ocr = False  # born-digital PDFs; OCR is slow and unnecessary
    opts.do_table_structure = True
    opts.generate_picture_images = True
    opts.images_scale = 2.0
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})

    kwargs = {"page_range": (1, max_pages)} if max_pages else {}
    doc = converter.convert(str(pdf), **kwargs).document

    out.mkdir(parents=True, exist_ok=True)
    doc.save_as_markdown(out / f"{key}.md", image_mode=ImageRefMode.REFERENCED, artifacts_dir=Path("md_images"))

    fig_lines, tab_lines = ["| file | page | caption |", "|---|---|---|"], []
    figdir = out / "figs"
    figdir.mkdir(exist_ok=True)
    n_fig = n_tab = 0
    for item, _ in doc.iterate_items():
        page = item.prov[0].page_no if item.prov else "?"
        if isinstance(item, PictureItem):
            img = item.get_image(doc)
            if img is None or min(img.size) < 80:  # skip icons/logos
                continue
            n_fig += 1
            name = f"fig-{n_fig:02d}-p{page}.png"
            img.save(figdir / name)
            cap = item.caption_text(doc).replace("\n", " ").replace("|", "\\|")
            fig_lines.append(f"| {name} | {page} | {cap[:300]} |")
        elif isinstance(item, TableItem):
            n_tab += 1
            cap = item.caption_text(doc).replace("\n", " ")
            tab_lines += [f"## Table {n_tab} (page {page})", f"Caption: {cap}", "", item.export_to_markdown(doc), ""]
    (out / "figures.md").write_text("\n".join(fig_lines) + "\n")
    (out / "tables.md").write_text("\n".join(tab_lines) + "\n")
    print(f"{key}: {n_fig} figures, {n_tab} tables -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("src")
    ap.add_argument("--max-pages", type=int, default=None)
    a = ap.parse_args()
    pdf = VAULT / "Attachments" / a.key / f"{a.key}.pdf"
    download(a.src, pdf)
    convert(pdf, VAULT / ".cache" / "docling" / a.key, a.key, a.max_pages)


if __name__ == "__main__":
    main()
