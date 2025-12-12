#!/usr/bin/env python
"""
Indexing Kalender Akademik USU 2025/2026 ke tabel dokumen_chunk
dengan pendekatan page-based chunking.

Strategi:
1. Ambil dokumen_kb dengan tipe = 'kalender_akademik' dan status_indexing = 'belum'
2. Baca PDF per halaman dengan pdfplumber
3. Bersihkan teks per halaman
4. Deteksi bagian (Semester Ganjil / Genap / Antara / Umum) berdasarkan heading
5. Potong teks halaman menjadi beberapa chunk (max ~800 karakter)
6. Simpan chunk ke dokumen_chunk
7. Update dokumen_kb.status_indexing menjadi 'siap_embedding'
"""

import os
import re
from typing import List

import mysql.connector
import pdfplumber

# ======================
# KONFIGURASI (EDIT)
# ======================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",          # ganti dengan password MySQL kamu
    "database": "asisten_mhs",
}

# Root project-mu, supaya digabung dengan kolom `url` di dokumen_kb
BASE_PROJECT_DIR = r"D:\ANGGI\joki\DANI\chatbot-va-usu"  # <-- GANTI sesuai path kamu

STATUS_BELUM = "belum"
STATUS_SIAP_EMBEDDING = "siap_embedding"
STATUS_GAGAL = "gagal"

# Batas maksimal panjang chunk (karakter)
MAX_CHARS_PER_CHUNK = 700


# ======================
# FUNGSI UTIL
# ======================

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def normalize_whitespace(text: str) -> str:
    """Rapikan spasi & baris: gabungkan multi-spasi jadi satu, hilangkan baris kosong berlebihan."""
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_bagian(page_text_upper: str) -> str:
    """Deteksi 'bagian' berdasarkan heading di halaman."""
    if "SEMESTER GANJIL" in page_text_upper:
        return "Semester Ganjil"
    if "SEMESTER GENAP" in page_text_upper:
        return "Semester Genap"
    if "SEMESTER ANTARA" in page_text_upper or "SEMESTER PENDEK" in page_text_upper:
        return "Semester Antara"
    if "LIBUR NASIONAL" in page_text_upper or "CUTI BERSAMA" in page_text_upper:
        return "Libur / Umum"
    if "KALENDER AKADEMIK" in page_text_upper:
        return "Judul / Cover"
    return "Umum"


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> List[str]:
    """
    Bagi teks panjang menjadi beberapa chunk dengan batas karakter max_chars.
    Diusahakan memotong di batas antar-kata.
    """
    words = text.split()
    chunks: List[str] = []
    current_words: List[str] = []
    length = 0

    for w in words:
        w_len = len(w)
        # +1 untuk spasi
        if length + w_len + (1 if current_words else 0) > max_chars:
            if current_words:
                chunks.append(" ".join(current_words))
            current_words = [w]
            length = w_len
        else:
            current_words.append(w)
            length += w_len + (1 if current_words else 0)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


# ======================
# DB HELPER
# ======================

def get_pending_kalender_docs(cursor):
    cursor.execute(
        """
        SELECT * FROM dokumen_kb
        WHERE tipe = 'kalender_akademik'
          AND status_indexing = %s
        """,
        (STATUS_BELUM,)
    )
    return cursor.fetchall()


def update_status_indexing(cursor, dokumen_id: int, status: str):
    cursor.execute(
        "UPDATE dokumen_kb SET status_indexing = %s WHERE id = %s",
        (status, dokumen_id),
    )


def insert_chunk(cursor, dokumen_id: int, sop_id, no_urut: int,
                 isi_chunk: str, halaman: int, bagian: str):
    cursor.execute(
        """
        INSERT INTO dokumen_chunk
            (dokumen_id, sop_id, no_urut, isi_chunk, halaman, bagian,
             embedding_id, created_at, updated_at)
        VALUES
            (%s, %s, %s, %s, %s, %s,
             NULL, NOW(), NOW())
        """,
        (dokumen_id, sop_id, no_urut, isi_chunk, halaman, bagian),
    )


# ======================
# PROSES UTAMA PER DOKUMEN
# ======================

def process_document(conn, doc: dict):
    cursor = conn.cursor(dictionary=True)

    dokumen_id = doc["id"]
    sop_id = doc.get("sop_id")  # biasanya None untuk kalender
    url = doc["url"]

    pdf_path = os.path.join(BASE_PROJECT_DIR, url.replace("/", os.sep))
    print(f"\nMemproses dokumen ID={dokumen_id}, file={pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"  [ERROR] File tidak ditemukan: {pdf_path}")
        update_status_indexing(cursor, dokumen_id, STATUS_GAGAL)
        conn.commit()
        cursor.close()
        return

    try:
        no_urut_global = 1

        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # HANYA PROSES HALAMAN 3 s.d. 7
                if page_num < 3 or page_num > 7:
                    continue

                raw_text = page.extract_text() or ""
                if not raw_text.strip():
                    continue

                cleaned = normalize_whitespace(raw_text)
                if not cleaned:
                    continue

                bagian = detect_bagian(cleaned.upper())
                chunks = chunk_text(cleaned, MAX_CHARS_PER_CHUNK)

                for c in chunks:
                    insert_chunk(
                        cursor,
                        dokumen_id=dokumen_id,
                        sop_id=sop_id,
                        no_urut=no_urut_global,
                        isi_chunk=c,
                        halaman=page_num,
                        bagian=bagian,
                    )
                    no_urut_global += 1

        update_status_indexing(cursor, dokumen_id, STATUS_SIAP_EMBEDDING)
        conn.commit()
        print(f"  [OK] Dokumen {dokumen_id} selesai di-chunk.")
    except Exception as e:
        print(f"  [ERROR] Gagal memproses dokumen {dokumen_id}: {e}")
        update_status_indexing(cursor, dokumen_id, STATUS_GAGAL)
        conn.commit()
    finally:
        cursor.close()


def main():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    docs = get_pending_kalender_docs(cur)
    cur.close()

    if not docs:
        print("Tidak ada dokumen kalender_akademik dengan status_indexing = 'belum'.")
        conn.close()
        return

    print(f"Menemukan {len(docs)} dokumen untuk diproses.")
    for doc in docs:
        process_document(conn, doc)

    conn.close()
    print("\nSelesai.")


if __name__ == "__main__":
    main()
