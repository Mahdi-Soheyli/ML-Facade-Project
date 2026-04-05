"""
Extract embedded raster charts from ASTM E1300 PDF (Annex A1 figures).

Requires: pymupdf. Output: building_code/e1300_data/chart_images/pageNN.png
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "building_code" / "ASTM E1300.pdf"
OUT = ROOT / "building_code" / "e1300_data" / "chart_images"


def main() -> None:
    try:
        import fitz
    except ImportError as e:
        print("Install pymupdf: pip install pymupdf", file=sys.stderr)
        raise e

    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    # PDF page indices 8..51 correspond to printed pages 9..52 (chart pages in E1300-24)
    for i in range(8, min(52, len(doc))):
        page = doc[i]
        for img in page.get_images(full=True):
            xref = img[0]
            if img[2] < 400:
                continue
            pix = fitz.Pixmap(doc, xref)
            if pix.n >= 4:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            path = OUT / f"page{i+1:02d}_chart.png"
            pix.save(str(path))
            print(path.relative_to(ROOT), pix.width, pix.height)
            break
    doc.close()


if __name__ == "__main__":
    main()
