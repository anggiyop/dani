"""
app.py

Backend API untuk chatbot:
- Endpoint /chat
- Memakai orchestrator (intent + RAG)
- Memanggil LLM lewat llm_client.generate_answer
"""

from __future__ import annotations

from typing import List, Any, Dict

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, root_validator

from dotenv import load_dotenv

from orchestrator import handle_user_query
from llm_client import generate_answer  # dipanggil untuk LLM


# ---------------------------------------------------------------------------
# Load konfigurasi dari .env (jika ada)
# ---------------------------------------------------------------------------

# .env ditempatkan di root project: D:\ANGGI\dani\chatbot-va-usu\.env
load_dotenv()


# ---------------------------------------------------------------------------
# Inisialisasi FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title=os.getenv("APP_TITLE", "Asisten Mahasiswa - Chatbot SOP"),
    version=os.getenv("APP_VERSION", "0.1.0"),
)

# CORS (boleh dibatasi nanti)
allowed_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Model request/response
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    # Field utama yang dipakai internal
    message: str

    # Terima alias seperti "query", "prompt", "text", "inputs"
    @root_validator(pre=True)
    def populate_message(cls, values):
        if "message" not in values:
            for key in ("query", "prompt", "text", "inputs"):
                if key in values and isinstance(values[key], str):
                    values["message"] = values[key]
                    break
        return values


class ChatSource(BaseModel):
    chunk_id: int | None = None
    dokumen_id: int | None = None
    sop_id: int | None = None
    judul_sop: str | None = None
    bagian: str | None = None
    no_urut: int | None = None
    halaman: int | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sources: List[ChatSource]


# ---------------------------------------------------------------------------
# Endpoint utama /chat
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    """
    Endpoint utama chatbot.
    - Terima pertanyaan user
    - Orchestrator menentukan intent + context
    - LLM menghasilkan jawaban berdasarkan context
    """
    user_message = req.message.strip()

    # 1. Orchestrator: intent + context + sources
    result: Dict[str, Any] = handle_user_query(user_message)
    intent: str = result["intent"]
    context: str = result["context"]
    sources_raw: List[Dict[str, Any]] = result["sources"]

    # 2. System prompt untuk LLM (bisa juga diambil dari .env kalau mau)
    system_prompt = (
        "Anda adalah asisten virtual untuk mahasiswa di lingkungan kampus. "
        "Jawab pertanyaan hanya berdasarkan konteks yang diberikan.\n\n"
        "Jika konteks berisi langkah-langkah SOP yang ditandai dengan huruf "
        "atau nomor (misalnya a., b., c. atau 1., 2., 3.), "
        "MAKA Anda WAJIB menuliskan SEMUA langkah tersebut secara berurutan "
        "tanpa menghilangkan satu pun, dan tanpa mengubah maknanya.\n"
        "Jika informasi tidak tersedia di konteks, katakan dengan jelas bahwa "
        "data tersebut tidak tersedia atau tidak diatur dalam SOP."
    )

    # 3. Panggil LLM untuk menghasilkan jawaban
    answer = generate_answer(
        system_prompt=system_prompt,
        context=context,
        user_query=user_message,
    )

    # 4. Konversi sources_raw ke ChatSource
    sources: List[ChatSource] = [ChatSource(**src) for src in sources_raw]

    return ChatResponse(
        answer=answer,
        intent=intent,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# Endpoint sederhana untuk health check
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "ok", "message": "Chatbot SOP backend is running."}


# ---------------------------------------------------------------------------
# Untuk menjalankan langsung dengan: python app.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)

