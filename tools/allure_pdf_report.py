"""
allure_pdf_report - build a PDF test report from Allure results (allure-results/*.json).

The Allure HTML report is an interactive web app and has no "export to PDF". Printing it from a
browser only captures the first screen. So this tool reads the SAME raw results that Allure uses
and writes a printable PDF with:

  1. Summary       - totals, pass rate, duration, pie chart, environment
  2. By feature    - passed / failed / broken / skipped per epic > feature
  3. All tests     - one row per test: title, feature/story, severity, status, duration
  4. Failures      - message, stack trace, steps and the screenshot taken on failure
  5. Test details  - the steps (and their status) of every test  (--details failed to skip)

Usage (from automation_framework/):
    python tools/allure_pdf_report.py
    python tools/allure_pdf_report.py --results allure-results --output reports/test_report.pdf
    python tools/allure_pdf_report.py --title "Sprint 42 regression" --details failed
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
STATUS_ORDER = ["passed", "failed", "broken", "skipped", "unknown"]
STATUS_COLORS = {
    "passed": colors.HexColor("#2e7d32"),
    "failed": colors.HexColor("#c62828"),
    "broken": colors.HexColor("#ef8f00"),
    "skipped": colors.HexColor("#757575"),
    "unknown": colors.HexColor("#6a1b9a"),
}
SEVERITY_ORDER = ["blocker", "critical", "normal", "minor", "trivial"]
HEADER_BG = colors.HexColor("#1f3b57")
ZEBRA = colors.HexColor("#f3f6f9")


# ------------------------------------------------------------------ fonts
def _register_font():
    """Use a Unicode TTF font if one is available (Windows: Arial, Linux: DejaVu), else Helvetica."""
    candidates = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("ReportFont", regular))
            pdfmetrics.registerFont(TTFont("ReportFont-Bold", bold))
            return "ReportFont", "ReportFont-Bold", True
    return "Helvetica", "Helvetica-Bold", False


FONT, FONT_BOLD, UNICODE_OK = _register_font()


def clean(text):
    """Escape for reportlab Paragraph markup; fall back to Latin-1 if no Unicode font is available."""
    text = "" if text is None else str(text)
    if not UNICODE_OK:
        text = text.encode("latin-1", "replace").decode("latin-1")
    return escape(text)


# ------------------------------------------------------------------ loading
def load_results(results_dir):
    """All *-result.json files. If a test ran more than once (reruns), keep only its latest result."""
    latest = {}
    for path in results_dir.glob("*-result.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        key = data.get("historyId") or data.get("uuid") or path.name
        if key not in latest or data.get("stop", 0) > latest[key].get("stop", 0):
            latest[key] = data
    return sorted(latest.values(), key=lambda r: r.get("start", 0))


def load_environment(results_dir):
    env_file = results_dir / "environment.properties"
    if not env_file.exists():
        return {}
    pairs = (line.split("=", 1) for line in env_file.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def label(result, name, default=""):
    return next((lb["value"] for lb in result.get("labels", []) if lb["name"] == name), default)


def status_of(result):
    return result.get("status") if result.get("status") in STATUS_COLORS else "unknown"


def duration_s(item):
    return max(0, (item.get("stop", 0) - item.get("start", 0)) / 1000)


def fmt_duration(seconds):
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs:02d}s"


def fmt_time(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def all_attachments(item):
    """Attachments of a test or step, including those of all nested steps."""
    found = list(item.get("attachments", []))
    for sub in item.get("steps", []):
        found.extend(all_attachments(sub))
    return found


# ------------------------------------------------------------------ styles
def build_styles():
    base = getSampleStyleSheet()

    def style(name, parent="Normal", **kw):
        kw.setdefault("fontName", FONT)
        return ParagraphStyle(name, parent=base[parent], **kw)

    return {
        "title": style("title", "Title", fontName=FONT_BOLD, fontSize=22, leading=26, textColor=HEADER_BG),
        "subtitle": style("subtitle", fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
        "h1": style("h1", "Heading1", fontName=FONT_BOLD, fontSize=15, textColor=HEADER_BG, spaceBefore=6),
        "h2": style("h2", "Heading2", fontName=FONT_BOLD, fontSize=11.5, spaceBefore=8, spaceAfter=3),
        "body": style("body", fontSize=9, leading=12),
        "small": style("small", fontSize=8, leading=10),
        "cell": style("cell", fontSize=8, leading=10),
        "cell_bold": style("cell_bold", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=colors.white),
        "kpi_num": style("kpi_num", fontName=FONT_BOLD, fontSize=18, leading=22, alignment=TA_CENTER),
        "kpi_lbl": style("kpi_lbl", fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#555555")),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=7, leading=8.5,
                               backColor=colors.HexColor("#f7f7f7"), borderPadding=4),
    }


def grid_table(rows, col_widths, header=True, zebra=True):
    table = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3dd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), HEADER_BG))
    if zebra:
        for row in range(1 if header else 0, len(rows)):
            if row % 2 == 0:
                commands.append(("BACKGROUND", (0, row), (-1, row), ZEBRA))
    table.setStyle(TableStyle(commands))
    return table


def status_badge(status, styles):
    color = STATUS_COLORS[status].hexval().replace("0x", "#")
    return Paragraph(f'<font color="{color}"><b>{status.upper()}</b></font>', styles["cell"])


# ------------------------------------------------------------------ sections
def summary_section(results, environment, title, styles):
    counts = Counter(status_of(r) for r in results)
    total = len(results)
    executed = total - counts["skipped"]
    pass_rate = (counts["passed"] / executed * 100) if executed else 0
    start = min((r.get("start", 0) for r in results), default=0)
    stop = max((r.get("stop", 0) for r in results), default=0)

    story = [
        Spacer(1, 12 * mm),
        Paragraph(clean(title), styles["title"]),
        Paragraph(f"Generated {datetime.now():%Y-%m-%d %H:%M:%S} from Allure results", styles["subtitle"]),
        Spacer(1, 8 * mm),
    ]

    # KPI tiles
    tiles = [("TOTAL", total, HEADER_BG)] + [
        (s.upper(), counts[s], STATUS_COLORS[s]) for s in ["passed", "failed", "broken", "skipped"]
    ] + [("PASS RATE", f"{pass_rate:.1f}%", STATUS_COLORS["passed"] if pass_rate == 100 else HEADER_BG)]
    numbers = [Paragraph(f'<font color="{c.hexval().replace("0x", "#")}">{v}</font>', styles["kpi_num"])
               for _, v, c in tiles]
    labels = [Paragraph(n, styles["kpi_lbl"]) for n, _, _ in tiles]
    kpi = Table([numbers, labels], colWidths=[28 * mm] * len(tiles))
    kpi.setStyle(TableStyle([
        ("BOX", (i, 0), (i, 1), 0.8, colors.HexColor("#c9d3dd")) for i in range(len(tiles))
    ] + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, 0), 6)]))
    story += [kpi, Spacer(1, 8 * mm)]

    # Pie chart + run info side by side
    drawing = Drawing(80 * mm, 55 * mm)
    present = [s for s in STATUS_ORDER if counts[s]]
    if present:
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 5 * mm, 5 * mm, 45 * mm, 45 * mm
        pie.data = [counts[s] for s in present]
        pie.labels = [str(counts[s]) for s in present]
        pie.slices.strokeColor = colors.white
        pie.slices.fontName = FONT_BOLD
        pie.slices.fontColor = colors.white
        pie.sideLabels = False
        pie.simpleLabels = True
        pie.slices.labelRadius = 0.65
        for i, s in enumerate(present):
            pie.slices[i].fillColor = STATUS_COLORS[s]
        legend = Legend()
        legend.x, legend.y = 55 * mm, 40 * mm
        legend.fontName, legend.fontSize = FONT, 8
        legend.colorNamePairs = [(STATUS_COLORS[s], f"{s} ({counts[s]})") for s in present]
        drawing.add(pie)
        drawing.add(legend)

    run_rows = [
        [Paragraph("<b>Started</b>", styles["cell"]), Paragraph(fmt_time(start), styles["cell"])],
        [Paragraph("<b>Finished</b>", styles["cell"]), Paragraph(fmt_time(stop), styles["cell"])],
        [Paragraph("<b>Wall-clock time</b>", styles["cell"]), Paragraph(fmt_duration((stop - start) / 1000), styles["cell"])],
        [Paragraph("<b>Sum of test durations</b>", styles["cell"]),
         Paragraph(fmt_duration(sum(duration_s(r) for r in results)), styles["cell"])],
    ] + [[Paragraph(f"<b>{clean(k)}</b>", styles["cell"]), Paragraph(clean(v), styles["cell"])]
         for k, v in environment.items()]
    run_table = grid_table(run_rows, [38 * mm, 58 * mm], header=False)
    side = Table([[drawing, run_table]], colWidths=[82 * mm, 98 * mm])
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Paragraph("Result distribution and run information", styles["h2"]), side]
    return story


def by_feature_section(results, styles):
    groups = defaultdict(Counter)
    for r in results:
        key = (label(r, "epic", "-"), label(r, "feature", label(r, "suite", "-")))
        groups[key][status_of(r)] += 1
    header = ["Epic", "Feature", "Total", "Passed", "Failed", "Broken", "Skipped"]
    rows = [[Paragraph(h, styles["cell_bold"]) for h in header]]
    for (epic, feature), c in sorted(groups.items()):
        rows.append([Paragraph(clean(epic), styles["cell"]), Paragraph(clean(feature), styles["cell"]),
                     sum(c.values()), c["passed"], c["failed"], c["broken"], c["skipped"]])
    table = grid_table(rows, [42 * mm, 50 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm])
    table.setStyle(TableStyle([("ALIGN", (2, 1), (-1, -1), "CENTER"), ("FONTNAME", (2, 1), (-1, -1), FONT),
                               ("FONTSIZE", (2, 1), (-1, -1), 8)]))
    return [Paragraph("Results by feature", styles["h1"]), table]


def all_tests_section(results, styles):
    header = ["#", "Test", "Feature / story", "Severity", "Status", "Duration"]
    rows = [[Paragraph(h, styles["cell_bold"]) for h in header]]
    for i, r in enumerate(results, 1):
        feature = label(r, "feature", label(r, "suite", ""))
        story = label(r, "story")
        rows.append([
            Paragraph(str(i), styles["cell"]),
            Paragraph(f"{clean(r.get('name'))}<br/><font size=6.5 color='#777777'>{clean(r.get('fullName', ''))}</font>",
                      styles["cell"]),
            Paragraph(clean(feature) + (f"<br/><font color='#777777'>{clean(story)}</font>" if story else ""),
                      styles["cell"]),
            Paragraph(clean(label(r, "severity", "normal")), styles["cell"]),
            status_badge(status_of(r), styles),
            Paragraph(fmt_duration(duration_s(r)), styles["cell"]),
        ])
    return [Paragraph("All tests", styles["h1"]),
            grid_table(rows, [8 * mm, 72 * mm, 45 * mm, 17 * mm, 17 * mm, 18 * mm])]


def steps_flowables(steps, styles, depth=0):
    flow = []
    for s in steps:
        st = status_of(s)
        color = STATUS_COLORS[st].hexval().replace("0x", "#")
        indent = "&nbsp;" * (4 * depth)
        flow.append(Paragraph(
            f"{indent}<font color='{color}'>&#9679;</font> {clean(s.get('name'))} "
            f"<font color='#777777'>({fmt_duration(duration_s(s))})</font>", styles["small"]))
        message = (s.get("statusDetails") or {}).get("message")
        if st in ("failed", "broken") and message:
            flow.append(Paragraph(f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;<font color='{color}'>{clean(message[:300])}</font>",
                                  styles["small"]))
        flow += steps_flowables(s.get("steps", []), styles, depth + 1)
    return flow


def screenshots(result, results_dir, max_width=170 * mm, max_height=100 * mm):
    images = []
    for att in all_attachments(result):
        if att.get("type") in ("image/png", "image/jpeg") and (results_dir / att["source"]).exists():
            img = Image(str(results_dir / att["source"]))
            scale = min(max_width / img.imageWidth, max_height / img.imageHeight, 1)
            img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
            images.append((att.get("name", "screenshot"), img))
    return images


def failures_section(results, results_dir, styles):
    failed = [r for r in results if status_of(r) in ("failed", "broken")]
    story = [Paragraph(f"Failures ({len(failed)})", styles["h1"])]
    if not failed:
        return story + [Paragraph("No failed or broken tests - well done.", styles["body"])]
    for r in failed:
        st = status_of(r)
        details = r.get("statusDetails") or {}
        block = [
            Paragraph(f"{clean(r.get('name'))} &nbsp; <font color='{STATUS_COLORS[st].hexval().replace('0x', '#')}'>"
                      f"[{st.upper()}]</font>", styles["h2"]),
            Paragraph(f"<b>Feature:</b> {clean(label(r, 'feature', '-'))} &nbsp; <b>Severity:</b> "
                      f"{clean(label(r, 'severity', 'normal'))} &nbsp; <b>Duration:</b> {fmt_duration(duration_s(r))}",
                      styles["small"]),
            Spacer(1, 2 * mm),
            Paragraph(f"<b>Message:</b> {clean(details.get('message', '-'))}", styles["body"]),
        ]
        story.append(KeepTogether(block))
        trace = details.get("trace")
        if trace:
            lines = trace.strip().splitlines()
            if len(lines) > 30:
                lines = lines[:12] + ["    ... (trace shortened) ..."] + lines[-15:]
            story += [Spacer(1, 2 * mm), Preformatted("\n".join(lines), styles["code"], maxLineLength=120)]
        if r.get("steps"):
            story += [Spacer(1, 2 * mm), Paragraph("<b>Steps</b>", styles["small"])] + steps_flowables(r["steps"], styles)
        for name, img in screenshots(r, results_dir):
            story += [Spacer(1, 2 * mm), Paragraph(f"<b>Attachment:</b> {clean(name)}", styles["small"]), img]
        story.append(Spacer(1, 6 * mm))
    return story


def details_section(results, styles):
    story = [Paragraph("Test details (steps)", styles["h1"])]
    for i, r in enumerate(results, 1):
        st = status_of(r)
        story += [CondPageBreak(25 * mm), Paragraph(
            f"{i}. {clean(r.get('name'))} &nbsp;<font color='{STATUS_COLORS[st].hexval().replace('0x', '#')}'>"
            f"[{st.upper()}]</font> <font color='#777777'>{fmt_duration(duration_s(r))}</font>", styles["h2"])]
        params = [p for p in r.get("parameters", []) if p.get("name")]
        for p in params:
            story.append(Paragraph(f"<b>{clean(p['name'])}:</b> {clean(p.get('value', ''))[:250]}", styles["small"]))
        story += steps_flowables(r.get("steps", []), styles) or [Paragraph("(no steps recorded)", styles["small"])]
    return story


# ------------------------------------------------------------------ page decoration
def make_page_decorator(title):
    def decorate(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(HEADER_BG)
        canvas.rect(0, height - 10 * mm, width, 10 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(FONT_BOLD, 9)
        canvas.drawString(15 * mm, height - 6.5 * mm, title[:90])
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.setFont(FONT, 7.5)
        canvas.drawString(15 * mm, 8 * mm, "Generated from Allure results by tools/allure_pdf_report.py")
        canvas.drawRightString(width - 15 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return decorate


# ------------------------------------------------------------------ main
def build_pdf(results_dir, output, title, details="all"):
    results = load_results(results_dir)
    if not results:
        raise SystemExit(f"No Allure results found in {results_dir} - run pytest first (it writes allure-results/).")
    environment = load_environment(results_dir)
    styles = build_styles()

    story = summary_section(results, environment, title, styles)
    story += [PageBreak()] + by_feature_section(results, styles)
    story += [Spacer(1, 6 * mm)] + all_tests_section(results, styles)
    story += [PageBreak()] + failures_section(results, results_dir, styles)
    if details == "all":
        story += [PageBreak()] + details_section(results, styles)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=A4, title=title, author="automation_framework",
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=16 * mm, bottomMargin=15 * mm)
    decorate = make_page_decorator(title)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    counts = Counter(status_of(r) for r in results)
    return output, len(results), counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a PDF test report from Allure results")
    parser.add_argument("--results", default=str(ROOT / "allure-results"), help="Allure results folder")
    parser.add_argument("--output", default=str(ROOT / "reports" / "test_report.pdf"), help="PDF file to write")
    parser.add_argument("--title", default="Desktop & CLI Automation - Test Report", help="report title")
    parser.add_argument("--details", choices=["all", "failed"], default="all",
                        help="'all' adds the steps of every test; 'failed' keeps the PDF short")
    args = parser.parse_args(argv)

    output, total, counts = build_pdf(Path(args.results), Path(args.output), args.title, args.details)
    summary = ", ".join(f"{s} {counts[s]}" for s in STATUS_ORDER if counts[s])
    print(f"PDF report: {output}  ({total} tests: {summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
