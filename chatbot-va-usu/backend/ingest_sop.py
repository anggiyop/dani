"""
ingest_sop.py

Script untuk:
- Membaca chunk SOP dari MySQL (tabel dokumen_chunk + join sop + unit_layanan)
- Menghitung embedding isi_chunk
- Menyimpan vector + payload ke Qdrant (embedded mode, path=QDRANT_PATH)

Jalankan ini sebelum chatbot digunakan, atau setiap kali ada update SOP baru.
"""

import os
import mysql.connector

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models as qmodels
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# Load konfigurasi dari .env
# ---------------------------------------------------------------------------

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "asisten_mhs")

QDRANT_PATH = os.getenv("QDRANT_PATH", "D:/ANGGI/dani/qdrant_data")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "kb_sop_chunks")
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)


# ---------------------------------------------------------------------------
# Koneksi MySQL
# ---------------------------------------------------------------------------

def get_mysql_conn():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


# ---------------------------------------------------------------------------
# Inisialisasi Qdrant embedded
# ---------------------------------------------------------------------------

def init_qdrant(embedding_dim: int) -> QdrantClient:
    """
    Inisialisasi Qdrant dalam mode embedded (local, tanpa host/port).
    Membuat ulang collection kb_sop_chunks dengan dimensi vector sesuai embedding_dim.
    """
    os.makedirs(QDRANT_PATH, exist_ok=True)

    client = QdrantClient(path=QDRANT_PATH)

    # Untuk awal: recreate_collection supaya selalu bersih.
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(
            size=embedding_dim,
            distance=qmodels.Distance.COSINE,
        ),
    )

    print(f"[Qdrant] Collection '{COLLECTION_NAME}' siap (dim={embedding_dim}).")
    return client


# ---------------------------------------------------------------------------
# Load chunk SOP dari MySQL
# ---------------------------------------------------------------------------

def load_chunks_to_index(conn):
    """
    Ambil data chunk dari tabel dokumen_chunk (join ke sop dan unit_layanan).

    Disesuaikan dengan struktur:
    - dokumen_chunk.id, dokumen_id, sop_id, isi_chunk, bagian, no_urut, halaman
    - sop.judul_sop, sop.kategori_layanan
    - unit_layanan.nama_unit
    """
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
            s.judul_sop,
            s.kategori_layanan,
            u.nama_unit AS unit_layanan
        FROM dokumen_chunk dc
        LEFT JOIN sop s ON dc.sop_id = s.id
        LEFT JOIN unit_layanan u ON s.unit_layanan_id = u.id
        WHERE dc.isi_chunk IS NOT NULL
    """
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    return rows


# ---------------------------------------------------------------------------
# Main ingest
# ---------------------------------------------------------------------------

def main():
    print("[Ingest] Mulai proses indexing SOP ke Qdrant embedded...")

    # 1. Koneksi MySQL
    conn = get_mysql_conn()
    print(f"[MySQL] Terhubung ke database: {DB_NAME}")

    # 2. Inisialisasi model embedding
    print(f"[Embedding] Memuat model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"[Embedding] Dimensi embedding: {embedding_dim}")

    # 3. Inisialisasi Qdrant embedded + collection
    qdrant = init_qdrant(embedding_dim=embedding_dim)

    # 4. Load chunk dari MySQL
    chunks = load_chunks_to_index(conn)
    print(f"[Ingest] Jumlah chunk yang akan di-index: {len(chunks)}")

    if not chunks:
        print("[Ingest] Tidak ada chunk untuk di-index. Selesai.")
        conn.close()
        return

    # 5. Siapkan batch points untuk Qdrant
    ids = []
    vectors = []
    payloads = []

    for row in chunks:
        text = row["isi_chunk"] or ""
        emb = model.encode(text).tolist()

        ids.append(row["chunk_id"])
        vectors.append(emb)
        payloads.append(
            {
                "chunk_id": row["chunk_id"],
                "dokumen_id": row["dokumen_id"],
                "sop_id": row["sop_id"],
                "judul_sop": row["judul_sop"],
                "bagian": row["bagian"],
                "no_urut": row["no_urut"],
                "halaman": row["halaman"],
                "unit_layanan": row["unit_layanan"],
                "kategori_layanan": row["kategori_layanan"],
                "isi_chunk": text,
            }
        )

    # 6. Upsert ke Qdrant
    print("[Ingest] Mengirim batch points ke Qdrant...")
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=qmodels.Batch(
            ids=ids,
            vectors=vectors,
            payloads=payloads,
        ),
    )
    print(f"[Ingest] Selesai upsert {len(ids)} chunk ke collection '{COLLECTION_NAME}'.")

    conn.close()
    print("[Ingest] Proses selesai.")


if __name__ == "__main__":
    main()
