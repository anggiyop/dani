import pandas as pd
import mysql.connector
from pathlib import Path

# ==========================
# KONFIGURASI
# ==========================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",           # ganti kalau pakai password
    "database": "asisten_mhs"
}

EXCEL_PATH = "informasi_dosen_dengan_fakultas.xlsx"  # sesuaikan nama file (dedup / fixed)


def norm(s: str | None) -> str | None:
    """Normalisasi nama (lowercase + buang spasi double)."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip().lower()
    s = " ".join(s.split())
    return s or None


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_dosen_prodi_table(cur):
    """Buat tabel dosen_prodi kalau belum ada."""
    sql = """
    CREATE TABLE IF NOT EXISTS dosen_prodi (
        id INT NOT NULL AUTO_INCREMENT,
        dosen_id INT NOT NULL,
        prodi_id INT NOT NULL,
        is_homebase TINYINT(1) NOT NULL DEFAULT 0,
        jabatan VARCHAR(100) NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uniq_dosen_prodi (dosen_id, prodi_id),
        CONSTRAINT fk_dp_dosen
          FOREIGN KEY (dosen_id) REFERENCES dosen(id)
          ON UPDATE CASCADE ON DELETE CASCADE,
        CONSTRAINT fk_dp_prodi
          FOREIGN KEY (prodi_id) REFERENCES prodi(id)
          ON UPDATE CASCADE ON DELETE RESTRICT
    ) ENGINE=InnoDB
      DEFAULT CHARSET=utf8mb4
      COLLATE=utf8mb4_unicode_ci;
    """
    cur.execute(sql)


def detect_program_studi_columns(df: pd.DataFrame) -> list[str]:
    """
    Deteksi semua kolom yang namanya diawali 'program_studi-'
    dan urutkan berdasarkan angka di belakangnya.
    """
    import re

    cols = [c for c in df.columns if str(c).startswith("program_studi-")]

    def col_key(c):
        m = re.search(r"program_studi-(\d+)", str(c))
        return int(m.group(1)) if m else 0

    cols = sorted(cols, key=col_key)
    return cols


def main():
    # 1. pastikan file Excel ada
    path = Path(EXCEL_PATH)
    if not path.exists():
        print(f"[ERROR] File {EXCEL_PATH} tidak ditemukan.")
        return

    # 2. baca Excel
    df = pd.read_excel(path)

    # cek kolom dasar yang kita pakai
    base_required_cols = ["nama_dosen", "NIP", "NIDN"]
    for c in base_required_cols:
        if c not in df.columns:
            print(f"[PERINGATAN] Kolom '{c}' tidak ditemukan di Excel.")

    # deteksi kolom program_studi-*
    program_cols = detect_program_studi_columns(df)
    if not program_cols:
        print("[ERROR] Tidak ada kolom yang diawali 'program_studi-' di Excel.")
        return

    print("Kolom program_studi terdeteksi:", program_cols)

    # 3. koneksi DB
    conn = get_connection()
    cur = conn.cursor(dictionary=True, buffered=True)

    # 4. pastikan tabel dosen_prodi ada
    ensure_dosen_prodi_table(cur)
    conn.commit()

    # 5. load semua prodi -> mapping normalisasi(nama_prodi) -> id
    cur.execute("SELECT id, nama_prodi FROM prodi")
    prodi_rows = cur.fetchall()
    prodi_map = {}
    for r in prodi_rows:
        key = norm(r["nama_prodi"])
        if key:
            prodi_map[key] = r["id"]
    print(f"Loaded {len(prodi_map)} prodi dari tabel prodi.")

    # 6. proses per baris Excel
    total = len(df)
    inserted = 0
    not_found_prodi = 0
    not_found_dosen = 0
    log_nf_prodi = []
    log_nf_dosen = []

    for idx, row in df.iterrows():
        nama_dosen = str(row.get("nama_dosen", "")).strip()
        nip = row.get("NIP")
        nidn = row.get("NIDN")

        # cari dosen_id: prioritas NIDN -> NIP -> nama_dosen
        dosen_id = None

        if nidn and not pd.isna(nidn):
            cur.execute("SELECT id FROM dosen WHERE nidn = %s", (str(nidn),))
            r = cur.fetchone()
            if r:
                dosen_id = r["id"]

        if dosen_id is None and nip and not pd.isna(nip):
            cur.execute("SELECT id FROM dosen WHERE nip = %s", (str(nip),))
            r = cur.fetchone()
            if r:
                dosen_id = r["id"]

        if dosen_id is None and nama_dosen:
            cur.execute("SELECT id FROM dosen WHERE nama_dosen = %s", (nama_dosen,))
            r = cur.fetchone()
            if r:
                dosen_id = r["id"]

        if dosen_id is None:
            not_found_dosen += 1
            log_nf_dosen.append(
                f"Baris {idx+2}: DOSEN tidak ketemu -> nama='{nama_dosen}', NIP='{nip}', NIDN='{nidn}'"
            )
            continue

        # proses semua kolom program_studi-* yang terdeteksi
        for i, col in enumerate(program_cols, start=1):
            if col not in df.columns:
                continue

            nama_prodi_excel = row.get(col)
            if pd.isna(nama_prodi_excel):
                continue

            nama_prodi_excel = str(nama_prodi_excel).strip()
            if not nama_prodi_excel:
                continue

            key = norm(nama_prodi_excel)
            prodi_id = prodi_map.get(key)

            if not prodi_id:
                not_found_prodi += 1
                log_nf_prodi.append(
                    f"Baris {idx+2}: PRODI tidak ketemu -> '{nama_prodi_excel}' (dosen: {nama_dosen})"
                )
                continue

            is_homebase = 1 if i == 1 else 0

            # INSERT IGNORE: kalau kombinasi sudah ada tidak error
            cur.execute(
                """
                INSERT IGNORE INTO dosen_prodi (dosen_id, prodi_id, is_homebase)
                VALUES (%s, %s, %s)
                """,
                (dosen_id, prodi_id, is_homebase)
            )
            if cur.rowcount > 0:
                inserted += 1

        if (idx + 1) % 50 == 0:
            conn.commit()
            print(f"Progress {idx+1}/{total} baris...")

    conn.commit()
    cur.close()
    conn.close()

    # 7. ringkasan
    print("==== RINGKASAN ====")
    print(f"Total baris Excel         : {total}")
    print(f"Relasi dosen_prodi dibuat : {inserted}")
    print(f"Dosen tidak ketemu di DB  : {not_found_dosen}")
    print(f"Prodi tidak ketemu di DB  : {not_found_prodi}")

    if log_nf_dosen:
        print("\nContoh DOSEN tidak ketemu (max 20):")
        for line in log_nf_dosen[:20]:
            print(" -", line)

    if log_nf_prodi:
        print("\nContoh PRODI tidak ketemu (max 20):")
        for line in log_nf_prodi[:20]:
            print(" -", line)


if __name__ == "__main__":
    main()
