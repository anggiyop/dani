import pandas as pd
import os

# ==========================
# KONFIGURASI
# ==========================

EXCEL_PATH = "faq.xlsx"          # nama file Excel sumber
SQL_OUTPUT = "insert_faq.sql"    # nama file SQL output

# Kalau tabel faq kamu TIDAK punya kolom segmen_pengguna,
# ubah USE_SEGMENT_COLUMN = False
USE_SEGMENT_COLUMN = True

# ==========================
# MAPPING jenis_faq -> (kategori_topik, segmen_pengguna)
# ==========================

FAQ_MAPPING = {
    "Kampus Merdeka": ("Kampus Merdeka & MBKM", "Mahasiswa"),
    "Buku Wisuda": ("Wisuda", "Mahasiswa"),
    "Sistem Informasi": ("Sistem Informasi & Akun", "Mahasiswa"),
    "Program Pendidikan": ("Program Pendidikan & Kurikulum", "Mahasiswa"),
    "Unit Kegiatan Mahasiswa": ("Unit Kegiatan Mahasiswa (UKM)", "Mahasiswa"),
    "Kampus Sehat": ("Kesehatan & Kampus Sehat", "Umum"),

    "Tenaga Kependidikan": ("Layanan Dosen/Tendik ULT", "Tenaga Kependidikan"),
    "Dosen": ("Layanan Dosen/Tendik ULT", "Dosen"),

    "Profil Dosen": ("Direktori & Profil Dosen", "Umum"),
    "Talenta Publisher": ("Talenta Publisher & Publikasi", "Umum"),

    "Mahasiswa": ("Layanan Akademik Mahasiswa ULT", "Mahasiswa"),
    "Umum": ("Fasilitas & Peminjaman Gedung", "Umum"),
}


def map_kategori_segmen(jenis: str):
    """
    Mengubah jenis_faq mentah dari Excel menjadi
    (kategori_topik, segmen_pengguna).
    Kalau tidak ada di mapping, pakai jenis_faq sebagai kategori,
    segmen default 'Umum'.
    """
    if pd.isna(jenis):
        return None, "Umum"

    jenis = str(jenis).strip()
    if jenis in FAQ_MAPPING:
        return FAQ_MAPPING[jenis]
    # default
    return jenis, "Umum"


def normalize_text(s: str) -> str:
    """
    - Ubah None/NaN -> ""
    - Hapus \r\n, jadikan spasi biasa
    - Rapikan spasi berlebih
    """
    if pd.isna(s):
        return ""
    text = str(s)
    text = text.replace("\r", " ").replace("\n", " ")
    # compress whitespace
    text = " ".join(text.split())
    return text


def sql_escape(s: str) -> str:
    """
    Escape karakter untuk dimasukkan ke SQL literal:
    - escape backslash
    - escape single quote
    """
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "''")
    return s


def main():
    if not os.path.exists(EXCEL_PATH):
        print(f"File Excel '{EXCEL_PATH}' tidak ditemukan.")
        return

    # 1. Baca Excel
    df = pd.read_excel(EXCEL_PATH)

    # Pastikan nama kolom sesuai
    # Kalau di Excel beda (misal 'jenis', 'question', 'answer'),
    # silakan di-rename di sini.
    df = df.rename(columns={
        "jenis_faq": "jenis_faq",
        "pertanyaan": "pertanyaan",
        "jawaban": "jawaban",
    })

    # 2. Tambah kolom kategori & segmen
    kategori_list = []
    segmen_list = []

    for jenis in df["jenis_faq"]:
        kategori, segmen = map_kategori_segmen(jenis)
        kategori_list.append(kategori)
        segmen_list.append(segmen)

    df["kategori"] = kategori_list
    df["segmen_pengguna"] = segmen_list

    # 3. Normalisasi teks pertanyaan & jawaban
    df["pertanyaan_norm"] = df["pertanyaan"].apply(normalize_text)
    df["jawaban_norm"] = df["jawaban"].apply(normalize_text)

    # 4. Generate SQL
    with open(SQL_OUTPUT, "w", encoding="utf-8") as f:
        f.write("-- SQL INSERT untuk tabel faq\n")
        f.write("-- Generated otomatis dari faq.xlsx\n\n")

        for _, row in df.iterrows():
            kategori = sql_escape(normalize_text(row["kategori"]))
            segmen = sql_escape(normalize_text(row["segmen_pengguna"]))
            pertanyaan = sql_escape(row["pertanyaan_norm"])
            jawaban = sql_escape(row["jawaban_norm"])

            if USE_SEGMENT_COLUMN:
                # Versi kalau tabel faq PUNYA kolom segmen_pengguna
                sql = (
                    "INSERT INTO faq (kategori, segmen_pengguna, pertanyaan, jawaban) "
                    f"VALUES ('{kategori}', '{segmen}', '{pertanyaan}', '{jawaban}');\n"
                )
            else:
                # Versi kalau tabel faq TIDAK punya kolom segmen_pengguna
                sql = (
                    "INSERT INTO faq (kategori, pertanyaan, jawaban) "
                    f"VALUES ('{kategori}', '{pertanyaan}', '{jawaban}');\n"
                )

            f.write(sql)

    print(f"Selesai. File SQL tersimpan sebagai: {SQL_OUTPUT}")


if __name__ == "__main__":
    main()