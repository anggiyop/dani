# intent_classifier.py
from typing import Literal, Dict, List, Tuple

IntentType = Literal["SOP", "DOSEN", "KALENDER", "UMUM"]

INTENT_KEYWORDS: Dict[IntentType, List[str]] = {
    "SOP": [
        "sop", "prosedur", "prosedurnya", "cara", "alur", "langkah",
        "syarat", "persyaratan", "jangka waktu", "lama proses",
        "waktu penyelesaian", "biaya", "tarif", "produk layanan",
        "pengaduan", "komplain", "proses pelayanan", "pelayanan"
    ],
    "DOSEN": [
        "dosen", "nidn", "nip", "mengajar", "mengampu", "mata kuliah",
        "kaprodi", "ketua prodi", "program studi", "prodi", "fakultas"
    ],
    "KALENDER": [
        "kalender akademik", "kalender", "jadwal", "tanggal", "batas",
        "deadline", "krs", "kartu rencana studi", "uts", "uas",
        "registrasi", "pendaftaran ulang", "wisuda"
    ],
    "UMUM": [],
}

def _count_matches(q: str, keywords: List[str]) -> int:
    return sum(1 for kw in keywords if kw in q)

def classify_intent_with_score(query: str) -> Tuple[IntentType, Dict[IntentType, int]]:
    q = (query or "").lower()
    scores: Dict[IntentType, int] = {
        "SOP": _count_matches(q, INTENT_KEYWORDS["SOP"]),
        "DOSEN": _count_matches(q, INTENT_KEYWORDS["DOSEN"]),
        "KALENDER": _count_matches(q, INTENT_KEYWORDS["KALENDER"]),
        "UMUM": 0,
    }

    best_intent: IntentType = max(scores, key=scores.get)  # type: ignore

    if scores[best_intent] == 0:
        best_intent = "UMUM"

    return best_intent, scores

def classify_intent(query: str) -> IntentType:
    intent, scores = classify_intent_with_score(query)

    # Contoh aturan prioritas tambahan:
    # kalau SOP dan DOSEN sama-sama >0, dahulukan SOP
    if scores["SOP"] > 0 and scores["DOSEN"] > 0 and intent == "DOSEN":
        intent = "SOP"

    return intent