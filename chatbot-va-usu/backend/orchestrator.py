"""
orchestrator.py

Orchestrator untuk chatbot Asisten Mahasiswa (SOP):

- Menentukan intent (untuk saat ini: default 'SOP')
- Menggunakan RAGPipeline untuk mencari SOP yang relevan
- Khusus pertanyaan tentang langkah/proses/mekanisme/prosedur SOP,
  mengambil seluruh langkah dari database (dokumen_chunk) agar
  jawaban selalu lengkap dan berurutan.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging
import os

import mysql.connector
from dotenv import load_dotenv

from rag_pipeline import RAGPipeline, RetrievedChunk


# ---------------------------------------------------------------------------
# Konfigurasi & logging
# ---------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger("orchestrator")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Konfigurasi DB dari .env
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "asisten_mhs")

# Inisialisasi global RAG
rag_pipeline = RAGPipeline()


# ---------------------------------------------------------------------------
# Utilitas DB
# ---------------------------------------------------------------------------

def get_mysql_conn():
    """
    Membuat koneksi MySQL berdasarkan konfigurasi .env
    """
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


# ---------------------------------------------------------------------------
# Deteksi pertanyaan tentang langkah / proses SOP
# ---------------------------------------------------------------------------

STEP_KEYWORDS = [
    "langkah",
    "proses",
    "mekanisme",
    "prosedur",
    "tahapan",
    "alur",
    "cara",
    "mengurus",
    "mengajukan",
    "mengganti",
    "menguruskan",
    "bagaimana",
    "apa yang harus dilakukan",
    "apa saja yang harus dilakukan",
    "bagaimana cara",
    "tata cara",
]


def is_step_question(user_query: str) -> bool:
    """
    Mengembalikan True jika pertanyaan user berhubungan dengan
    langkah/proses/mekanisme/prosedur SOP.
    """
    q_lower = user_query.lower()
    return any(kw in q_lower for kw in STEP_KEYWORDS)


# ---------------------------------------------------------------------------
# Ambil seluruh langkah SOP dari DB (dokumen_chunk)
# ---------------------------------------------------------------------------

def fetch_step_chunks_for_sop(sop_id: int) -> List[Dict[str, Any]]:
    """
    Mengambil seluruh langkah untuk satu SOP dari tabel dokumen_chunk.

    Asumsi struktur (sesuai skema kamu):
    - dokumen_chunk.id
    - dokumen_chunk.dokumen_id
    - dokumen_chunk.sop_id
    - dokumen_chunk.isi_chunk
    - dokumen_chunk.bagian
    - dokumen_chunk.no_urut
    - dokumen_chunk.halaman
    - sop.judul_sop

    Filter bagian:
    - LOWER(bagian) IN ('langkah', 'sistem, mekanisme, dan prosedur')
      (silakan sesuaikan kalau ada variasi lain)
    """
    conn = get_mysql_conn()
    cur = conn.cursor(dictionary=True)

    sql = """
        SELECT
            dc.id AS chunk_id,
            dc.dokumen_id,
            dc.sop_id,
            dc.isi_chunk,
            dc.bagian,
            dc.no_urut,
            dc.halaman,
            s.judul_sop
        FROM dokumen_chunk dc
        LEFT JOIN sop s ON dc.sop_id = s.id
        WHERE dc.sop_id = %s
          AND LOWER(dc.bagian) IN ('langkah', 'sistem, mekanisme, dan prosedur')
        ORDER BY dc.no_urut ASC, dc.halaman ASC, dc.id ASC
    """
    cur.execute(sql, (sop_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def build_full_step_context_from_db(
    sop_id: int,
    fallback_judul_sop: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Mengambil seluruh langkah SOP dari DB dan menyusunnya menjadi context string
    yang siap dikirim ke LLM, plus daftar sources.

    Return dict:
    {
        "context": str,
        "sources": List[Dict[str, Any]],
    }

    Jika tidak ditemukan langkah, context dikembalikan sebagai string kosong.
    """
    rows = fetch_step_chunks_for_sop(sop_id)

    if not rows:
        logger.warning(
            "Tidak ditemukan langkah di dokumen_chunk untuk sop_id=%s", sop_id
        )
    else:
        logger.info(
            "Ditemukan %d langkah (dokumen_chunk) untuk sop_id=%s",
            len(rows),
            sop_id,
        )

    if not rows:
        return {"context": "", "sources": []}

    # Ambil judul SOP dari baris pertama bila tersedia
    judul_sop = rows[0].get("judul_sop") or fallback_judul_sop or "SOP"

    # Susun langkah secara berurutan
    lines: List[str] = []
    lines.append(
        f"SOP: {judul_sop}\n"
        f"Bagian: Sistem, Mekanisme, dan Prosedur (Langkah-langkah pelayanan)\n"
    )

    for idx, row in enumerate(rows, start=1):
        isi = (row.get("isi_chunk") or "").strip()
        if not isi:
            continue
        lines.append(f"Langkah {idx}: {isi}")

    context = "\n".join(lines)

    # Susun sources dari rows
    sources: List[Dict[str, Any]] = []
    for row in rows:
        sources.append(
            {
                "chunk_id": row.get("chunk_id"),
                "dokumen_id": row.get("dokumen_id"),
                "sop_id": row.get("sop_id"),
                "judul_sop": row.get("judul_sop") or judul_sop,
                "bagian": row.get("bagian"),
                "no_urut": row.get("no_urut"),
                "halaman": row.get("halaman"),
            }
        )

    return {
        "context": context,
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# Build konteks SOP (RAG + special handling langkah)
# ---------------------------------------------------------------------------

def build_sop_context(user_query: str) -> Dict[str, Any]:
    """
    Membangun context dan sources untuk pertanyaan bertipe SOP.

    Langkah:
    1. Gunakan RAGPipeline untuk mencari chunk paling relevan.
    2. Jika pertanyaan mengandung kata kunci "langkah/proses/mekanisme/prosedur"
       dan RAG menemukan sop_id:
       - Ambil seluruh langkah SOP tersebut dari DB (dokumen_chunk),
         dan gunakan itu sebagai context utama.
    3. Jika tidak, gunakan context default dari RAGPipeline (top_k chunk).
    """
    # 1. Ambil chunk paling relevan lewat RAG
    chunks: List[RetrievedChunk] = rag_pipeline.retrieve_sop_context(
        user_query,
        top_k=5,
    )

    if not chunks:
        logger.warning("RAG tidak menemukan chunk relevan untuk query: %s", user_query)
        return {
            "context": "",
            "sources": [],
        }

    # Konversi chunks → sources dasar
    default_sources: List[Dict[str, Any]] = []
    for c in chunks:
        default_sources.append(
            {
                "chunk_id": c.chunk_id,
                "dokumen_id": c.dokumen_id,
                "sop_id": c.sop_id,
                "judul_sop": c.judul_sop,
                "bagian": c.bagian,
                "no_urut": c.no_urut,
                "halaman": c.halaman,
            }
        )

    # Context default (RAG, digabung jadi satu string)
    default_context: str = rag_pipeline.build_context_string(
        chunks,
        max_chars=4000,
    )

    # 2. Jika pertanyaan tentang langkah/proses, coba ambil full langkah dari DB
    first_chunk = chunks[0]
    sop_id = first_chunk.sop_id
    judul_sop = first_chunk.judul_sop

    if sop_id is not None and is_step_question(user_query):
        logger.info(
            "Query terdeteksi sebagai pertanyaan langkah/proses SOP. "
            "Mengambil seluruh langkah dari DB untuk sop_id=%s",
            sop_id,
        )
        full_step_data = build_full_step_context_from_db(
            sop_id=sop_id,
            fallback_judul_sop=judul_sop,
        )

        if full_step_data["context"]:
            # Berhasil dapat context lengkap dari DB
            return {
                "context": full_step_data["context"],
                "sources": full_step_data["sources"],
            }
        else:
            logger.warning(
                "Gagal membangun context langkah lengkap dari DB, "
                "fallback ke context RAG default."
            )

    # 3. Fallback: pakai context RAG biasa
    return {
        "context": default_context,
        "sources": default_sources,
    }


# ---------------------------------------------------------------------------
# Intent classification (sementara: selalu 'SOP')
# ---------------------------------------------------------------------------

def classify_intent(user_query: str) -> str:
    """
    Untuk saat ini, semua pertanyaan dianggap intent 'SOP'.
    Nanti kalau sudah ada intent_classifier yang cocok, fungsi ini bisa diubah.
    """
    return "SOP"


# ---------------------------------------------------------------------------
# Entry point yang dipanggil dari app.py
# ---------------------------------------------------------------------------

def handle_user_query(user_query: str) -> Dict[str, Any]:
    """
    Fungsi utama yang dipanggil FastAPI (app.py).

    Return dict:
    {
        "intent": str,
        "context": str,
        "sources": List[Dict[str, Any]],
    }
    """
    user_query = (user_query or "").strip()
    if not user_query:
        return {
            "intent": "UNKNOWN",
            "context": "",
            "sources": [],
        }

    intent = classify_intent(user_query)

    # Untuk sekarang, semua intent diperlakukan sebagai SOP
    sop_data = build_sop_context(user_query)
    return {
        "intent": intent,
        "context": sop_data["context"],
        "sources": sop_data["sources"],
    }


if __name__ == "__main__":
    # Testing manual sederhana
    q = "apa saja proses dan langkah-langkah yang harus dilakukan dalam menunda kegiatan akademik?"
    result = handle_user_query(q)
    print("Intent:", result["intent"])
    print("Context:\n", result["context"])
    print("Sources:", result["sources"])
