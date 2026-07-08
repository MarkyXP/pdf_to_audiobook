from pathlib import Path

from pdf_oxide import PdfDocument


def extract_paragraphs(pdf_path: Path) -> list[str]:
    """
    Extract text from a PDF, split into paragraphs by blank lines.

    Args:
        pdf_path (pathlib.Path) : Source PDF file

    Returns:
        list[str]: A list of paragraphs

    Example:
        >>> extract_paragraphs("tests/Assets/The-Body-Keeps-the-Score-PDF.pdf")
        '[...]'
    """
    with PdfDocument(pdf_path) as doc:
        raw_text = "".join([page.text for page in doc if page.text.strip()])
    # Split on blank lines to get paragraphs
    paragraphs = [line.strip() for line in raw_text.split("\n") if line.strip()]

    # Merge consecutive short lines into paragraphs
    merged: list[str] = []
    current: list[str] = []
    for p in paragraphs:
        if len(p) < 100 and current:
            current.append(p)
        else:
            if current:
                merged.append(" ".join(current))
            current = [p]
    if current:
        merged.append(" ".join(current))
    return merged


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True, optionflags=doctest.ELLIPSIS)
