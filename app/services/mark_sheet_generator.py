"""
mark_sheet_generator.py

Generates a RUET-style CT mark sheet PDF (like the provided sample image).

FIX APPLIED:
- Switched from low-level Canvas drawing to Platypus SimpleDocTemplate
- This enables automatic multi-page table splitting
- NO layout change
- NO business logic change
- Colors, fonts, table structure unchanged
- Fixed font loading to use ReportLab's built-in Times-Roman fonts
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple, Union
import random

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# No custom font registration needed - using built-in fonts
FONT_NORMAL = "Times-Roman"
FONT_BOLD = "Times-Bold"

# -----------------------------
# Public API
# -----------------------------

def generate_mark_sheet(
    output_pdf_path: str,
    *,
    dept: str,
    series: str,
    section: Optional[str] = None,
    course_code: str,
    course_name: str,
    from_roll: Union[str, int],
    to_roll: Union[str, int],
    marks_batch_entries: List[Dict[str, Union[str, int]]],
    ct_count: int = 4,
    ct_full_marks: Optional[Union[int, Sequence[int]]] = 20,
    show_div0: bool = True,
) -> str:

    # Normalize full marks
    if isinstance(ct_full_marks, int):
        full_marks = [ct_full_marks] * ct_count
    else:
        full_marks = list(ct_full_marks)
        if len(full_marks) != ct_count:
            raise ValueError("ct_full_marks must match ct_count")

    start = int(str(from_roll).strip())
    end = int(str(to_roll).strip())
    if end < start:
        raise ValueError("to_roll must be >= from_roll")

    rolls = [str(r) for r in range(start, end + 1)]

    # Build marks map
    marks_map: Dict[Tuple[str, int], str] = {}
    for e in marks_batch_entries or []:
        roll_no = str(e.get("roll_no", "")).strip()
        ct_no = int(e.get("ct_no"))
        marks = str(e.get("marks", "")).strip()
        if roll_no and 1 <= ct_no <= ct_count:
            marks_map[(roll_no, ct_no)] = marks

    # Collect numeric values for stats
    ct_numeric = {i: [] for i in range(1, ct_count + 1)}
    for roll in rolls:
        for ct in range(1, ct_count + 1):
            val = _parse_mark_to_float(marks_map.get((roll, ct), ""))
            if val is not None:
                ct_numeric[ct].append(val)

    highest, lowest, average = [], [], []
    for ct in range(1, ct_count + 1):
        nums = ct_numeric[ct]
        if nums:
            highest.append(_fmt_num(max(nums)))
            lowest.append(_fmt_num(min(nums)))
            average.append(f"{sum(nums) / len(nums):.2f}")
        else:
            highest.append("0.0")
            lowest.append("0.0")
            average.append("#DIV/0!" if show_div0 else "0.0")

    # -----------------------------
    # Document setup (FIX)
    # -----------------------------

    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = FONT_NORMAL
    styles["Normal"].fontSize = 10

    styles["Title"].fontName = FONT_BOLD
    styles["Heading1"].fontName = FONT_BOLD
    styles["Heading2"].fontName = FONT_BOLD
    styles["Heading3"].fontName = FONT_BOLD

    styles.add(ParagraphStyle(
        name="Center",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName=FONT_NORMAL,
    ))
    
    story = []

    # -----------------------------
    # Header (unchanged content)
    # -----------------------------

    story.append(Paragraph("Heaven's Light is Our Guide", styles["Center"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "<b>Rajshahi University of Engineering & Technology</b>",
        ParagraphStyle(
            "ruet",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName=FONT_BOLD,
            fontSize=16,
            leading=18,
        ),
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"<b>Department of {dept}</b>",
        ParagraphStyle(
            "dept",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=12,
        ),
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        (
            f"<b>Class Test Marks ({str(section).strip().upper()} Section), {course_code} : {course_name}</b>"
            if (
                section is not None
                and str(section).strip() != ""
                and str(section).strip().lower() not in {"none", "null"}
                and str(section).strip().upper() in {"A", "B", "C"}
            )
            else f"<b>Class Test Marks, {course_code} : {course_name}</b>"
        ),
        ParagraphStyle(
            "course",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=12,
        ),
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(f"<b>{series} Series</b>", styles["Center"]))
    story.append(Spacer(1, 12))

    # -----------------------------
    # Table data (unchanged logic)
    # -----------------------------

    table_data: List[List[str]] = []

    table_data.append(["Roll No."] + [f"CT-{i:02d}" for i in range(1, ct_count + 1)])
    table_data.append(["Marks"] + [str(m) for m in full_marks])
    table_data.append(["Highest"] + highest)
    table_data.append(["Lowest"] + lowest)
    table_data.append(["Average"] + average)

    for roll in rolls:
        row = [roll]
        for ct in range(1, ct_count + 1):
            row.append(marks_map.get((roll, ct), ""))
        table_data.append(row)

    col_widths = [28 * mm] + [26 * mm] * ct_count

    table = Table(
        table_data,
        colWidths=col_widths,
        repeatRows=1,  # header repeats on each page
    )

    header_blue = colors.Color(0.46, 0.62, 0.80)
    label_blue = colors.Color(0.62, 0.76, 0.88)
    green = colors.Color(0.70, 0.87, 0.61)
    orange = colors.Color(0.98, 0.78, 0.45)
    yellow = colors.Color(0.99, 0.92, 0.50)

    style = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NORMAL),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),

        ("BACKGROUND", (0, 0), (-1, 0), header_blue),

        ("BACKGROUND", (0, 1), (-1, 1), label_blue),
        ("BACKGROUND", (0, 2), (-1, 2), green),
        ("BACKGROUND", (0, 3), (-1, 3), orange),
        ("BACKGROUND", (0, 4), (-1, 4), yellow),

        ("FONTNAME", (0, 1), (0, 4), FONT_BOLD),
    ])

    # Absent styling
    for r in range(5, len(table_data)):
        for c in range(1, ct_count + 1):
            if str(table_data[r][c]).strip().upper() == "A":
                style.add("TEXTCOLOR", (c, r), (c, r), colors.red)
                style.add("FONTNAME", (c, r), (c, r), FONT_BOLD)

    table.setStyle(style)
    story.append(table)

    # Build (this is where pagination happens)
    doc.build(story)

    return output_pdf_path


# -----------------------------
# Helpers (unchanged)
# -----------------------------

def _parse_mark_to_float(raw: str) -> Optional[float]:
    if not raw or str(raw).strip().upper() == "A":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _fmt_num(x: float) -> str:
    if float(x).is_integer():
        return f"{x:.1f}"
    return str(x).rstrip("0").rstrip(".")


# -----------------------------
# Test data (unchanged)
# -----------------------------

def generate_random_marks(
    start_roll=121,
    end_roll=181,
    ct_nos=(1, 2),
    absent_probability=0.15,
):
    entries = []
    for roll in range(start_roll, end_roll + 1):
        for ct in ct_nos:
            marks = "A" if random.random() < absent_probability else str(random.randint(1, 20))
            entries.append({"roll_no": str(roll), "ct_no": ct, "marks": marks})
    return entries


marks_batch_entries = generate_random_marks()


# demo data for quick testing (uncomment to use instead of random data)
marks_batch_entries = [
    {'roll_no': '121', 'ct_no': 1, 'marks': '8'},
    {'roll_no': '121', 'ct_no': 2, 'marks': '11'},
    {'roll_no': '122', 'ct_no': 1, 'marks': '5'},
    {'roll_no': '122', 'ct_no': 2, 'marks': '7'},
    {'roll_no': '123', 'ct_no': 1, 'marks': '13'},
    {'roll_no': '123', 'ct_no': 2, 'marks': '16'},
    {'roll_no': '124', 'ct_no': 1, 'marks': 'A'},
    {'roll_no': '124', 'ct_no': 2, 'marks': '13'},
    {'roll_no': '125', 'ct_no': 1, 'marks': '6'},
    {'roll_no': '125', 'ct_no': 2, 'marks': '17'}
]


generate_mark_sheet(
    output_pdf_path="demo_ct_marksheet.pdf",
    dept="Computer Science & Engineering",
    series="23",
    section="A",
    course_code="CSE 2101",
    course_name="Discrete Mathematics",
    from_roll=121,
    to_roll=181,
    marks_batch_entries=marks_batch_entries,
)