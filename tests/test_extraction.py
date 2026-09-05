"""
Getting text out of an uploaded resume.

Every fixture here is a real file — a PDF written by a real PDF writer, a
scan that is genuinely an image with no text layer, a Word document whose
content lives inside a table. Mocking the extractors would test the mocks; the
failure modes worth catching are all in what these libraries actually do with
a real file.
"""

from pathlib import Path

import pytest

from extraction import MAX_PDF_PAGES, MIN_USEFUL_CHARS, SUPPORTED, ExtractionError, extract_text

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ---------------------------------------------------------------- happy path --


@pytest.mark.parametrize(
    "filename", ["resume.pdf", "resume.docx", "table_resume.docx", "resume.txt", "utf16.txt"]
)
def test_every_supported_format_yields_the_same_resume(filename):
    text = extract_text(load(filename), filename)
    assert "Jordan Avery Blake" in text
    assert "AI Engineering Intern" in text
    assert "Placeholder Labs" in text


def test_a_docx_built_entirely_from_a_table_is_not_empty():
    # A very common template shape, and document.paragraphs does not reach
    # inside a table — this would extract to nothing without the table walk.
    text = extract_text(load("table_resume.docx"), "table_resume.docx")
    assert "Backend Intern" in text
    assert len(text) > MIN_USEFUL_CHARS


def test_a_utf16_text_file_is_read_as_text():
    # UTF-16LE writes every ASCII character as a byte followed by NUL, which
    # is exactly what a binary sniff looks for. Notepad still writes these.
    assert "Jordan Avery Blake" in extract_text(load("utf16.txt"), "utf16.txt")


def test_line_structure_survives_extraction():
    # The roast quotes the resume back, so the bullets have to stay separate
    # lines rather than collapsing into one paragraph.
    text = extract_text(load("resume.pdf"), "resume.pdf")
    assert text.count("\n") > 5


# ------------------------------------------------------------------ cleaning --


def test_runs_of_blank_lines_are_collapsed():
    raw = b"Name\n\n\n\n\n\nExperience\n\n\n\nSkills\n" + b"x" * MIN_USEFUL_CHARS
    assert "\n\n\n" not in extract_text(raw, "cv.txt")


def test_trailing_whitespace_is_stripped_from_every_line():
    raw = b"Name   \nExperience\t\n" + b"x" * MIN_USEFUL_CHARS
    assert not any(line != line.rstrip() for line in extract_text(raw, "cv.txt").split("\n"))


def test_windows_line_endings_are_normalised():
    raw = b"Name\r\nExperience\r\n" + b"x" * MIN_USEFUL_CHARS
    assert "\r" not in extract_text(raw, "cv.txt")


def test_the_words_themselves_are_left_alone():
    # Reflowing or de-hyphenating would change what the model sees, and so
    # what it says. Cleaning is whitespace only.
    body = "Built an LLM-powered summariser using Python 3.11 & FastAPI (2026)."
    raw = (body + "\n" + "x" * MIN_USEFUL_CHARS).encode()
    assert body in extract_text(raw, "cv.txt")


def test_non_breaking_spaces_become_ordinary_ones():
    raw = ("Jordan\xa0Blake\n" + "x" * MIN_USEFUL_CHARS).encode()
    assert "Jordan Blake" in extract_text(raw, "cv.txt")


# ------------------------------------------------------------- what it refuses --


def test_a_scanned_pdf_says_it_is_a_scan():
    # pypdf reads an image-only page as an empty string without complaining,
    # so without the length check this uploads as a blank resume and the model
    # gets paid to roast nothing.
    with pytest.raises(ExtractionError, match="scan"):
        extract_text(load("scanned.pdf"), "scanned.pdf")


def test_a_password_protected_pdf_says_so():
    with pytest.raises(ExtractionError, match="password"):
        extract_text(load("encrypted.pdf"), "encrypted.pdf")


