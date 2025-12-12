import pdfplumber

PDF_PATH = r"D:\ANGGI\joki\DANI\chatbot-va-usu\storage\dokumen\SOP-ULT-2023.pdf"
START_PAGE = 9
END_PAGE   = 120

def norm(s):
    if not s:
        return ""
    return " ".join(str(s).strip().split())

def detect_judul_sop(page_text: str):
    if not page_text:
        return None
    for line in page_text.splitlines():
        line_norm = norm(line)
        if line_norm.startswith("Standar Pelayanan"):
            return line_norm
    return None

with pdfplumber.open(PDF_PATH) as pdf:
    num_pages = len(pdf.pages)
    print(f"PDF punya {num_pages} halaman")

    for page_num in range(START_PAGE, min(END_PAGE, num_pages) + 1):
        page = pdf.pages[page_num - 1]
        text = page.extract_text() or ""

        judul = detect_judul_sop(text)
        print("=" * 60)
        print(f"Halaman {page_num}")
        print(f"  Judul SOP terdeteksi : {judul}")

        tables = page.extract_tables()
        print(f"  Jumlah tabel         : {len(tables) if tables else 0}")

        if tables:
            for idx, tbl in enumerate(tables):
                if not tbl:
                    continue
                header = " | ".join([c or "" for c in tbl[0]])
                print(f"  Tabel {idx} header   : {header}")
