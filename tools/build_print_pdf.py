"""Build the Arabic booklet PDFs for print — an editable version first, then the print version.

    python tools/build_print_pdf.py                       # both files, from index.html
    python tools/build_print_pdf.py --ai                  # also the layered Illustrator file
    python tools/build_print_pdf.py --from EDITED.pdf     # print file from an edited editable PDF

Files in print/:
  discover-islam-booklet-ar-EDITABLE.pdf  live text (fonts embedded), every photo, shape and text
                                          block a separate object; CMYK; 3mm bleed; crop marks on
                                          their own "Crop marks" layer. Make last-minute changes here
                                          (Acrobat Pro or Illustrator), then run --from on it.
  discover-islam-booklet-ar-PRINT-READY.pdf     the same, with all text converted to outlines — send this.

Layout (16 pages): cover, pages 2–11, the 12–13 spread split into two pages, two blank pages,
back cover. Bleed, the split spread and the blanks come from index.html?print=bleed.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "print"
EDITABLE = OUT_DIR / "discover-islam-booklet-ar-EDITABLE.pdf"
PRINT = OUT_DIR / "discover-islam-booklet-ar-PRINT-READY.pdf"
AI = OUT_DIR / "discover-islam-booklet-ar-EDITABLE.ai"
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
GS = os.environ.get("GS", r"C:\Program Files\gs\gs10.08.0\bin\gswin64c.exe")
ICC = os.environ.get("CMYK_ICC", r"C:\Program Files (x86)\Common Files\Adobe\Color\Profiles\Recommended\CoatedFOGRA39.icc")

MM = 72 / 25.4
OFFSET = 10 * MM                  # trim sits 10mm in from the sheet's top-left (3mm bleed + 7mm for marks)
TRIM_W, TRIM_H, BLEED = 210 * MM, 148 * MM, 3 * MM
MARK_GAP, MARK_LEN = 3 * MM, 6 * MM
REGISTRATION = (1, 1, 1, 1)       # CMYK, for crop marks


def chrome_pdf(dest):
    url = (ROOT / "index.html").as_uri() + "?lang=ar&print=bleed"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
                    f"--print-to-pdf={dest}", url], check=True, capture_output=True)


def ghostscript(src, dest, outline):
    args = [GS, "-dNOPAUSE", "-dBATCH", "-dSAFER", f"--permit-file-read={ICC}", "-dQUIET",
            "-sDEVICE=pdfwrite", "-sColorConversionStrategy=CMYK", "-sProcessColorModel=DeviceCMYK",
            f"-sOutputICCProfile={ICC}", "-dRenderIntent=1", "-dAutoRotatePages=/None",
            "-dDownsampleColorImages=false", "-dDownsampleGrayImages=false", "-dPassThroughJPEGImages=true",
            "-dColorImageFilter=/DCTEncode", "-dJPEGQ=95"]
    if outline:
        args.append("-dNoOutputFonts")  # every glyph becomes a vector path
    subprocess.run(args + [f"-sOutputFile={dest}", str(src)], check=True)


def boxes_for(page):
    trim = fitz.Rect(OFFSET, OFFSET, OFFSET + TRIM_W, OFFSET + TRIM_H)
    bleed = fitz.Rect(trim.x0 - BLEED, trim.y0 - BLEED, trim.x1 + BLEED, trim.y1 + BLEED)
    return trim, bleed & page.mediabox


def add_marks_and_boxes(path, dest):
    doc = fitz.open(path)
    layer = doc.add_ocg("Crop marks", on=True)
    for page in doc:
        trim, bleed = boxes_for(page)
        shape = page.new_shape()
        for x in (trim.x0, trim.x1):
            shape.draw_line((x, trim.y0 - MARK_GAP - MARK_LEN), (x, trim.y0 - MARK_GAP))
            shape.draw_line((x, trim.y1 + MARK_GAP), (x, trim.y1 + MARK_GAP + MARK_LEN))
        for y in (trim.y0, trim.y1):
            shape.draw_line((trim.x0 - MARK_GAP - MARK_LEN, y), (trim.x0 - MARK_GAP, y))
            shape.draw_line((trim.x1 + MARK_GAP, y), (trim.x1 + MARK_GAP + MARK_LEN, y))
        shape.finish(color=REGISTRATION, width=0.25, oc=layer)
        shape.commit()
        page.set_bleedbox(bleed)
        page.set_trimbox(trim)
    doc.set_metadata({"title": "Discover Islam booklet (Arabic)", "producer": "build_print_pdf.py"})
    doc.save(dest, garbage=4, deflate=True)


def copy_boxes(src_path, dest_path):
    """Ghostscript may drop TrimBox/BleedBox — put the editable file's boxes back on the print file."""
    src, doc = fitz.open(src_path), fitz.open(dest_path)
    for s, d in zip(src, doc):
        d.set_bleedbox(s.bleedbox)
        d.set_trimbox(s.trimbox)
    doc.save(dest_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)


def make_print(editable):
    tmp = OUT_DIR / "_outlined.pdf"
    ghostscript(editable, tmp, outline=True)
    shutil.move(tmp, PRINT)
    copy_boxes(editable, PRINT)


def build_ai(editable, pages):
    """Layered Illustrator file via tools/build_ai.jsx (needs Illustrator; takes a few minutes)."""
    jsx = ROOT / "tools" / "build_ai.jsx"
    ps = (f'$ai = New-Object -ComObject "Illustrator.Application"; '
          f'$ai.DoJavaScriptFile("{jsx}", @("{editable.as_posix()}", "{AI.as_posix()}", "{pages}"))')
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def report(path):
    doc = fitz.open(path)
    fonts = sum(1 for x in range(1, doc.xref_length()) if doc.xref_get_key(x, "Type") == ("name", "/Font"))
    t = doc[0].trimbox
    print(f"  {path.name}: {doc.page_count} pages, {path.stat().st_size / 1e6:.1f} MB, "
          f"font objects {fonts}, trim {t.width / MM:.0f}x{t.height / MM:.0f}mm")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", type=Path, help="make the PRINT file from this (edited) editable PDF")
    ap.add_argument("--ai", action="store_true", help="also build the layered Illustrator file (needs Illustrator)")
    a = ap.parse_args()
    OUT_DIR.mkdir(exist_ok=True)
    if a.src:
        print("outlining text in", a.src, "..."); make_print(a.src.resolve())
        report(PRINT)
        return
    raw, cmyk = OUT_DIR / "_chrome.pdf", OUT_DIR / "_cmyk.pdf"
    print("1/3 printing from Chrome..."); chrome_pdf(raw)
    print("2/3 editable version (CMYK, live text, crop-mark layer)...")
    ghostscript(raw, cmyk, outline=False); add_marks_and_boxes(cmyk, EDITABLE)
    print("3/3 print version (text to outlines)..."); make_print(EDITABLE)
    for tmp in (raw, cmyk):
        try:
            tmp.unlink()
        except OSError:
            pass  # still open in a viewer or scanner; harmless, overwritten next run
    report(EDITABLE); report(PRINT)
    if a.ai:
        print("4/4 layered Illustrator file (progress in print/*.ai.log)...")
        build_ai(EDITABLE, fitz.open(EDITABLE).page_count)
        print(f"  {AI.name}: {AI.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    sys.exit(main())
