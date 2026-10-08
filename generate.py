#!/usr/bin/env python3
"""
DFL Poster - turn Markdown into print-ready lab documents.

    python generate.py doc.md                 # -> doc.html
    python generate.py doc.md --pdf           # -> doc.html + doc.pdf
    python generate.py doc.md -o out/ --size A3 --orientation landscape

See README.md for the full syntax (frontmatter, callouts, QR codes, quizzes).
"""

import argparse
import base64
import io
import re
import sys
from html import escape, unescape
from pathlib import Path

import frontmatter
import markdown
import qrcode
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
TEMPLATES_DIR = ROOT / "templates"
FONTS_DIR = ROOT / "fonts"

DOC_TYPES = {
    "poster":    "Poster",
    "induction": "Lab Induction",
    "howto":     "How-To",
    "stepguide": "Step-by-Step Guide",
}
DEFAULT_TYPE = "howto"

PAGE_SIZES = {
    "A3": ("297mm", "420mm"),
    "A4": ("210mm", "297mm"),
    "A5": ("148mm", "210mm"),
    "letter": ("215.9mm", "279.4mm"),
}

DEFAULT_DECLARATION = (
    "I confirm that I have read and understood this induction, that I have had the "
    "opportunity to ask questions, and that I will follow the procedures described."
)


# ---------------------------------------------------------------------------
# QR codes
# ---------------------------------------------------------------------------

def _qr_dataurl(url: str, box_size: int = 10, border: int = 2) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=box_size, border=border)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# [QR](url) or [QR: caption](url)  ->  <a href="url">QR</a> / <a href="url">QR: caption</a>
_QR_A = r'<a href="([^"]+)">QR(?:\s*:\s*(.*?))?</a>'
_QR_BLOCK_RE = re.compile(r'<p>\s*' + _QR_A + r'\s*</p>', re.S)
_QR_INLINE_RE = re.compile(_QR_A, re.S)


def _process_qr_links(doc: str) -> str:
    def _block(m):
        url, label = unescape(m.group(1)), (m.group(2) or "").strip()
        alt = escape(re.sub(r"<[^>]+>", "", label) or "QR code")
        caption = f'<div class="qr-caption">{label}</div>' if label else ""
        return (f'<div class="qr-block"><img class="qr" src="{_qr_dataurl(url, 8)}" '
                f'alt="{alt}">{caption}</div>')

    def _inline(m):
        url = unescape(m.group(1))
        return f'<img class="qr qr-inline" src="{_qr_dataurl(url, 8)}" alt="QR code">'

    return _QR_INLINE_RE.sub(_inline, _QR_BLOCK_RE.sub(_block, doc))


# ---------------------------------------------------------------------------
# Callouts:  > [!WARNING] Bold title        (title optional)
#            > Body text on following lines
# ---------------------------------------------------------------------------

_CALLOUT_KINDS = {
    "danger": "danger", "stop": "danger",
    "warning": "warning", "caution": "warning",
    "important": "important",
    "note": "note", "info": "note",
    "tip": "tip", "hint": "tip",
}
_CALLOUT_HEAD_RE = re.compile(
    r'\s*<p>\[!(\w+)\][ \t]*(.*?)(</p>|<br\s*/?>)\s*(.*?)\s*$', re.S)


def _process_callouts(doc: str) -> str:
    def _one(chunk: str) -> str:
        m = _CALLOUT_HEAD_RE.match(chunk)
        kind = _CALLOUT_KINDS.get(m.group(1).lower()) if m else None
        if not kind:
            return f"<blockquote>{chunk}</blockquote>"
        title, term, rest = m.group(2).strip(), m.group(3), m.group(4)
        if term != "</p>" and rest:          # body continues in the same paragraph
            rest = f"<p>{rest}"
        title_html = f'<span class="callout-title">{title}</span>' if title else ""
        body_html = f'<div class="callout-body">{rest}</div>' if rest.strip() else ""
        return (f'<div class="callout callout-{kind}"><div class="callout-head">'
                f'<span class="callout-label">{kind}</span>{title_html}</div>{body_html}</div>')

    def _blockquote(m):
        # Python-Markdown merges blockquotes separated by blank lines; split them apart again.
        chunks = re.split(r'(?=<p>\[!\w+\])', m.group(1))
        return "\n".join(_one(c) for c in chunks if c.strip())

    return re.sub(r'<blockquote>\s*(.*?)\s*</blockquote>', _blockquote, doc, flags=re.S)


# ---------------------------------------------------------------------------
# Quiz (induction only):  a "## ... Quiz" section
#   1. Question text
#      - [ ] wrong answer
#      - [x] right answer
#   2. A question with no options becomes a written-answer question
# ---------------------------------------------------------------------------

def _inline_md(text: str) -> str:
    return re.sub(r"^<p>(.*)</p>$", r"\1", markdown.markdown(text).strip(), flags=re.S)


def _extract_quiz(text: str):
    head = re.search(r"^##[ \t]+(.*\bquiz\b.*?)[ \t]*$", text, re.I | re.M)
    if not head:
        return text, None
    nxt = re.search(r"^##[ \t]+", text[head.end():], re.M)
    end = head.end() + nxt.start() if nxt else len(text)
    block = re.sub(r"^\s*---+\s*$", "", text[head.end():end], flags=re.M)

    q_re = re.compile(r"^\s*\d+[.)]\s+(.*\S)\s*$")
    o_re = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.*\S)\s*$")
    intro, questions = [], []
    for line in block.splitlines():
        if m := q_re.match(line):
            questions.append({"n": len(questions) + 1, "text": m.group(1), "options": []})
        elif (m := o_re.match(line)) and questions:
            questions[-1]["options"].append(
                {"text": _inline_md(m.group(2)), "correct": m.group(1).lower() == "x"})
        elif line.strip():
            if questions and not questions[-1]["options"]:
                questions[-1]["text"] += " " + line.strip()
            elif not questions:
                intro.append(line)
    for q in questions:
        q["text"] = _inline_md(q["text"])

    quiz = {"title": head.group(1), "intro": markdown.markdown("\n".join(intro)),
            "questions": questions}
    return text[:head.start()] + text[end:], quiz


