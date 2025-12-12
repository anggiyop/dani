import pandas as pd
import datetime
import math
import re
from pathlib import Path

# =====================
# KONFIG
# =====================

EXCEL_PATH = "kalender_akademik.xlsx"          # nama file excel
OUTPUT_SQL = "kalender_akademik_insert.sql"    # nama file sql output
TAHUN_AKADEMIK = "2025/2026"                   # bisa kamu ubah kalau perlu

# Mapping nama bulan Indonesia -> nomor bulan
MONTH_MAP = {
    'januari': 1,
    'februari': 2,
    'maret': 3,
    'april': 4,
    'mei': 5,
    'juni': 6,
    'juli': 7,
    'agustus': 8,
    'september': 9,
    'oktober': 10,
    'november': 11,
    'desember': 12,
}


# =====================
# FUNGSI PARSER JADWAL
# =====================

def parse_jadwal(text):
    """
    Mengubah teks jadwal seperti:
    - '18 Agustus 2025'
    - '01 - 16 Agustus 2025'
    - '20 Oktober 2025 - 05 Desember 2025'
    menjadi (tanggal_mulai, tanggal_selesai) berupa datetime.date.
    """
    if not isinstance(text, str):
        return None, None

    s = text.strip()

    # Pola 1: dua tanggal lengkap
    # contoh: "20 Oktober 2025 - 05 Desember 2025"
    m = re.match(
        r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*-\s*'
        r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$',
        s
    )
    if m:
        d1, mon1, y1, d2, mon2, y2 = m.groups()
        mon1 = MONTH_MAP.get(mon1.lower())
        mon2 = MONTH_MAP.get(mon2.lower())
        if mon1 and mon2:
            dt1 = datetime.date(int(y1), mon1, int(d1))
            dt2 = datetime.date(int(y2), mon2, int(d2))
            return dt1, dt2

    # Pola 2: range hari di bulan yang sama
    # contoh: "01 - 16 Agustus 2025"
    m = re.match(
        r'^(\d{1,2})\s*-\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$',
        s
    )
    if m:
        d1, d2, mon, y = m.groups()
        monn = MONTH_MAP.get(mon.lower())
        if monn:
            dt1 = datetime.date(int(y), monn, int(d1))
            dt2 = datetime.date(int(y), monn, int(d2))
            return dt1, dt2

    # Pola 3: satu tanggal saja
    # contoh: "18 Agustus 2025"
    m = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', s)
    if m:
        d, mon, y = m.groups()
        monn = MONTH_MAP.get(mon.lower())
        if monn:
            dt = datetime.date(int(y), monn, int(d))
            return dt, dt

    # Kalau tidak cocok pola apapun
    return None, None


# =====================
# DETEKSI SEMESTER
# =====================

def detect_semester(row):
    """
    Heuristik semester:
    1) Kalau ada kata eksplisit:
       - 'semester antara' -> Antara
       - 'ganjil' -> Ganjil
       - 'genap' -> Genap
    2) Kalau tidak ada, pakai tanggal tengah (mid-date):
       - tahun 2025 -> Ganjil
       - tahun 2026:
           bulan 1-6 -> Genap
           bulan >=7 -> Antara
    """
    kat = str(row['kategori_agenda']).lower()
    nama = str(row['nama_agenda']).lower()
    ket = str(row['keterangan']).lower() if not pd.isna(row['keterangan']) else ""

    start = row['tanggal_mulai']
    end = row['tanggal_selesai']

    # 1. Berdasarkan kata kunci eksplisit
    if 'semester antara' in kat or 'semester antara' in nama or 'semester pendek' in kat or 'semester pendek' in nama:
        return 'Antara'
    if 'ganjil' in kat or 'ganjil' in nama or 'ganjil' in ket:
        return 'Ganjil'
    if 'genap' in kat or 'genap' in nama or 'genap' in ket:
        return 'Genap'

    # 2. Berdasarkan tanggal (khusus untuk T.A. 2025/2026)
    if isinstance(start, datetime.date) and isinstance(end, datetime.date):
        mid = start + (end - start) / 2
        # semua 2025 kita anggap terkait Semester Ganjil 2025/2026
        if mid.year == 2025:
            return 'Ganjil'
        if mid.year == 2026:
            if mid.month <= 6:
                return 'Genap'
            else:
                return 'Antara'

    # fallback kalau tidak ketemu
    return 'Umum'