def test_an_image_is_refused_by_content_not_by_name():
    # Named .pdf, and still an image. The filename is a claim, not evidence.
    with pytest.raises(ExtractionError, match="does not look like"):
        extract_text(load("image.png"), "resume.pdf")


def test_an_empty_file_says_it_is_empty():
    with pytest.raises(ExtractionError, match="empty"):
        extract_text(b"", "resume.pdf")


def test_a_zip_that_is_not_a_docx_says_so():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "not a word document")
    with pytest.raises(ExtractionError, match="not a Word document"):
        extract_text(buffer.getvalue(), "resume.docx")


def test_truncated_pdf_bytes_do_not_raise_something_unhandled():
    # Half a PDF is what an interrupted upload looks like. Whatever pypdf does
    # with it, the caller has to get an ExtractionError with a message.
    truncated = load("resume.pdf")[:400]
    with pytest.raises(ExtractionError):
        extract_text(truncated, "resume.pdf")


def test_a_text_file_of_almost_nothing_is_still_accepted():
    # Text files are not length-checked: if somebody pastes a two-line resume
    # into a .txt, that is their business and the roast will cover it.
    assert extract_text(b"Jordan Blake\nPython", "cv.txt") == "Jordan Blake\nPython"


# --------------------------------------------------------------------- limits --


def test_a_very_long_pdf_is_read_up_to_the_page_cap():
    # 25 pages in the fixture. A resume is one or two; the rest is not read.
    from pypdf import PdfReader

    reader = PdfReader(str(FIXTURES / "long.pdf"))
    assert len(reader.pages) > MAX_PDF_PAGES, "the fixture should exceed the cap"

    text = extract_text(load("long.pdf"), "long.pdf")
    assert text.count("Jordan Avery Blake") == MAX_PDF_PAGES


# ------------------------------------------------------------------ the table --


def test_the_supported_map_is_the_single_source_of_truth():
    # The endpoint and the file picker are both built from this, so it has to
    # stay well-formed: dotted lowercase extensions, human labels.
    assert ".pdf" in SUPPORTED
    for extension, label in SUPPORTED.items():
        assert extension.startswith(".") and extension.islower(), extension
        assert label and not label.startswith("."), label


# ------------------------------------------------------------ damaged files --


def _corrupt(data: bytes) -> bytes:
    """Flip one byte in the middle — what a bad download or bad disk produces."""
    middle = len(data) // 2
    return data[:middle] + bytes([data[middle] ^ 0xFF]) + data[middle + 1 :]


def test_a_corrupted_pdf_raises_extraction_error_not_something_random():
    # pypdf raises whatever the malformed structure happens to produce —
    # ValueError from an Ascii85 decoder, KeyError, struct.error. Unhandled,
    # those reach the browser as a 500 and read as "upload is broken".
    with pytest.raises(ExtractionError):
        extract_text(_corrupt(load("resume.pdf")), "resume.pdf")


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.4\n",
        b"%PDF-1.7\n" + b"\xde\xad\xbe\xef" * 400,
        b"%PDF-1.4\n" + bytes(range(256)) * 8,
    ],
)
def test_pdf_shaped_garbage_is_always_an_extraction_error(data):
    with pytest.raises(ExtractionError):
        extract_text(data, "resume.pdf")


def test_a_corrupted_docx_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_text(_corrupt(load("resume.docx")), "resume.docx")


def test_nothing_escapes_as_anything_but_an_extraction_error():
    # A blunt sweep. Whatever is thrown at the extractor, the caller only ever
    # has to catch ExtractionError — anything else reaches the browser as a
    # 500 and reads, correctly, as "the upload is broken".
    samples = [
        b"", b"\x00", b"%PDF-", b"PK\x03\x04", b"PK\x03\x04" + b"\x00" * 100,
        bytes(range(256)), b"\xff\xfe", b"\xef\xbb\xbf",
        load("resume.pdf")[:50], load("resume.docx")[:50],
    ]
    for sample in samples:
        try:
            extract_text(sample, "resume.pdf")
        except ExtractionError:
            pass  # the contract
