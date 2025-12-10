import pdfplumber
import mysql.connector
import re

# =========================
# KONFIGURASI
# =========================

PDF_PATH = r"D:\ANGGI\joki\DANI\chatbot-va-usu\storage\dokumen\SOP-ULT-2023.pdf"
DOKUMEN_ID = 1   # ganti dengan id di tabel dokumen_kb untuk SOP ULT 2023

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "asisten_mhs"
}

# Halaman PDF yang berisi uraian SOP (1-based index)
START_PAGE = 9
END_PAGE   = 120


# =========================
# FUNGSI BANTU
# =========================

def norm(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(str(s).strip().split())


def map_komponen_to_jenis(komponen: str) -> str | None:
    """
    Mapping nama komponen di kolom 'Komponen' PDF
    ke ENUM sop_komponen.jenis
    """
    k = komponen.lower()
    if "persyaratan" in k:
        return "persyaratan"
    if "sistem" in k and "prosedur" in k:
        return "sistem_prosedur"
    if "jangka waktu" in k:
        return "jangka_waktu"
    if "biaya" in k or "tarif" in k:
        return "biaya"
    if "produk layanan" in k or "produk pelayanan" in k:
        return "produk"
    if "pengaduan" in k or "saran" in k or "masukan" in k:
        return "pengaduan"
    return None


def split_langkah(uraian: str):
    """
    Pecah 'a. ... b. ... c. ...' menjadi list langkah.
    Kalau format di PDF agak beda, regex di sini yang nanti kita tweak.
    """
    if not uraian:
        return []
    text = uraian.replace("\n", " ")
    text = " ".join(text.split())

    # pecah berdasarkan pola "a." "b." "c." dsb
    parts = re.split(r"([a-z]\.)", text)
    langkah = []
    current_label = None
    current_text = ""

    for part in parts:
        if re.fullmatch(r"[a-z]\.", part):
            # label baru
            if current_label and current_text.strip():
                langkah.append(current_text.strip())
            current_label = part
            current_text = ""
        else:
            current_text += " " + part

    if current_label and current_text.strip():
        langkah.append(current_text.strip())

    langkah = [l for l in langkah if l]
    return langkah


def detect_judul_sop(page_text: str) -> str | None:
    """
    Deteksi judul SOP dari teks halaman.
    Normal: baris yang diawali nomor + 'Standar Pelayanan ...'
    Khusus: SOP 50 judulnya tidak mengandung kata 'Standar Pelayanan',
            jadi kita deteksi dengan pola tersendiri.
    """
    if not page_text:
        return None

    for line in page_text.splitlines():
        line_norm = norm(line)
        lower = line_norm.lower()

        # skip baris yang jelas bukan judul SOP
        if "pedoman standar pelayanan" in lower:
            continue
        if "evaluasi kinerja pelaksana" in lower:
            continue

        # CASE NORMAL: "12. Standar Pelayanan ......"
        if "standar pelayanan" in lower:
            # ada nomor di depan
            if re.match(r"^\s*\d+[\.\)]\s*standar pelayanan", lower):
                return line_norm

        # CASE KHUSUS: SOP 50 tidak pakai kata 'standar pelayanan'
        # bentuk di PDF: "50.  PENGUNDURAN DIRI BAGI DOSEN DAN TENAGA KEPENDIDIKAN  NON PNS"
        if re.match(r"^\s*50[\.\)]", lower) \
           and "pengunduran diri bagi dosen" in lower \
           and "tenaga kependidikan" in lower:

            # supaya konsisten dengan SOP lain, kita tambahkan "Standar Pelayanan" di depannya
            # contoh hasil: "50. Standar Pelayanan Pengunduran Diri Bagi Dosen dan Tenaga Kependidikan Non PNS"
            # ambil teks setelah "50." / "50)"
            after_number = re.split(r"^\s*50[\.\)]\s*", line_norm, maxsplit=1)[-1]
            return "50. Standar Pelayanan " + after_number.strip()

    return None


def get_or_create_unit_ult(cur) -> int:
    """
    Pastikan ada unit_layanan 'Unit Layanan Terpadu', return id-nya.
    """
    cur.execute("SELECT id FROM unit_layanan WHERE nama_unit = %s", ("Unit Layanan Terpadu",))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO unit_layanan (nama_unit, deskripsi) VALUES (%s, %s)",
        ("Unit Layanan Terpadu", "Unit Layanan Terpadu Universitas Sumatera Utara")
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

        current_sop = None  # dict: {judul, halaman_awal, komponen_text: {jenis: teks}}
        sop_counter = 0

        def flush_current_sop():
            nonlocal sop_counter, current_sop

            if not current_sop:
                return

            raw_title = current_sop["judul"]           # contoh: "1. Standar Pelayanan Cetak Bukti SPP"
            halaman_awal = current_sop["halaman_awal"]
            komponen_text = current_sop["komponen_text"]

            # --- BERSIHKAN NOMOR DI DEPAN JUDUL --- #
            m = re.match(r"^\s*(\d+)[\.\)]\s*(.*)$", raw_title)
            if m:
                # nomor_urut = int(m.group(1))        # kalau mau dipakai nanti
                judul_sop = m.group(2).strip()        # "Standar Pelayanan Cetak Bukti SPP"
            else:
                judul_sop = raw_title.strip()

            sop_counter += 1
            kode_sop = f"SOP-ULT-{sop_counter:03d}"

            print(f"[FLUSH] SOP #{sop_counter}: {judul_sop} (halaman {halaman_awal})")

            # 1) Insert ke tabel sop (tanpa kolom nomor_urut)
            cur.execute("""
                INSERT INTO sop
                    (kode_sop, judul_sop, deskripsi_singkat, unit_layanan_id,
                    kategori_layanan, sasaran_layanan, tanggal_berlaku,
                    file_url)
                VALUES
                    (%s, %s, %s, %s,
                    %s, %s, %s,
                    %s)
            """, (
                kode_sop,
                judul_sop,
                None,
                unit_ult_id,
                None,
                None,
                None,
                "storage/dokumen/sop/SOP-ULT-2023.pdf"
            ))
            sop_id = cur.lastrowid

            no_chunk = 1

            # 2) Simpan komponen ke sop_komponen + dokumen_chunk
            for jenis, teks in komponen_text.items():
                if not teks:
                    continue

                if jenis == "persyaratan":
                    judul_komp = "Persyaratan Pelayanan"
                elif jenis == "sistem_prosedur":
                    judul_komp = "Sistem, Mekanisme, dan Prosedur"
                elif jenis == "jangka_waktu":
                    judul_komp = "Jangka Waktu Penyelesaian"
                elif jenis == "biaya":
                    judul_komp = "Biaya/Tarif"
                elif jenis == "produk":
                    judul_komp = "Produk Layanan"
                elif jenis == "pengaduan":
                    judul_komp = "Penanganan, Pengaduan, Saran dan Masukan"
                else:
                    judul_komp = jenis

                isi = norm(teks)

                # sop_komponen
                cur.execute("""
                    INSERT INTO sop_komponen (sop_id, jenis, judul, isi, halaman)
                    VALUES (%s, %s, %s, %s, %s)
                """, (sop_id, jenis, judul_komp, isi, halaman_awal))

                # chunk komponen
                isi_chunk = f"{judul_sop} - {judul_komp}: {isi}"
                cur.execute("""
                    INSERT INTO dokumen_chunk
                        (dokumen_id, sop_id, no_urut, isi_chunk, halaman, bagian)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                """, (
                    DOKUMEN_ID,
                    sop_id,
                    no_chunk,
                    isi_chunk,
                    halaman_awal,
                    judul_komp
                ))
                no_chunk += 1

            # 3) Pecah langkah dari sistem_prosedur → sop_step + chunk
            sistem_text = komponen_text.get("sistem_prosedur", "")
            langkah_list = split_langkah(sistem_text)
            step_no = 1
            for langkah in langkah_list:
                langkah = norm(langkah)
                if not langkah:
                    continue

                # sop_step
                cur.execute("""
                    INSERT INTO sop_step (sop_id, no_urut, deskripsi)
                    VALUES (%s, %s, %s)
                """, (sop_id, step_no, langkah))

                # chunk langkah
                isi_step_chunk = f"{judul_sop} - Langkah {step_no}: {langkah}"
                cur.execute("""
                    INSERT INTO dokumen_chunk
                        (dokumen_id, sop_id, no_urut, isi_chunk, halaman, bagian)
                    VALUES
                        (%s, %s, %s, %s, %s, %s)
                """, (
                    DOKUMEN_ID,
                    sop_id,
                    no_chunk,
                    isi_step_chunk,
                    halaman_awal,
                    f"Langkah {step_no}"
                ))
                no_chunk += 1
                step_no += 1

            conn.commit()
            current_sop = None


        # ========== LOOP HALAMAN 9–120 ==========

        for page_num in range(START_PAGE, min(END_PAGE, num_pages) + 1):
            page = pdf.pages[page_num - 1]
            text = page.extract_text() or ""

            print(f"[PAGE] {page_num}")

            # 1) cek judul SOP baru
            judul_baru = detect_judul_sop(text)
            if judul_baru:
                print(f"  Judul SOP terdeteksi: {judul_baru}")

                # kalau sudah ada SOP aktif, simpan dulu ke DB
                flush_current_sop()

                # mulai SOP baru
                current_sop = {
                    "judul": judul_baru,
                    "halaman_awal": page_num,
                    "komponen_text": {
                        "persyaratan": "",
                        "sistem_prosedur": "",
                        "jangka_waktu": "",
                        "biaya": "",
                        "produk": "",
                        "pengaduan": ""
                    }
                }

            if not current_sop:
                print("  [INFO] Belum ada SOP aktif di halaman ini, skip isi tabel.")
                continue

            # 2) Extract tabel di halaman ini
            tables = page.extract_tables()
            print(f"  Jumlah tabel di halaman ini: {len(tables) if tables else 0}")

            if not tables:
                continue

            target_table = None
            for tbl in tables:
                if not tbl or len(tbl) < 2:
                    continue
                header = " ".join([c or "" for c in tbl[0]])
                print(f"    Candidate header: {header}")
                if "Komponen" in header and "Uraian" in header:
                    target_table = tbl
                    break  # pakai HANYA tabel pertama (a. Penyampaian Pelayanan)

            if not target_table:
                print("  [WARN] Tidak menemukan tabel Komponen/Uraian di halaman ini.")
                continue

            # 3) Proses tabel Komponen/Uraian (hanya tabel a)
            tbl = target_table
            rows = tbl[1:]  # skip header
            for row in rows:
                if len(row) < 3:
                    continue
                no, komponen, uraian = row[0], row[1], row[2]
                komponen = norm(komponen)
                uraian = norm(uraian)

                if not komponen or not uraian:
                    continue

                jenis = map_komponen_to_jenis(komponen)
                if jenis is None:
                    print(f"  [INFO] Komponen tidak dikenal (di-skip): '{komponen}'")
                    continue

                prev = current_sop["komponen_text"].get(jenis, "")
                if prev:
                    current_sop["komponen_text"][jenis] = prev + " " + uraian
                else:
                    current_sop["komponen_text"][jenis] = uraian


        # setelah semua halaman selesai, flush SOP terakhir
        flush_current_sop()

    # update status dokumen_kb
    cur.execute("""
        UPDATE dokumen_kb
        SET status_indexing = 'sukses'
        WHERE id = %s
    """, (DOKUMEN_ID,))
    conn.commit()

    cur.close()
    conn.close()
    print("Selesai indexing semua SOP dari halaman 9-120.")


if __name__ == "__main__":
    main()
