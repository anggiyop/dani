import pandas as pd
import numpy as np
import re

# =======================
# KONFIGURASI FILE
# =======================
INPUT_FILE = "informasi_dosen_dengan_fakultas.xlsx"    # file asal
OUTPUT_FIXED_FILE = "informasi_dosen_dengan_fakultas_dedup.xlsx"  # file hasil perbaikan
OUTPUT_LOG_FILE = "informasi_dosen_dengan_fakultas_dedup_log.xlsx"  # file log perubahan

# Nama kolom nama dosen
NAMA_DOSEN_COL = "nama_dosen"


def normalize_name(name: str) -> str:
    """
    Normalisasi nama supaya perbandingan 100% lebih 'fair':
    - ke lowercase
    - hilangkan spasi berlebih di tengah
    - strip spasi di awal/akhir
    """
    if pd.isna(name):
        return ""
    if not isinstance(name, str):
        name = str(name)
    name = name.lower().strip()
    # ganti banyak spasi dengan satu spasi
    name = " ".join(name.split())
    return name


def detect_program_studi_columns(df: pd.DataFrame):
    """
    Deteksi semua kolom yang namanya diawali 'program_studi-'
    dan urutkan berdasarkan angka di belakangnya.
    """
    prog_cols = [c for c in df.columns if c.startswith("program_studi-")]
    # urutkan berdasarkan angka setelah dash
    def col_key(c):
        m = re.search(r"program_studi-(\d+)", c)
        return int(m.group(1)) if m else 0

    prog_cols = sorted(prog_cols, key=col_key)
    return prog_cols


def get_program_list_from_row(row, prog_cols):
    """
    Ambil daftar program studi dari satu baris (hanya yang tidak kosong).
    Kembalikan list string.
    """
    values = []
    for col in prog_cols:
        if col not in row:
            continue
        v = row[col]
        if pd.isna(v):
            continue
        if isinstance(v, str):
            if v.strip() == "":
                continue
            values.append(v.strip())
        else:
            # kalau bukan string, tetap dimasukkan, tapi dalam bentuk string
            values.append(str(v))
    return values


