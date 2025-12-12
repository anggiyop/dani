import pdfplumber
import mysql.connector
import re

# =========================
# KONFIGURASI
# =========================

PDF_PATH = r"D:\ANGGI\dani\chatbot-va-usu\storage\dokumen\SOP-ULT-2023.pdf"
DOKUMEN_ID = 1  # id di tabel dokumen_kb untuk SOP-ULT-2023.pdf

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "asisten_mhs",
}

# Halaman PDF yang berisi SOP (nomor halaman CETAK, 1-based)
START_PAGE = 9
END_PAGE = 120


# =========================
# FUNGSI BANTU
# =========================

def norm(s: str | None) -> str:
    """Bersihkan string (strip + compress whitespace)."""
    if not s:
        return ""
    return " ".join(str(s).strip().split())


# Mapping komponen → jenis canon
KOMPONEN_MAPPING = {
    "persyaratan": {
        "keywords": ["persyaratan"],
        "judul_komp": "Persyaratan Pelayanan",
    },
    "sistem_prosedur": {
        "keywords": ["mekanisme", "prosedur", "sistem"],
        "judul_komp": "Sistem, Mekanisme, dan Prosedur",
    },
    "jangka_waktu": {
        "keywords": ["jangka waktu"],
        "judul_komp": "Jangka Waktu Penyelesaian",
    },
    "biaya": {
        "keywords": ["biaya", "tarif"],
        "judul_komp": "Biaya/Tarif",
    },
    "produk": {
        "keywords": ["produk layanan", "produk pelayanan", "produk"],
        "judul_komp": "Produk Layanan",
    },
    "pengaduan": {
        "keywords": ["pengaduan", "keberatan", "saran", "masukan"],
        "judul_komp": "Penanganan, Pengaduan, Saran dan Masukan",
    },
}


def map_komponen_to_jenis(komponen: str) -> str | None:
    """Mapping teks kolom 'Komponen' ke salah satu jenis canon."""
    if not komponen:
        return None
    k = komponen.lower()

    for jenis, cfg in KOMPONEN_MAPPING.items():
        for kw in cfg["keywords"]:
            if kw in k:
                return jenis
    return None


def split_langkah(uraian: str) -> list[str]:
    """
    Pecah teks 'a. ... b. ... c. ...' menjadi list langkah.
    Dipakai untuk menghasilkan sop_step dari Sistem/Mekanisme/Prosedur.
    """
    if not uraian:
        return []
    text = uraian.replace("\n", " ")
    text = " ".join(text.split())

    parts = re.split(r"([a-z]\.)", text)
    langkah = []
    current_label = None
    current_text = ""

    for part in parts:
        if re.fullmatch(r"[a-z]\.", part):
            if current_label and current_text.strip():
                langkah.append(current_text.strip())
            current_label = part
            current_text = ""
        else:
            current_text += " " + part

    if current_label and current_text.strip():
        langkah.append(current_text.strip())

    return [l for l in langkah if l]


def detect_judul_with_y(page) -> tuple[str | None, float | None]:
    """
    Deteksi judul SOP pada sebuah page + koordinat Y-nya.

    Strategi:
    - Ambil semua words, group per baris berdasarkan "top".
    - Buat teks baris; judul valid jika:
      - pola 'NN. STANDAR PELAYANAN ...', atau
      - khusus SOP 50: '50. PENGUNDURAN DIRI BAGI DOSEN ...'
    """
    words = page.extract_words()
    if not words:
        return None, None

    words_sorted = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = []
    current_top = None
    current_line = []
    threshold = 3  # toleransi 'top' untuk 1 baris

    for w in words_sorted:
        if current_top is None:
            current_top = w["top"]
            current_line = [w]
            continue

        if abs(w["top"] - current_top) <= threshold:
            current_line.append(w)
        else:
            lines.append((current_top, current_line))
            current_top = w["top"]
            current_line = [w]

    if current_line:
        lines.append((current_top, current_line))

    for top, line_words in lines:
        text = " ".join(w["text"] for w in line_words)
        normtext = re.sub(r"\s+", " ", text).strip()
        low = normtext.lower()

        # Khusus SOP 50: di halaman SOP judulnya tidak ada kata "Standar Pelayanan"
        if re.match(r"^50\.\s*pengunduran diri bagi dosen", low):
            title = (
                "50. STANDAR PELAYANAN PENGUNDURAN DIRI BAGI DOSEN "
                "DAN TENAGA KEPENDIDIKAN"
            )
            return title, top

        # Judul SOP normal
        if re.match(r"^\d+\.\s*standar pelayanan", low):
            return normtext, top

    return None, None