# ---------------------------------------------------------------------------
# Misc HTML helpers
# ---------------------------------------------------------------------------

def _resolve_images(doc: str, source_dir: Path) -> str:
    def _replace(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:", "/")):
            return m.group(0)
        return f'src="{(source_dir / src).resolve()}"'
    return re.sub(r'src="([^"]+)"', _replace, doc)


def _parse_steps(doc: str):
    parts = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S).split(doc)
    steps = [{"number": i // 2 + 1,
              "title": re.sub(r"<[^>]+>", "", parts[i]).strip(),
              "content": parts[i + 1].strip()}
             for i in range(1, len(parts) - 1, 2)]
    return parts[0].strip(), steps


def _load_clancey():
    for ext, fmt in [("woff2", "woff2"), ("woff", "woff"), ("ttf", "truetype"), ("otf", "opentype")]:
        for name in ("Clancey", "clancey", "CLANCEY"):
            path = FONTS_DIR / f"{name}.{ext}"
            if path.exists():
                return f"data:font/{fmt};base64," + base64.b64encode(path.read_bytes()).decode(), fmt
    return None, None


def _write(html_text: str, path: Path, pdf: bool):
    path.write_text(html_text, encoding="utf-8")
    print(f"✓ HTML  →  {path}")
    if pdf:
        try:
            from weasyprint import HTML
            HTML(filename=str(path)).write_pdf(str(path.with_suffix(".pdf")))
            print(f"✓ PDF   →  {path.with_suffix('.pdf')}")
        except ImportError:
            print("WeasyPrint not installed: pip install weasyprint", file=sys.stderr)
        except Exception as exc:
            print(f"PDF generation failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Generate print-ready lab documents from Markdown.")
    ap.add_argument("input", help="Input .md file")
    ap.add_argument("-o", "--output", help="Output directory (default: next to the input file)")
    ap.add_argument("--pdf", action="store_true", help="Also write a PDF via WeasyPrint")
    ap.add_argument("--size", choices=list(PAGE_SIZES), help="Override page size")
    ap.add_argument("--orientation", choices=["portrait", "landscape"], help="Override orientation")
    args = ap.parse_args()

    src = Path(args.input).resolve()
    if not src.exists():
        sys.exit(f"Error: {src} not found")
    out_dir = Path(args.output).resolve() if args.output else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    post = frontmatter.load(str(src))
    meta = post.metadata

    doc_type = str(meta.get("type", DEFAULT_TYPE)).lower()
    if doc_type not in DOC_TYPES:
        print(f"Warning: unknown type '{doc_type}', using '{DEFAULT_TYPE}'", file=sys.stderr)
        doc_type = DEFAULT_TYPE

    page_size = args.size or str(meta.get("size", "A4"))
    orientation = args.orientation or str(meta.get("orientation", "portrait"))
    w, h = PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])
    if orientation == "landscape":
        w, h = h, w

    clancey, clancey_fmt = _load_clancey()
    if not clancey:
        print("Note: no Clancey font in fonts/ — headings use a fallback.", file=sys.stderr)

    facts = meta.get("facts") or {}
    ctx = {
        "title": str(meta.get("title", src.stem.replace("-", " ").title())),
        "subtitle": str(meta.get("subtitle", "")),
        "tag": str(meta.get("tag", DOC_TYPES[doc_type])),
        "page_css": f"{page_size} {orientation}",
        "page_w": w, "page_h": h,
        "accent": str(meta.get("accent", "#D62828")),
        "clancey_data": clancey, "clancey_fmt": clancey_fmt,
        "facts": [(str(k), str(v)) for k, v in facts.items()],
        "pass_mark": str(meta.get("pass_mark", "")),
        "declaration": str(meta.get("declaration", DEFAULT_DECLARATION)),
        "signoff": bool(meta.get("signoff", True)) and doc_type == "induction",
        "quiz": None,
    }
    if meta.get("qr_corner"):
        ctx["qr_corner"] = _qr_dataurl(str(meta["qr_corner"]), 12)
        ctx["qr_corner_label"] = str(meta.get("qr_corner_label", "Scan for more info"))
    if meta.get("qr_video"):
        ctx["qr_video"] = _qr_dataurl(str(meta["qr_video"]), 12)
        ctx["qr_video_label"] = str(meta.get("qr_video_label", "Watch the video"))

    content = post.content
    if doc_type == "induction":
        content, ctx["quiz"] = _extract_quiz(content)

    body = markdown.markdown(content, extensions=["extra", "nl2br"])
    body = _resolve_images(_process_callouts(_process_qr_links(body)), src.parent)

    if doc_type == "stepguide":
        ctx["intro"], ctx["steps"] = _parse_steps(body)
    else:
        ctx["body"] = body

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    _write(env.get_template(f"{doc_type}.html").render(**ctx), out_dir / f"{src.stem}.html", args.pdf)

    if ctx["quiz"] and ctx["quiz"]["questions"]:
        key = env.get_template("answerkey.html").render(**ctx)
        _write(key, out_dir / f"{src.stem}-answer-key.html", args.pdf)


if __name__ == "__main__":
    main()