def main():
    print(f"Membaca file: {INPUT_FILE}")
    df = pd.read_excel(INPUT_FILE)

    if NAMA_DOSEN_COL not in df.columns:
        raise ValueError(f"Kolom '{NAMA_DOSEN_COL}' tidak ditemukan di file Excel!")

    # Simpan index asli untuk referensi (misal ingin tahu baris Excel keberapa)
    df["__row_index_original"] = df.index + 2  # +2 kalau mau kira-kira nomor baris Excel (header di baris 1)

    # Deteksi kolom program_studi yang ada sekarang
    program_cols = detect_program_studi_columns(df)
    if not program_cols:
        raise ValueError("Tidak ditemukan kolom yang diawali 'program_studi-' di file Excel.")

    print("Kolom program_studi terdeteksi:", program_cols)

    # Tambah kolom normalisasi nama dosen
    df["__nama_norm"] = df[NAMA_DOSEN_COL].apply(normalize_name)

    # Log perubahan gabungan
    changes_log = []
    rows_to_drop = []
    merged_programs_for_master = {}  # index_master -> list program gabungan
    master_before_programs = {}      # index_master -> list program sebelum gabung

    max_program_count_overall = len(program_cols)

    # Group berdasarkan nama yang sudah dinormalisasi
    grouped = df.groupby("__nama_norm", dropna=False)

    for nama_norm, group in grouped:
        # Abaikan nama kosong
        if nama_norm == "" or pd.isna(nama_norm):
            continue

        if len(group) <= 1:
            # tidak ada duplikat
            continue

        # Ada lebih dari 1 baris dengan nama_norm yang sama → kandidat duplikat
        group_indices = list(group.index)
        # Anggap baris pertama berdasarkan index sebagai master
        group_indices.sort()
        master_idx = group_indices[0]
        other_indices = group_indices[1:]

        master_row = df.loc[master_idx]
        master_name = master_row[NAMA_DOSEN_COL]

        # Program studi awal (sebelum penggabungan)
        master_programs = get_program_list_from_row(master_row, program_cols)
        master_before_programs[master_idx] = list(master_programs)  # simpan untuk log

        # Kumpulkan semua program_studi dari baris lain
        all_other_programs = []

        for idx in other_indices:
            row = df.loc[idx]
            progs = get_program_list_from_row(row, program_cols)
            all_other_programs.extend(progs)
            rows_to_drop.append(idx)

        # Gabungkan semua program studi (master + lainnya),
        # dan hilangkan duplikat sambil mempertahankan urutan muncul.
        merged_programs = []
        for p in master_programs + all_other_programs:
            if p not in merged_programs:
                merged_programs.append(p)

        merged_programs_for_master[master_idx] = merged_programs

        # Catat jumlah maksimum program yang diperlukan secara global
        if len(merged_programs) > max_program_count_overall:
            max_program_count_overall = len(merged_programs)

        # Siapkan log perubahan per kelompok nama
        changes_log.append(
            {
                "nama_dosen": master_name,
                "nama_dosen_norm": nama_norm,
                "index_master_df": master_idx,
                "row_excel_master": int(df.loc[master_idx, "__row_index_original"]),
                "index_duplikat_lain_df": ",".join(map(str, other_indices)),
                "rows_excel_duplikat_lain": ",".join(
                    str(int(df.loc[i, "__row_index_original"])) for i in other_indices
                ),
                "program_studi_master_before": "|".join(master_programs),
                "program_studi_duplikat_lain": "|".join(all_other_programs),
                "program_studi_final_after_merge": "|".join(merged_programs),
            }
        )

    # Kalau tidak ada duplikat, tinggal simpan apa adanya
    if not merged_programs_for_master:
        print("Tidak ditemukan nama dosen yang duplikat (100% sama setelah normalisasi).")
        print(f"Menyimpan file tanpa perubahan ke: {OUTPUT_FIXED_FILE}")
        df.drop(columns=["__nama_norm", "__row_index_original"], errors="ignore").to_excel(
            OUTPUT_FIXED_FILE, index=False
        )

        # Log kosong
        log_df = pd.DataFrame(columns=[
            "nama_dosen",
            "nama_dosen_norm",
            "index_master_df",
            "row_excel_master",
            "index_duplikat_lain_df",
            "rows_excel_duplikat_lain",
            "program_studi_master_before",
            "program_studi_duplikat_lain",
            "program_studi_final_after_merge",
        ])
        deleted_rows_df = pd.DataFrame(columns=df.columns)

        with pd.ExcelWriter(OUTPUT_LOG_FILE, engine="openpyxl") as writer:
            log_df.to_excel(writer, sheet_name="changes", index=False)
            deleted_rows_df.to_excel(writer, sheet_name="deleted_rows", index=False)

        print(f"Log perubahan (kosong) disimpan ke: {OUTPUT_LOG_FILE}")
        return

    # ================================
    # PASTIKAN KOLUM PROGRAM_STUDI CUKUP
    # ================================
    # Jika total program studi gabungan > jumlah kolom sekarang, tambahkan kolom baru.
    current_prog_count = len(program_cols)
    if max_program_count_overall > current_prog_count:
        print(
            f"Menambah kolom program_studi karena ada dosen dengan total "
            f"{max_program_count_overall} program studi (kolom awal: {current_prog_count})."
        )
        for i in range(current_prog_count + 1, max_program_count_overall + 1):
            new_col = f"program_studi-{i}"
            if new_col not in df.columns:
                df[new_col] = pd.NA
                program_cols.append(new_col)

    # ==================================
    # TULISKAN HASIL GABUNGAN KE MASTER
    # ==================================
    for master_idx, merged_programs in merged_programs_for_master.items():
        # Kosongkan dulu semua kolom program_studi di baris master
        for col in program_cols:
            df.at[master_idx, col] = pd.NA

        # Isi ulang dari kiri dengan daftar program studi gabungan
        for i, p in enumerate(merged_programs):
            if i >= len(program_cols):
                # Ini tidak seharusnya terjadi karena kita sudah menambah kolom di atas
                break
            col = program_cols[i]
            df.at[master_idx, col] = p

    # ================================
    # SIAPKAN DATA YANG DIHAPUS
    # ================================
    rows_to_drop_unique = sorted(set(rows_to_drop))
    print(f"Total baris duplikat yang akan dihapus: {len(rows_to_drop_unique)}")

    deleted_rows_df = df.loc[rows_to_drop_unique].copy()

    # ================================
    # BERSIHKAN & SIMPAN HASIL
    # ================================
    df_dedup = df.drop(index=rows_to_drop_unique).copy()

    # Hapus kolom bantu dari output akhir
    for tmp_col in ["__nama_norm", "__row_index_original"]:
        if tmp_col in df_dedup.columns:
            df_dedup = df_dedup.drop(columns=[tmp_col])
        if tmp_col in deleted_rows_df.columns:
            deleted_rows_df = deleted_rows_df.drop(columns=[tmp_col])

    print(f"Menyimpan file hasil deduplikasi ke: {OUTPUT_FIXED_FILE}")
    df_dedup.to_excel(OUTPUT_FIXED_FILE, index=False)

    # ================================
    # SIMPAN LOG PERUBAHAN & DATA DIHAPUS
    # ================================
    log_df = pd.DataFrame(changes_log)

    print(f"Menyimpan log perubahan ke: {OUTPUT_LOG_FILE}")
    with pd.ExcelWriter(OUTPUT_LOG_FILE, engine="openpyxl") as writer:
        log_df.to_excel(writer, sheet_name="changes", index=False)
        deleted_rows_df.to_excel(writer, sheet_name="deleted_rows", index=False)

    print("Selesai ✅")


if __name__ == "__main__":
    main()