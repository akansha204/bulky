from datetime import date

from pypdf import PdfReader

from app.certificates import generate_certificate


def test_fixed_template_contains_recipient_and_event(tmp_path) -> None:
    path = tmp_path / "certificate.pdf"
    generate_certificate(path, "Ada Lovelace", "Python Workshop", date(2026, 10, 7))

    reader = PdfReader(path)
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "CERTIFICATE OF COMPLETION" in text
    assert "Ada Lovelace" in text
    assert "Python Workshop" in text
    assert "October 07, 2026" in text


def test_long_name_and_title_are_kept_on_the_pdf(tmp_path) -> None:
    path = tmp_path / "long.pdf"
    name = "A Very Long Recipient Name With Several Words That Must Wrap Across The Certificate"
    title = "An Extended Python Course Covering Web APIs, Databases, Testing, and Background Jobs"
    generate_certificate(path, name, title, date(2026, 10, 7))

    text = PdfReader(path).pages[0].extract_text()
    assert "A Very Long Recipient Name" in text
    assert "Background Jobs" in text
