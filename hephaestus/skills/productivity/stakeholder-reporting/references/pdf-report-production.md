# PDF report production

For a report a stakeholder will read or forward. Markdown converters give almost no control
over pagination, so author semantic HTML with print CSS and convert that.

## Pipeline

1. Write the HTML with `@page` sizing and print-oriented CSS.
2. Convert with a headless HTML-to-PDF converter.
3. Confirm page count and page size from the PDF's own metadata.
4. **Render pages to images and look at them.** Non-negotiable — see below.
5. Extract the text layer and sweep it for identifiers.

The text sweep in step 5 is a different check from step 4 and neither substitutes for the
other: text extraction cannot see layout, and a rendered image cannot be grepped.

## The CSS that prevents the usual defects

A clean compile does not mean a clean document. These four rules prevent the layout
failures that survive conversion without any warning:

```css
@page { size: A4; margin: 16mm 14mm; }
h2, h3  { page-break-after: avoid; break-after: avoid; }  /* heading stays with its content */
thead   { display: table-header-group; }                  /* split tables repeat the header */
tr      { page-break-inside: avoid; break-inside: avoid; } /* no row torn across a page */
.keep, pre, blockquote { page-break-inside: avoid; break-inside: avoid; }
```

**Wrap a heading and its table in a keep-together container when the pair must not split.**
The `page-break-after: avoid` on the heading alone can still leave the heading plus the
table's header row stranded at the foot of a page with the body overleaf.

**Give every table a real `<thead>`.** Without it a table that splits loses its column
headers entirely on the continuation page, and the reader sees an unlabelled grid of
numbers. This is the most damaging of the layout defects because the content is still there
and still looks intentional.

## Visual verification

Render each page to an image and inspect it. Check specifically:

- text or tables clipped at the right edge
- uneven left/right margins
- a heading or table header orphaned at the foot of a page
- a table continuing onto a page without its header row
- overlapping text
- preformatted blocks wider than the text column

**A successful conversion exit code says nothing about the layout.** Converters report
success for documents with stranded headings, clipped tables, and headerless continuation
pages. The only check that catches these is looking at the rendered pixels.

**Re-render and re-inspect after every layout fix.** A page-break rule that solves one
orphan commonly creates another further down, because every subsequent break moves.

## Editing an existing document: renumbering

Inserting or removing a section in a numbered document breaks every number after it.

**Renumber by document position in a single regex pass over all headings at once, never
by a sequence of individual replacements.** Replacing `4` with `5`, then `3` with `4`,
rewrites the same heading twice and silently produces duplicates or a scrambled order; a
replacement capped at one occurrence applies to whichever instance appears first in the
file, which is rarely the one intended. A counter-driven substitution over every match in
order is correct by construction.

**Then assert the result is `[1..n]` before rendering.** Extract the numbers and compare
against the expected range programmatically. Numbering errors are invisible in a diff and
fully visible to the reader, and the same trap applies to ordered rows inside tables —
check those separately from the headings.

**Re-read the row labels after renumbering, not just the numbers.** A sequence can read
`1..n` correctly while the rows sit in a scrambled order, so confirm the first few words
of each row still appear in the intended sequence.

## Converter quirks

Some converters silently ignore switches they do not support and print a notice to stderr
rather than failing. **Read the converter's stderr even on a zero exit**, or you will
believe a header, footer, or page-numbering option was applied when it was dropped.

**Unpatched-Qt wkhtmltopdf (the distro package) ignores `@page` margins, every
`--header-*`/`--footer-*` switch, `--print-media-type`, and flexbox.** Pass page size and
margins on the command line (`-s A4 -T 18mm -B 18mm -L 16mm -R 16mm`), centre a cover
with padding rather than flex, and say in the delivery that page numbers are unavailable
from this build (the HTML prints with them from any browser). A cover that renders
flush-left with no margins and a `>` leaking from a blockquote are the two tells that the
CSS you wrote was not applied.

**Keep short tables whole and glue the lead paragraph to them; let only long tables split.**
Mark a table `keep` when it has at most ~18 body rows (so it never splits) and `splittable`
otherwise (so `thead` repeats). For a `keep` table, move the paragraph that introduces it
INSIDE the keep container; for a `splittable` one give that paragraph
`page-break-after: avoid`. `break-after: avoid` on the paragraph alone is not honoured by
unpatched Qt, so a lead sentence still strands at the foot of a page with its table
overleaf unless it shares the container.

**Force page breaks only before the long sections.** `page-break-before: always` on every
section leaves near-empty pages (a three-line tail on its own page); let short sections
flow and break only before the two or three that fill a page by themselves. Re-render after
changing which sections break, because the orphan moves.

**`pdftoppm` numbers output pages with the minimum digits (`pg-1.png` under ten pages,
`pg-01.png` at ten or more)**, so a page-image path hard-coded from an earlier run with more
pages fails with "not found" after the document shrinks. List the directory before
inspecting.

**Author the HTML yourself when no markdown library is installed** — a sixty-line converter
(headings, lists, tables with a real `<thead>`, inline code/bold/links, blockquote → callout)
beats a pip install that may need approval, and it gives the cover and contents page for
free. Drop the markdown's own title/byline paragraph when the cover already carries them.
Handle every construct the source uses or it renders as prose: `###` → `<h3>` (otherwise
subsection titles vanish into body text), fenced ``` blocks → `<pre>` with
`white-space: pre-wrap` (otherwise commands print as one run-on paragraph with the fence
markers visible), and a bare `>` or `**…**` opening line → callout, not `<p>`. Grep the
produced HTML for `<h3>` and `<pre>` counts against the source before rendering. Skip the
contents page below ~5 pages; it wastes a sheet.

## Final sweep

Extract the text layer and check for: personal names, email addresses, phone numbers,
customer or record identifiers, internal hostnames, ports, credential prefixes, and UUIDs.

**Inspect each hit rather than trusting the count.** Legitimate content matches these
patterns — an organisation name in a subtitle, a date read as a phone number, an identifier
in a code example. The goal is zero *unintended* identifiers, which is a judgement the
pattern cannot make for you.
