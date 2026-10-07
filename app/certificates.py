"""Single predefined certificate design."""

from datetime import date
from pathlib import Path
from threading import Lock

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_font_lock = Lock()


def _font() -> str:
    """Use the TrueType font distributed with ReportLab."""
    font_name = "CertificateVera"
    with _font_lock:
        if font_name not in pdfmetrics.getRegisteredFontNames():
            import reportlab

            font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    return font_name


def _wrap(text: str, font: str, size: int, available_width: float) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}" if line else word
        if pdfmetrics.stringWidth(candidate, font, size) <= available_width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = ""
        for char in word:
            if line and pdfmetrics.stringWidth(line + char, font, size) > available_width:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines


def _draw_fitted(
    pdf: canvas.Canvas, text: str, font: str, width: float, y: float,
    available_width: float, desired_size: int, max_lines: int,
) -> None:
    for size in range(desired_size, 11, -1):
        lines = _wrap(text, font, size, available_width)
        if len(lines) <= max_lines:
            break
    pdf.setFont(font, size)
    for index, line in enumerate(lines):
        pdf.drawCentredString(width / 2, y - index * (size + 5), line)


def generate_certificate(path: Path, name: str, event_title: str, completion_date: date) -> None:
    """Write one landscape A4 PDF to a temporary or final path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    font = _font()
    width, height = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=(width, height))
    pdf.setTitle(f"Certificate for {name}")
    pdf.setFillColor(colors.HexColor("#f8f5ee"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#a37d3d"))
    pdf.setLineWidth(3)
    pdf.rect(28, 28, width - 56, height - 56, fill=0, stroke=1)
    pdf.setStrokeColor(colors.HexColor("#d1b779"))
    pdf.setLineWidth(1)
    pdf.rect(39, 39, width - 78, height - 78, fill=0, stroke=1)

    pdf.setFillColor(colors.HexColor("#25384b"))
    pdf.setFont(font, 20)
    pdf.drawCentredString(width / 2, height - 128, "CERTIFICATE OF COMPLETION")
    pdf.setFont(font, 14)
    pdf.drawCentredString(width / 2, height - 183, "This certificate is presented to")

    pdf.setFillColor(colors.HexColor("#a37d3d"))
    _draw_fitted(pdf, name, font, width, height - 255, width - 120, 36, 3)

    pdf.setFillColor(colors.HexColor("#25384b"))
    pdf.setFont(font, 14)
    pdf.drawCentredString(width / 2, height - 355, "for completing")
    _draw_fitted(pdf, event_title, font, width, height - 390, width - 120, 24, 3)
    pdf.setFont(font, 12)
    pdf.drawCentredString(width / 2, 108, completion_date.strftime("%B %d, %Y"))
    pdf.showPage()
    pdf.save()
