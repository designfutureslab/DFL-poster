# DFL Poster

Turn Markdown (plus images) into consistently formatted, print-ready lab documents: posters, inductions, how-tos and step-by-step guides.

```bash
pip install -r requirements.txt
python generate.py examples/induction-example.md          # -> .html next to the input
python generate.py examples/howto-example.md --pdf        # also writes a PDF (WeasyPrint)
python generate.py doc.md -o out/ --size A3 --orientation landscape
```

To print from a browser, open the `.html`, press `Ctrl+P`, set margins to **None** and turn on **Background graphics**. Put images next to the `.md` file and reference them normally: `![caption](photo.jpg)`.

**Fonts.** Headings use Clancey: drop `Clancey.woff2` (or `.woff`, `.ttf`, `.otf`) into `fonts/` and it is embedded in every output file. Body text is Roboto, loaded from Google Fonts (needs internet; falls back to Arial).

---

## Document types

Set with `type:` in the frontmatter. Default is `howto`.

| `type` | Use it for | Structure |
|---|---|---|
| `poster` | Wall signage, rules, reminders | One page. Big title, accent bar, bullets and callouts |
| `induction` | Formal machine/area inductions | Cover band, document-control table, numbered sections, **quiz**, **sign-off block**, page numbers. Also writes an assessor **answer key** file |
| `howto` | Occasional tasks that don't need formality | Light header, facts strip, plain sections, numbered-badge lists |
| `stepguide` | Visual procedures at the machine | Each `##` heading becomes a numbered step card |

## Frontmatter

```yaml
---
type: induction
title: Prusa MK4S Induction
subtitle: FDM 3D Printer
tag: Lab Induction            # small label in the header (default depends on type)
size: A4                      # A4 | A3 | A5 | letter
orientation: portrait         # portrait | landscape
accent: "#1B4F72"             # any CSS colour
qr_corner: https://...        # corner QR (top right of the header)
qr_corner_label: Machine page # caption under it (default "Scan for more info")
qr_video: https://...         # video QR, shown beside the corner QR
qr_video_label: Watch the induction video
facts:                        # key/value strip under the header
  Document ID: DFL-IND-003
  Version: "1.2"
  Time: 10 minutes
# induction only
pass_mark: "4 / 4 (100%)"
signoff: true                 # sign-off block (default true)
declaration: "I confirm that..."   # override the sign-off wording
---
```

On an induction the `facts` strip is your document control (ID, version, owner, review date). On a how-to it is quick info (time, level, tools).

## Callouts

A blockquote whose first line starts with `[!TYPE]` becomes a callout. **Text after the type on that line becomes the bold title** next to the coloured label; the lines below are the body. The title is optional.

```markdown
> [!WARNING] Hot surfaces
> The hot end reaches 290 °C. Allow 5 minutes to cool.

> [!NOTE]
> A callout with just a label and body.
```

| Type | Colour | Also accepts |
|---|---|---|
| `DANGER` | red | `STOP` |
| `WARNING` | orange | `CAUTION` |
| `IMPORTANT` | purple | |
| `NOTE` | blue | `INFO` |
| `TIP` | green | `HINT` |

A plain blockquote without `[!TYPE]` renders as a quiet quotation.

## QR codes

| Syntax | Result |
|---|---|
| `qr_corner:` / `qr_video:` in frontmatter | QR codes in the header, top right |
| `[QR: Watch the demo](https://...)` on its own line | Captioned QR block. **Directly after a heading it floats to the right of that section**, which is how you put a video QR at the top of any section |
| `[QR](https://...)` on its own line | Uncaptioned QR block |
| `[QR](https://...)` inside a sentence or table cell | Small inline QR |

```markdown
## Safety Requirements

[QR: Safety walkthrough video](https://example.com/safety)

> [!DANGER] Fire risk
> ...
```

## Quiz (induction)

Any `##` section whose title contains "Quiz" becomes the quiz page. Number the questions; mark correct answers with `[x]`. A question with no options becomes a written answer with ruled lines.

```markdown
## Knowledge Check Quiz

Answer every question.

1. How long should you stay with the printer at the start of a print?
   - [ ] Not at all
   - [x] For the first 3–4 minutes
   - [ ] Until the print finishes
2. Describe what you do before leaving a print running.
```

The induction prints with blank checkboxes. Correct answers are written to a separate `<name>-answer-key.html` marked *Assessor copy*: don't hang that one up.

## Step guides

Each `##` is one step. Text before the first `##` is the intro. Images, lists, callouts and `[QR: ...]` blocks go inside the step they follow.
