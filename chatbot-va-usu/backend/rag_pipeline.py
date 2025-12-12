"""
rag_pipeline.py

Modul ini menangani proses Retrieval-Augmented Generation (RAG) untuk SOP:
- Menghitung embedding pertanyaan user
- Melakukan pencarian ke Qdrant
- Mengembalikan daftar chunk (teks + metadata)
- Menyusun context string untuk dikirim ke LLM

Versi ini menggunakan Qdrant dalam mode embedded (local, tanpa Docker/server eksternal),
dengan penyimpanan data di folder lokal (QDRANT_PATH).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import logging
import os

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# Konfigurasi dasar (diambil dari .env bila ada)
# ---------------------------------------------------------------------------

# Path folder untuk database Qdrant embedded
# Contoh di .env: QDRANT_PATH=D:\ANGGI\dani\qdrant_data
DEFAULT_QDRANT_PATH = os.getenv("QDRANT_PATH", "D:/ANGGI/dani/qdrant_data")

# Nama collection untuk chunk SOP
DEFAULT_QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "kb_sop_chunks")

# Model embedding untuk RAG
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)

logger = logging.getLogger("rag_pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Data class untuk representasi chunk hasil retrieval
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    """Representasi satu chunk yang diambil dari Qdrant."""
    text: str
    score: float

    chunk_id: Optional[int] = None
    dokumen_id: Optional[int] = None
    sop_id: Optional[int] = None
    judul_sop: Optional[str] = None
    bagian: Optional[str] = None
    no_urut: Optional[int] = None
    halaman: Optional[int] = None
    unit_layanan: Optional[str] = None
    kategori_layanan: Optional[str] = None

    @staticmethod
    def from_qdrant_point(point: qmodels.ScoredPoint) -> "RetrievedChunk":
        """Membuat RetrievedChunk dari ScoredPoint Qdrant."""
        payload = point.payload or {}

        return RetrievedChunk(
            text=str(payload.get("isi_chunk", "")),
            score=float(getattr(point, "score", 0.0)),

            chunk_id=payload.get("chunk_id"),
            dokumen_id=payload.get("dokumen_id"),
            sop_id=payload.get("sop_id"),
            judul_sop=payload.get("judul_sop"),
            bagian=payload.get("bagian"),
            no_urut=payload.get("no_urut"),
            halaman=payload.get("halaman"),
            unit_layanan=payload.get("unit_layanan"),
            kategori_layanan=payload.get("kategori_layanan"),
        )


# ---------------------------------------------------------------------------
# Kelas utama RAGPipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    Pipeline RAG untuk dokumen SOP.

    Tugas:
    - Menghitung embedding query
    - Query Qdrant (embedded) untuk mencari chunk terdekat
    - Menghasilkan context string untuk LLM
    """

    def __init__(
        self,
        qdrant_path: str = DEFAULT_QDRANT_PATH,
        collection_name: str = DEFAULT_QDRANT_COLLECTION,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.collection_name = collection_name

        logger.info(
            "Inisialisasi RAGPipeline (Qdrant embedded: %s, collection: %s, embedding: %s)",
            qdrant_path,
            collection_name,
            embedding_model_name,
        )

        # Inisialisasi Qdrant client dalam mode embedded (tanpa host/port)
        # Data akan disimpan di folder qdrant_path
        os.makedirs(qdrant_path, exist_ok=True)
        self.client = QdrantClient(path=qdrant_path)

        # Inisialisasi model embedding
        self.embedding_model = SentenceTransformer(embedding_model_name)

    # ---------------------------------------------------------------------
    # Utilitas embedding
    # ---------------------------------------------------------------------

    def embed_text(self, text: str) -> List[float]:
        """
        Menghasilkan embedding untuk satu teks.
        """
        if not text:
            text = " "

        emb = self.embedding_model.encode(text)
        return emb.tolist()

    # ---------------------------------------------------------------------
    # Filter Qdrant (opsional)
    # ---------------------------------------------------------------------

    def _build_filter(self, filters: Optional[Dict[str, Any]]) -> Optional[qmodels.Filter]:
        """
        Membangun filter Qdrant dari dict sederhana.
        Contoh:
            filters = {"sop_id": 10, "unit_layanan": "Biro Akademik"}
        """
        if not filters:
            return None

        must_conditions: List[qmodels.FieldCondition] = []
        for key, value in filters.items():
            if value is None:
                continue
            must_conditions.append(
                qmodels.FieldCondition(
                    key=key,
                    match=qmodels.MatchValue(value=value),
                )
            )

        if not must_conditions:
            return None

        return qmodels.Filter(must=must_conditions)

    # ---------------------------------------------------------------------
    # Method yang dipanggil orchestrator: retrieve_sop_context
    # ---------------------------------------------------------------------

    def retrieve_sop_context(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Mengambil top-k chunk yang paling relevan dengan query dari Qdrant.

        Parameter:
        - query: pertanyaan user
        - top_k: jumlah chunk
        - filters: dict filter metadata (optional)

        Return:
        - List[RetrievedChunk]
        """
        if not query:
            logger.warning("retrieve_sop_context dipanggil dengan query kosong.")
            return []

        logger.info("Melakukan retrieval untuk query: %s", query)
        query_vector = self.embed_text(query)
        q_filter = self._build_filter(filters)

        # Adaptif terhadap versi qdrant-client:
        # - versi lama: QdrantClient.search(...)
        # - versi baru: QdrantClient.query_points(...)
        try:
            if hasattr(self.client, "search"):
                logger.debug("Menggunakan QdrantClient.search() (API lama)")
                hits = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    query_filter=q_filter,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False,
                )
            else:
                logger.debug("Menggunakan QdrantClient.query_points() (Query API baru)")
                resp = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=q_filter,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False,
                )
                hits = resp.points

        except Exception as e:
            logger.exception("Gagal melakukan search/query ke Qdrant: %s", e)
            return []

        retrieved_chunks: List[RetrievedChunk] = []
        for point in hits:
            chunk = RetrievedChunk.from_qdrant_point(point)
            retrieved_chunks.append(chunk)

        logger.info("Retrieval selesai. %d chunk ditemukan.", len(retrieved_chunks))
        return retrieved_chunks

    # ---------------------------------------------------------------------
    # Penyusunan context string
    # ---------------------------------------------------------------------

    def build_context_string(
        self,
        chunks: List[RetrievedChunk],
        max_chars: Optional[int] = None,
    ) -> str:
        """
        Menyusun context string dari daftar chunk.
        """
        if not chunks:
            return ""

        parts: List[str] = []
        current_length = 0

        for c in chunks:
            header = self._format_chunk_header(c)
            body = c.text.strip()
            block = f"{header}\n{body}\n"
            block_len = len(block)

            if max_chars is not None and current_length + block_len > max_chars:
                break

            parts.append(block)
            current_length += block_len

        context = "\n\n".join(parts)
        return context

    def _format_chunk_header(self, chunk: RetrievedChunk) -> str:
        """
        Header ringkas untuk setiap chunk.
        """
        judul = chunk.judul_sop or "SOP"
        bagian = chunk.bagian or "-"
        langkah = chunk.no_urut if chunk.no_urut is not None else "-"
        halaman = chunk.halaman if chunk.halaman is not None else "-"

        header = (
            f"[SOP: {judul} | Bagian: {bagian} | Langkah: {langkah} | Halaman: {halaman}]"
        )
        return header


# ---------------------------------------------------------------------------
# Testing manual (opsional)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pipeline = RAGPipeline()
    q = "Apa saja persyaratan untuk mengajukan cuti kuliah?"
    chunks = pipeline.retrieve_sop_context(q, top_k=3)
    print("Ditemukan:", len(chunks))
    ctx = pipeline.build_context_string(chunks, max_chars=2000)
    print("Context:\n", ctx)
