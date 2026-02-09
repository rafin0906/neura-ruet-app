"""
RUET-style Lab Report / Assignment / Report Cover PDF Generator (ReportLab)

Fonts used:
- University name: Alice, 20
- Department: Futura, 17
- Series: Futura, 13.2
- Motto: CormorantGaramond-Light, 12
- Details block: Times New Roman (optional), 15 (fallback: Times-Roman)

Paths:
- All font/image paths can be relative (resolved relative to this file) or absolute.

Install:
  pip install reportlab
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
PathLike = Union[str, Path]


# -----------------------------
# Helpers: path + font registry
# -----------------------------
def resolve_path(p: Optional[PathLike], base_dir: Path = BASE_DIR) -> Optional[str]:
    if not p:
        return None
    p = Path(p)
    return str(p if p.is_absolute() else (base_dir / p).resolve())


def safe_register_ttf(font_name: str, font_path: PathLike) -> None:
    if font_name in pdfmetrics.getRegisteredFontNames():
        return
    fp = resolve_path(font_path)
    if not fp or not Path(fp).exists():
        raise FileNotFoundError(f'Font file not found: "{fp}"')
    pdfmetrics.registerFont(TTFont(font_name, fp))


def register_cover_fonts(
    *,
    alice_ttf_path: PathLike,
    futura_ttf_path: PathLike,
    cormorant_ttf_path: PathLike,
    times_new_roman_ttf_path: Optional[PathLike] = None,
) -> None:
    safe_register_ttf("Alice", alice_ttf_path)
    safe_register_ttf("Futura", futura_ttf_path)
    safe_register_ttf("CormorantGaramond", cormorant_ttf_path)
    if times_new_roman_ttf_path:
        safe_register_ttf("TimesNewRoman", times_new_roman_ttf_path)


# -----------------------------
# Layout helpers
# -----------------------------
def _draw_centered(c: canvas.Canvas, text: str, y: float, font: str, size: float, page_w: float) -> None:
    c.setFont(font, size)
    c.drawString((page_w - c.stringWidth(text, font, size)) / 2.0, y, text)


def _draw_detail_row(
    c: canvas.Canvas,
    label: str,
    value: str,
    x: float,
    y: float,
    label_w: float,
    font_label: tuple[str, float],
    font_value: tuple[str, float],
) -> None:
    c.setFont(*font_label)
    c.drawString(x, y, label)
    c.setFont(*font_value)
    c.drawString(x + label_w, y, f": {value}")


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    c.setFont(font, size)
    words = (text or "").split()
    if not words:
        return [""]

    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if c.stringWidth(trial, font, size) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _wrap_lines_hardsplit(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    """
    Word wrap; if a single word is too long, hard-split to fit max_width.
    Also supports empty string.
    """
    c.setFont(font, size)
    text = (text or "").strip()
    if not text:
        return [""]

    def fits(s: str) -> bool:
        return c.stringWidth(s, font, size) <= max_width

    words = text.split()
    lines: list[str] = []
    cur = ""

    for w in words:
        candidate = w if not cur else (cur + " " + w)
        if fits(candidate):
            cur = candidate
            continue

        if cur:
            lines.append(cur)
            cur = ""

        if not fits(w):
            chunk = ""
            for ch in w:
                cand2 = chunk + ch
                if fits(cand2):
                    chunk = cand2
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            cur = chunk
        else:
            cur = w

    if cur:
        lines.append(cur)

    return lines


def _draw_wrapped_block_in_cell(
    c: canvas.Canvas,
    text_block: str,
    x: float,
    y_top: float,
    cell_w: float,
    cell_h: float,
    *,
    font: str,
    size: float,
    padding: float = 6 * mm,
    line_gap: float = 6.0 * mm,
) -> None:
    """
    Draw a multiline block inside a cell (wrap + clip).
    - Supports '\n' as paragraph breaks.
    - Guarantees nothing crosses borders via clipPath(path).
    """
    c.saveState()
    path = c.beginPath()
    path.rect(x, y_top - cell_h, cell_w, cell_h)
    c.clipPath(path, stroke=0, fill=0)

    c.setFont(font, size)
    max_width = max(1.0, cell_w - 2 * padding)

    # Split by newline, wrap each line separately (preserve the intended rows)
    raw_lines = (text_block or "").splitlines() or [""]
    wrapped_lines: list[str] = []
    for ln in raw_lines:
        wrapped_lines.extend(_wrap_lines_hardsplit(c, ln, font, size, max_width))

    y = y_top - padding - size
    min_y = y_top - cell_h + padding

    for line in wrapped_lines:
        if y < min_y:
            break
        c.drawString(x + padding, y, line)
        y -= line_gap

    c.restoreState()

def _draw_image_rotated(
    c: canvas.Canvas,
    img_path: str,
    x: float,
    y: float,
    w: float,
    h: float,
    rotate_deg: float = 0.0,
    preserve_aspect: bool = True,
):
    """
    Draw image rotated around its center.
    x,y = bottom-left of the final box location on the page.
    """
    c.saveState()
    cx, cy = x + w / 2.0, y + h / 2.0
    c.translate(cx, cy)
    if rotate_deg:
        c.rotate(rotate_deg)
    c.drawImage(img_path, -w / 2.0, -h / 2.0, width=w, height=h, mask="auto", preserveAspectRatio=preserve_aspect)
    c.restoreState()


# -----------------------------
# Data container
# -----------------------------
@dataclass
class CoverAssets:
    logo_path: str
    doodle_top_left_path: Optional[str] = None
    doodle_top_right_path: Optional[str] = None


# -----------------------------
# Main generator
# -----------------------------
def generate_ruet_cover_pdf(
    *,
    output_path: PathLike,
    # NEW: Cover type parameters
    cover_type: str,  # "Experiment" | "Assignment" | "Report"
    cover_type_no: str,  # The number (e.g., "01", "02")
    cover_type_title: str = "",  # Optional title (if empty, won't be shown)
    # Existing parameters
    course_code: str,
    course_title: str,
    date_of_exp: str = "",  # Make optional for assignments/reports
    date_of_submission: str,
    full_name: str,
    roll_no: str,
    section: str,
    dept: str,
    series: str,
    session: str,
    teacher_name: str,
    teacher_designation: str,
    teacher_dept: str,
    logo_path: PathLike,
    doodle_top_left_path: Optional[PathLike] = None,
    doodle_top_right_path: Optional[PathLike] = None,
    # fonts (relative paths resolve next to this file)
    alice_ttf_path: PathLike = "Alice-Regular.ttf",
    futura_ttf_path: PathLike = "Futura.ttf",
    cormorant_ttf_path: PathLike = "CormorantGaramond-Light.ttf",
    times_new_roman_ttf_path: Optional[PathLike] = None,
) -> str:
    # Register fonts
    register_cover_fonts(
        alice_ttf_path=alice_ttf_path,
        futura_ttf_path=futura_ttf_path,
        cormorant_ttf_path=cormorant_ttf_path,
        times_new_roman_ttf_path=times_new_roman_ttf_path,
    )

    # Details font
    details_font_name = "TimesNewRoman" if times_new_roman_ttf_path else "Times-Roman"

    assets = CoverAssets(
        logo_path=resolve_path(logo_path) or str(logo_path),
        doodle_top_left_path=resolve_path(doodle_top_left_path),
        doodle_top_right_path=resolve_path(doodle_top_right_path),
    )

    out_path = resolve_path(output_path) or str(output_path)

    page_w, page_h = A4
    c = canvas.Canvas(out_path, pagesize=A4)

    margin_x = 22 * mm
    top_y = page_h - 18 * mm

    # --- Top corner doodles (left rectangle + right flask/tube) ---
    rect_path = resolve_path("../assets/images/rectangle.png") or "../assets/images/rectangle.png"
    flask_path = resolve_path("../assets/images/doodle_1.png") or "../assets/images/doodle_1.png"
    tube_path  = resolve_path("../assets/images/doodle_2.png") or "../assets/images/doodle_2.png"
        
    # LEFT rectangle
    _draw_image_rotated(
        c,
        rect_path,
        x=-2 * mm,  
        y=page_h - 18 * mm,  
        w=15 * mm,
        h=10 * mm,
        rotate_deg=0,
        preserve_aspect=False,
    )

    # RIGHT doodles: conical flask + test tube
    _draw_image_rotated(
        c,
        flask_path,
        x=page_w - 18 * mm,
        y=page_h - 22 * mm,
        w=22 * mm,
        h=22 * mm,
        rotate_deg=-10,
    )

    _draw_image_rotated(
        c,
        tube_path,
        x=page_w - 40 * mm,
        y=page_h - 12 * mm,
        w=32 * mm,
        h=32 * mm,
        rotate_deg=30,
    )

    # Doodles (optional)
    if assets.doodle_top_left_path:
        try:
            c.drawImage(
                assets.doodle_top_left_path,
                0 * mm,
                page_h - 28 * mm,
                width=40 * mm,
                height=28 * mm,
                mask="auto",
                preserveAspectRatio=True,
                anchor="nw",
            )
        except Exception:
            pass

    if assets.doodle_top_right_path:
        try:
            c.drawImage(
                assets.doodle_top_right_path,
                page_w - 55 * mm,
                page_h - 35 * mm,
                width=55 * mm,
                height=35 * mm,
                mask="auto",
                preserveAspectRatio=True,
                anchor="nw",
            )
        except Exception:
            pass

    # Motto
    _draw_centered(c, "Haven's Light is Our Guide", top_y, "CormorantGaramond", 12, page_w)

    # University name (Alice 20)
    uni_y = top_y - 18 * mm
    _draw_centered(
        c,
        "Rajshahi University of Engineering & Technology",
        uni_y,
        "Alice",
        20,
        page_w,
    )

    # Logo block
    logo_y = uni_y - 65 * mm
    logo_size = 52 * mm
    try:
        c.drawImage(
            assets.logo_path,
            (page_w - logo_size) / 2.0,
            logo_y,
            width=logo_size,
            height=logo_size,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception as e:
        c.setFont("Times-Italic", 10)
        c.setFillColor(colors.red)
        c.drawString(margin_x, logo_y + logo_size / 2.0, f"Logo not loaded: {e}")
        c.setFillColor(colors.black)

    # Department + Series
    dept_y = logo_y - 16 * mm
    _draw_centered(c, dept, dept_y, "Futura", 17, page_w)
    _draw_centered(c, series, dept_y - 10 * mm, "Times-Bold", 13.2, page_w)

    # Details block - Dynamic based on cover_type
    details_x = 36 * mm
    details_top_y = dept_y - 35 * mm
    label_w = 52 * mm
    row_gap = 8.3 * mm

    detail_label_font = ("Times-Bold", 15)
    detail_value_font = (details_font_name, 15)

    current_y = details_top_y
    
    # Cover Type No. (e.g., "Experiment No.", "Assignment No.", "Report No.")
    type_label = f"{cover_type} No."
    _draw_detail_row(c, type_label, cover_type_no, details_x, current_y, label_w, detail_label_font, detail_value_font)
    current_y -= row_gap
    
    # Cover Type Title (only if not empty)
    if cover_type_title and cover_type_title.strip():
        max_title_w = page_w - (details_x + label_w + 16 * mm)
        type_title_label = f"{cover_type} Title"
        type_title_lines = _wrap_text(c, cover_type_title, details_font_name, 15, max_width=max_title_w)
        
        c.setFont("Times-Bold", 15)
        c.drawString(details_x, current_y, type_title_label)
        c.setFont(details_font_name, 15)
        c.drawString(details_x + label_w, current_y, f": {type_title_lines[0]}")
        
        # Handle wrapped lines
        if len(type_title_lines) > 1:
            indent_x = details_x + label_w + c.stringWidth(": ", details_font_name, 15)
            for i, line in enumerate(type_title_lines[1:], 1):
                current_y -= row_gap
                c.drawString(indent_x, current_y, line)
        
        current_y -= row_gap
    
    # Course Code
    _draw_detail_row(c, "Course Code", course_code, details_x, current_y, label_w, detail_label_font, detail_value_font)
    current_y -= row_gap

    # Course Title
    max_title_w = page_w - (details_x + label_w + 16 * mm)
    title_lines = _wrap_text(c, course_title, details_font_name, 15, max_width=max_title_w)

    c.setFont("Times-Bold", 15)
    c.drawString(details_x, current_y, "Course Title")
    c.setFont(details_font_name, 15)
    c.drawString(details_x + label_w, current_y, f": {title_lines[0]}")

    if len(title_lines) > 1:
        indent_x = details_x + label_w + c.stringWidth(": ", details_font_name, 15)
        current_y -= row_gap
        c.drawString(indent_x, current_y, title_lines[1])
    
    current_y -= row_gap

    # Date of Experiment (only if provided - mainly for lab reports)
    if date_of_exp and date_of_exp.strip():
        _draw_detail_row(c, "Date of Experiment", date_of_exp, details_x, current_y, label_w, detail_label_font, detail_value_font)
        current_y -= row_gap
    
    # Date of Submission
    _draw_detail_row(c, "Date of Submission", date_of_submission, details_x, current_y, label_w, detail_label_font, detail_value_font)

    # Bottom table
    table_w = page_w - 2 * margin_x
    table_x = margin_x
    table_y = 18 * mm
    header_h = 10 * mm
    body_h = 38 * mm
    table_h = header_h + body_h

    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    header_color = colors.HexColor("#2E86D6")
    c.setFillColor(header_color)
    c.rect(table_x, table_y + body_h, table_w, header_h, fill=1, stroke=0)
    c.setFillColor(colors.white)

    c.setFont("Times-Bold", 11)
    mid_x = table_x + table_w / 2.0
    c.drawCentredString((table_x + mid_x) / 2.0, table_y + body_h + 3 * mm, "SUBMITTED BY:")
    c.drawCentredString((mid_x + table_x + table_w) / 2.0, table_y + body_h + 3 * mm, "SUBMITTED TO:")

    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(mid_x, table_y, mid_x, table_y + table_h)

    c.setFillColor(colors.black)

    cell_w = table_w / 2.0
    left_cell_x = table_x
    right_cell_x = table_x + cell_w
    body_top_y = table_y + body_h

    font_body = "Times-Roman"
    size_body = 12

    left_block = "\n".join(
        [
            full_name,
            f"Roll:  {roll_no}",
            f"Section: {section}",
            f"Session: {session}",
        ]
    )

    right_block = "\n".join(
        [
            teacher_name,
            teacher_designation,
            teacher_dept,
        ]
    )

    _draw_wrapped_block_in_cell(
        c,
        left_block,
        left_cell_x,
        body_top_y,
        cell_w,
        body_h,
        font=font_body,
        size=size_body,
        padding=6 * mm,
        line_gap=6.0 * mm,
    )

    _draw_wrapped_block_in_cell(
        c,
        right_block,
        right_cell_x,
        body_top_y,
        cell_w,
        body_h,
        font=font_body,
        size=size_body,
        padding=6 * mm,
        line_gap=6.0 * mm,
    )

    c.showPage()
    c.save()
    return out_path


# -----------------------------
# Demo / Local test runs
# -----------------------------
if __name__ == "__main__":
    # Example 1: Lab Report (Experiment)
    print("Generating Lab Report cover...")
    generate_ruet_cover_pdf(
        output_path="../assets/pdf/ruet_lab_report_cover.pdf",
        cover_type="Experiment",
        cover_type_no="01",
        cover_type_title="Flow Chart",  # Optional
        course_code="CSE 1201",
        course_title="Digital Logic Design Sessional",
        date_of_exp="31 January 2026",
        date_of_submission="7 February 2026",
        full_name="Taieb Mahmud Rafin",
        roll_no="2303137",
        section="C",
        dept="Department of Computer Science & Engineering",
        series="23 Series",
        session="2023-24",
        teacher_name="Emrana Kabir Hashi",
        teacher_designation="Assistant Professor",
        teacher_dept="Dept. of Computer Science & Engineering, RUET",
        logo_path="../assets/images/ruet_logo.png",
        alice_ttf_path="../assets/fonts/Alice-Regular.ttf",
        futura_ttf_path="../assets/fonts/Futura.ttf",
        cormorant_ttf_path="../assets/fonts/CormorantGaramond-Light.ttf",
    )
    print("✓ Generated: ruet_lab_report_cover.pdf\n")

    # Example 2: Assignment (without experiment date, without type title)
    print("Generating Assignment cover...")
    generate_ruet_cover_pdf(
        output_path="../assets/pdf/ruet_assignment_cover.pdf",
        cover_type="Assignment",
        cover_type_no="03",
        cover_type_title="",  # Empty - won't be shown
        course_code="CSE 2104",
        course_title="Data Structure and Algorithm",
        date_of_exp="",  # No experiment date for assignments
        date_of_submission="15 February 2026",
        full_name="Tahsan Uddin Mahim Al Azad",
        roll_no="2303133",
        section="C",
        dept="Department of Computer Science & Engineering",
        series="23 Series",
        session="2023-24",
        teacher_name="Dr. Md. Abdur Razzaque",
        teacher_designation="Professor",
        teacher_dept="Dept. of Computer Science & Engineering, RUET",
        logo_path="../assets/images/ruet_logo.png",
        alice_ttf_path="../assets/fonts/Alice-Regular.ttf",
        futura_ttf_path="../assets/fonts/Futura.ttf",
        cormorant_ttf_path="../assets/fonts/CormorantGaramond-Light.ttf",
    )
    print("✓ Generated: ruet_assignment_cover.pdf\n")

    # Example 3: Report (with type title)
    print("Generating Report cover...")
    generate_ruet_cover_pdf(
        output_path="../assets/pdf/ruet_report_cover.pdf",
        cover_type="Report",
        cover_type_no="01",
        cover_type_title="Machine Learning Applications in Healthcare",
        course_code="CSE 4107",
        course_title="Software Engineering and Information System Design Sessional",
        date_of_exp="",  # No experiment date for reports
        date_of_submission="20 February 2026",
        full_name="Md. Zahirul Islam",
        roll_no="2303140",
        section="C",
        dept="Department of Computer Science & Engineering",
        series="23 Series",
        session="2023-24",
        teacher_name="Md. Shariful Islam",
        teacher_designation="Associate Professor",
        teacher_dept="Dept. of Computer Science & Engineering, RUET",
        logo_path="../assets/images/ruet_logo.png",
        alice_ttf_path="../assets/fonts/Alice-Regular.ttf",
        futura_ttf_path="../assets/fonts/Futura.ttf",
        cormorant_ttf_path="../assets/fonts/CormorantGaramond-Light.ttf",
    )
    print("✓ Generated: ruet_report_cover.pdf")
