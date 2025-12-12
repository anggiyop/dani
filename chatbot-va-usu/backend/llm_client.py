"""
llm_client.py

Client HTTP untuk llama.cpp (llama-server) yang menjalankan model GGUF
Meta-Llama-3.1-8B-Instruct-Q5_K_M.

Fungsi utama yang dipanggil dari app.py:
    generate_answer(system_prompt, context, user_query) -> str
"""

from __future__ import annotations

import os
from typing import List

import requests

# ---------------------------------------------------------------------------
# Konfigurasi koneksi ke llama-server
# ---------------------------------------------------------------------------

# Endpoint OpenAI-compatible dari llama.cpp
# Default: server jalan di localhost port 8080
LLAMA_SERVER_URL = os.getenv(
    "LLAMA_SERVER_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)

# Nama model (label saja di sisi server; bebas, tidak harus sama dengan nama file)
LLAMA_MODEL_NAME = os.getenv(
    "LLAMA_MODEL_NAME",
    "Meta-Llama-3.1-8B-Instruct-Q5_K_M",
)


# ---------------------------------------------------------------------------
# Utilitas penyusun messages
# ---------------------------------------------------------------------------

def build_messages(system_prompt: str, context: str, user_query: str) -> List[dict]:
    """
    Susun daftar messages (format OpenAI-style) untuk dikirim ke llama.cpp.
    """
    if context is None:
        context = ""
    context = context.strip()

    # Konten yang diberikan ke role "user"
    user_content = (
        "Berikut konteks yang relevan (kutipan SOP / data kampus):\n\n"
        f"{context}\n\n"
        "Berdasarkan konteks di atas, jawab pertanyaan berikut secara jelas, "
        "singkat, dan sesuai dengan SOP/aturan yang berlaku. "
        "Jika informasi tidak ada di konteks, katakan bahwa data tersebut "
        "tidak tersedia dalam SOP atau belum diatur.\n\n"
        f"Pertanyaan: {user_query}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return messages


# ---------------------------------------------------------------------------
# Fungsi utama untuk menghasilkan jawaban dari LLM
# ---------------------------------------------------------------------------

def generate_answer(
    system_prompt: str,
    context: str,
    user_query: str,
    max_tokens: int = 512,
) -> str:
    """
    Panggil llama-server (llama.cpp) untuk mendapatkan jawaban.

    Parameter:
        system_prompt : instruksi global untuk asisten
        context       : teks konteks hasil RAG / query DB
        user_query    : pertanyaan asli dari user
        max_tokens    : batas maksimal token jawaban

    Return:
        String jawaban dari model.
    """
    messages = build_messages(system_prompt, context, user_query)

    payload = {
        "model": LLAMA_MODEL_NAME,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "top_p": 0.9,
    }

    response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=300)
    response.raise_for_status()

    data = response.json()
    # Struktur standar OpenAI-compatible: choices[0].message.content
    content = data["choices"][0]["message"]["content"]
    return (content or "").strip()