def get_or_create_unit_ult(cur) -> int:
    """Pastikan ada unit_layanan 'Unit Layanan Terpadu', return id-nya."""
    cur.execute(
        "SELECT id FROM unit_layanan WHERE nama_unit = %s",
        ("Unit Layanan Terpadu",),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO unit_layanan (nama_unit, deskripsi) VALUES (%s, %s)",
        ("Unit Layanan Terpadu", "Unit Layanan Terpadu Universitas Sumatera Utara"),
    )
    return cur.lastrowid


# =========================
# MAIN INDEXING
# =========================

def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(buffered=True)

    unit_ult_id = get_or_create_unit_ult(cur)
    conn.commit()

    with pdfplumber.open(PDF_PATH) as pdf:
        num_pages = len(pdf.pages)
        print(f"PDF memiliki {num_pages} halaman.")

        current_sop = None
        sop_counter = 0  # hanya untuk log; kode_sop pakai nomor di judul

        def flush_current_sop():
            """Simpan SOP aktif ke DB (sop, sop_komponen, sop_step, dokumen_chunk)."""
            nonlocal sop_counter, current_sop

            if not current_sop:
                return

            raw_title = current_sop["judul"]
            halaman_awal = current_sop["halaman_awal"]
            komponen_text = current_sop["komponen_text"]
            no_sop = current_sop["no"]

            # Bersihkan nomor di depan judul untuk field judul_sop
            m = re.match(r"^\s*(\d+)[\.\)]\s*(.*)$", raw_title)
            if m:
                judul_sop = m.group(2).strip()
            else:
                judul_sop = raw_title.strip()

            sop_counter += 1
            if no_sop is None:
                no_sop = sop_counter
            kode_sop = f"SOP-ULT-{no_sop:03d}"

            missing = [j for j, v in komponen_text.items() if not v]
            print(
                f"[FLUSH] SOP no {no_sop} (#{sop_counter}): {judul_sop} "
                f"(hal {halaman_awal}) | missing komponen: {missing}"
            )

                        # 1) insert ke sop (tanpa deskripsi_singkat & tanpa tanggal_berlaku & tanpa halaman_pdf)
            cur.execute(
                """
                INSERT INTO sop
                    (kode_sop, judul_sop, unit_layanan_id,
                     kategori_layanan, sasaran_layanan,
                     file_url)
                VALUES
                    (%s, %s, %s,
                     %s, %s,
                     %s)
                """,
                (
                    kode_sop,
                    judul_sop,
                    unit_ult_id,
                    None,   # kategori_layanan (diisi kemudian via UPDATE)
                    None,   # sasaran_layanan (diisi kemudian via UPDATE)
                    "storage/dokumen/sop/SOP-ULT-2023.pdf",
                ),
            )
            sop_id = cur.lastrowid

            no_chunk = 1

            # 2) sop_komponen + chunk komponen
            for jenis, teks in komponen_text.items():
                if not teks:
                    continue

                mapping_cfg = KOMPONEN_MAPPING.get(jenis, {})
                judul_komp = mapping_cfg.get("judul_komp", jenis)

                isi = norm(teks)

                # sop_komponen
                cur.execute(
                    """
                    INSERT INTO sop_komponen (sop_id, jenis, judul, isi, halaman)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (sop_id, jenis, judul_komp, isi, halaman_awal),
                )

                # dokumen_chunk untuk komponen
                isi_chunk = f"{judul_sop} - {judul_komp}: {isi}"
                cur.execute(
                    """
                    INSERT INTO dokumen_chunk
                        (dokumen_id, sop_id, no_urut, isi_chunk, halaman, bagian)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                    """,
                    (DOKUMEN_ID, sop_id, no_chunk, isi_chunk, halaman_awal, jenis),
                )
                no_chunk += 1

            # 3) sop_step dari sistem_prosedur + chunk langkah
            sistem_text = komponen_text.get("sistem_prosedur", "")
            langkah_list = split_langkah(sistem_text)
            step_no = 1
            for langkah in langkah_list:
                langkah = norm(langkah)
                if not langkah:
                    continue

                # sop_step
                cur.execute(
                    """
                    INSERT INTO sop_step (sop_id, no_urut, deskripsi)
                    VALUES (%s, %s, %s)
                    """,
                    (sop_id, step_no, langkah),
                )

                # dokumen_chunk untuk langkah
                isi_step_chunk = f"{judul_sop} - Langkah {step_no}: {langkah}"
                cur.execute(
                    """
                    INSERT INTO dokumen_chunk
                        (dokumen_id, sop_id, no_urut, isi_chunk, halaman, bagian)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        DOKUMEN_ID,
                        sop_id,
                        no_chunk,
                        isi_step_chunk,
                        halaman_awal,
                        "langkah",
                    ),
                )
                no_chunk += 1
                step_no += 1

            conn.commit()
            current_sop = None

        # =========================
        # LOOP HALAMAN START_PAGE–END_PAGE
        # =========================
        for page_idx in range(START_PAGE - 1, min(END_PAGE, num_pages)):
            page_no_display = page_idx + 1
            page = pdf.pages[page_idx]

            title, title_y = detect_judul_with_y(page)
            table_objs = page.find_tables()
            table_objs = sorted(table_objs, key=lambda t: t.bbox[1])  # sort by top

            print(f"[PAGE] {page_no_display} | title={title} | title_y={title_y}")

            def process_table_into(sop_dict, tbl_obj):
                """Parse 1 tabel dan gabungkan ke komponen_text SOP yang diberikan."""
                rows = tbl_obj.extract()
                if not rows:
                    return

                header_row = rows[0]
                komponen_idx = 1
                uraian_idx = 2
                start_row = 0

                header_text = " ".join((c or "") for c in header_row).lower()
                if "komponen" in header_text or "uraian" in header_text:
                    for i, cell in enumerate(header_row):
                        cell_l = (cell or "").lower()
                        if "komponen" in cell_l:
                            komponen_idx = i
                        if "uraian" in cell_l:
                            uraian_idx = i
                    start_row = 1  # skip header

                for row in rows[start_row:]:
                    if len(row) <= max(komponen_idx, uraian_idx):
                        continue

                    komponen = norm(row[komponen_idx])
                    uraian = norm(row[uraian_idx])

                    if not komponen or not uraian:
                        continue

                    jenis = map_komponen_to_jenis(komponen)
                    if jenis is None:
                        continue

                    prev = sop_dict["komponen_text"].get(jenis, "")
                    if prev:
                        if uraian not in prev:
                            sop_dict["komponen_text"][jenis] = (
                                prev + " " + uraian
                            ).strip()
                    else:
                        sop_dict["komponen_text"][jenis] = uraian

            # ----- KASUS: halaman mengandung judul SOP baru -----
            if title:
                # parsing nomor SOP dari judul
                m_no = re.match(r"\s*(\d+)\.", title)
                no_sop = int(m_no.group(1)) if m_no else None

                if current_sop is None:
                    # SOP pertama dimulai di halaman ini
                    current_sop = {
                        "judul": title,
                        "no": no_sop,
                        "halaman_awal": page_no_display,
                        "komponen_text": {k: "" for k in KOMPONEN_MAPPING.keys()},
                    }
                    sop_counter += 1
                    print(f"  [NEW] SOP no {no_sop} (#{sop_counter}) dimulai di halaman ini.")

                    # semua tabel dengan top >= title_y dianggap milik SOP ini
                    for t in table_objs:
                        t_top = t.bbox[1]
                        if title_y is None or t_top >= title_y:
                            process_table_into(current_sop, t)
                    continue

                else:
                    # sudah ada SOP sebelumnya; judul baru berarti SOP lama selesai
                    # 1) tabel di atas judul baru → milik SOP lama
                    for t in table_objs:
                        t_top, t_bottom = t.bbox[1], t.bbox[3]
                        if title_y is not None and t_bottom <= title_y:
                            process_table_into(current_sop, t)

                    # 2) flush SOP lama
                    flush_current_sop()

                    # 3) mulai SOP baru
                    current_sop = {
                        "judul": title,
                        "no": no_sop,
                        "halaman_awal": page_no_display,
                        "komponen_text": {k: "" for k in KOMPONEN_MAPPING.keys()},
                    }
                    sop_counter += 1
                    print(f"  [NEW] SOP no {no_sop} (#{sop_counter}) dimulai di halaman ini.")

                    # 4) tabel di bawah judul baru → milik SOP baru
                    for t in table_objs:
                        t_top = t.bbox[1]
                        if title_y is None or t_top >= title_y:
                            process_table_into(current_sop, t)
                    continue

            # ----- KASUS: halaman TANPA judul SOP baru -----
            if not title and current_sop is not None:
                # semua tabel di halaman ini milik SOP yang sedang aktif
                for t in table_objs:
                    process_table_into(current_sop, t)

        # flush SOP terakhir
        flush_current_sop()

    # update status dokumen_kb
    cur.execute(
        """
        UPDATE dokumen_kb
        SET status_indexing = 'sukses'
        WHERE id = %s
        """,
        (DOKUMEN_ID,),
    )
    conn.commit()

    cur.close()
    conn.close()
    print("Selesai indexing semua SOP.")


if __name__ == "__main__":
    main()
