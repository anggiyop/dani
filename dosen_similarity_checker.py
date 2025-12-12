import mysql.connector
from difflib import SequenceMatcher
import pandas as pd
from datetime import datetime

# ==============================
# KONFIGURASI KONEKSI DATABASE
# ==============================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "asisten_mhs",
}

# Threshold kemiripan (0.0 - 1.0)
SIMILARITY_THRESHOLD = 0.90

# Nama file output Excel
OUTPUT_EXCEL = "duplikasi_nama_dosen.xlsx"


def normalize_name(name: str) -> str:
    """
    Normalisasi nama supaya perbandingan lebih fair:
    - lowercase
    - hilangkan spasi berlebih
    - strip di awal/akhir
    """
    if not name:
        return ""
    n = name.lower()
    n = " ".join(n.split())
    return n


def get_dosen_list(conn):
    """
    Ambil data dosen dari tabel dosen.
    Return list of dict: {"id": ..., "nama": ..., "nama_norm": ...}
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, nama_dosen FROM dosen")
    rows = cursor.fetchall()
    cursor.close()

    dosen_list = []
    for row in rows:
        id_dosen = row[0]
        nama = row[1] or ""
        dosen_list.append(
            {
                "id": id_dosen,
                "nama": nama,
                "nama_norm": normalize_name(nama),
            }
        )
    return dosen_list


def similarity(a: str, b: str) -> float:
    """Hitung kemiripan string dengan SequenceMatcher (0.0 - 1.0)."""
    return SequenceMatcher(None, a, b).ratio()


def find_similar_names(dosen_list, threshold: float):
    """
    Cari pasangan nama dosen yang mirip di atas 'threshold'.
    Mengembalikan list dict:
    {
      "id_1": ...,
      "nama_1": ...,
      "id_2": ...,
      "nama_2": ...,
      "similarity": ... (0.0 - 1.0)
    }
    """
    results = []
    n = len(dosen_list)

    for i in range(n):
        for j in range(i + 1, n):
            d1 = dosen_list[i]
            d2 = dosen_list[j]

            if not d1["nama_norm"] or not d2["nama_norm"]:
                continue

            sim = similarity(d1["nama_norm"], d2["nama_norm"])

            if sim >= threshold:
                results.append(
                    {
                        "id_1": d1["id"],
                        "nama_1": d1["nama"],
                        "id_2": d2["id"],
                        "nama_2": d2["nama"],
                        "similarity": sim,
                    }
                )

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results


def save_to_excel(pairs, threshold: float, output_path: str):
    """
    Simpan hasil pasangan nama mirip ke file Excel.
    """
    if not pairs:
        print("Tidak ada pasangan nama mirip di atas threshold, tetap membuat file Excel kosong...")
        df = pd.DataFrame(
            columns=[
                "id_1",
                "nama_1",
                "id_2",
                "nama_2",
                "similarity_percent",
            ]
        )
    else:
        df = pd.DataFrame(
            [
                {
                    "id_1": p["id_1"],
                    "nama_1": p["nama_1"],
                    "id_2": p["id_2"],
                    "nama_2": p["nama_2"],
                    "similarity_percent": round(p["similarity"] * 100, 2),
                }
                for p in pairs
            ]
        )

    # Optional: tambahkan info threshold & timestamp di sheet kedua
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="duplikasi_nama", index=False)

        info_df = pd.DataFrame(
            [
                {
                    "threshold_similarity": threshold,
                    "threshold_percent": threshold * 100,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_pairs": len(pairs),
                }
            ]
        )
        info_df.to_excel(writer, sheet_name="info", index=False)

    print(f"File Excel berhasil dibuat: {output_path}")


def main():
    print("Menghubungkan ke database...")
    conn = mysql.connector.connect(**DB_CONFIG)

    try:
        print("Mengambil data dosen...")
        dosen_list = get_dosen_list(conn)
        print(f"Total dosen: {len(dosen_list)}")

        print(f"\nMencari nama dosen yang mirip (threshold >= {SIMILARITY_THRESHOLD * 100:.0f}%)...")
        similar_pairs = find_similar_names(dosen_list, SIMILARITY_THRESHOLD)

        print(f"Ditemukan {len(similar_pairs)} pasangan nama yang mirip.\n")

        # Tampilkan ringkas di console (opsional)
        for item in similar_pairs[:20]:  # batasi 20 baris pertama
            print(
                f"[{item['similarity']*100:5.1f}%] "
                f"(id={item['id_1']}) '{item['nama_1']}'  <-->  "
                f"(id={item['id_2']}) '{item['nama_2']}'"
            )

        # Simpan hasil ke Excel
        save_to_excel(similar_pairs, SIMILARITY_THRESHOLD, OUTPUT_EXCEL)

    finally:
        conn.close()
        print("\nKoneksi database ditutup.")


if __name__ == "__main__":
    main()