# =====================
# UTIL SQL
# =====================

def sql_escape(s: str) -> str:
    """Escape sederhana untuk string SQL (tanda kutip & backslash)."""
    return s.replace("\\", "\\\\").replace("'", "''")


# =====================
# MAIN
# =====================

def main():
    excel_path = Path(EXCEL_PATH)
    if not excel_path.exists():
        raise FileNotFoundError(f"File Excel '{EXCEL_PATH}' tidak ditemukan.")

    # 1. Baca Excel
    df = pd.read_excel(excel_path)

    # 2. Parse jadwal -> tanggal_mulai & tanggal_selesai
    df['tanggal_mulai'], df['tanggal_selesai'] = zip(*df['jadwal'].map(parse_jadwal))

    # 3. Cek kalau ada jadwal yang gagal diparse
    gagal = df[df['tanggal_mulai'].isna()][['jadwal']]
    if not gagal.empty:
        print("PERINGATAN: Ada baris yang jadwal-nya tidak bisa diparse:")
        print(gagal)
        print("Silakan cek dan perbaiki manual.")
        # boleh lanjut, tapi tanggal akan NULL

    # 4. Tambah kolom tahun_akademik & semester
    df['tahun_akademik'] = TAHUN_AKADEMIK
    df['semester'] = df.apply(detect_semester, axis=1)

    # 5. Bangun SQL
    lines = []

    # CREATE TABLE
    lines.append(
        """CREATE TABLE IF NOT EXISTS kalender_akademik (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tahun_akademik VARCHAR(20) NOT NULL,
    semester ENUM('Ganjil','Genap','Antara','Umum') NOT NULL,
    kategori VARCHAR(100) NOT NULL,
    nama_agenda VARCHAR(200) NOT NULL,
    tanggal_mulai DATE NOT NULL,
    tanggal_selesai DATE NULL,
    keterangan TEXT NULL,
    link VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""
    )

    # INSERT
    values_sql = []
    for _, row in df.iterrows():
        ta = row['tahun_akademik']
        sem = row['semester']
        kat = row['kategori_agenda']
        nama = row['nama_agenda']
        t1 = row['tanggal_mulai']
        t2 = row['tanggal_selesai']
        ket = row['keterangan']
        link = row['link-href']

        def fmt_str(v):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return "NULL"
            return f"'{sql_escape(str(v))}'"

        v_ta = fmt_str(ta)
        v_sem = fmt_str(sem)
        v_kat = fmt_str(kat)
        v_nama = fmt_str(nama)
        v_t1 = f"'{t1.isoformat()}'" if isinstance(t1, datetime.date) else "NULL"
        v_t2 = f"'{t2.isoformat()}'" if isinstance(t2, datetime.date) else "NULL"
        v_ket = fmt_str(ket) if not pd.isna(ket) else "NULL"
        v_link = fmt_str(link) if not pd.isna(link) else "NULL"

        values_sql.append(
            f"({v_ta}, {v_sem}, {v_kat}, {v_nama}, {v_t1}, {v_t2}, {v_ket}, {v_link})"
        )

    insert_sql = (
        "INSERT INTO kalender_akademik "
        "(tahun_akademik, semester, kategori, nama_agenda, tanggal_mulai, "
        "tanggal_selesai, keterangan, link) VALUES\n"
        + ",\n".join(values_sql)
        + ";"
    )

    lines.append("")
    lines.append(insert_sql)

    # 6. Tulis ke file .sql
    out_path = Path(OUTPUT_SQL)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Selesai. SQL tersimpan di: {out_path.resolve()}")


if __name__ == "__main__":
    main()