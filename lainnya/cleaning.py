import json
import re

# Baca file JSON
with open("pengumuman_usu.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Fungsi bersih teks
def clean_text(value):
    if isinstance(value, str):
        # Hapus newline -> jadi spasi
        text = value.replace("\n", " ")
        # Ganti spasi berlebih jadi satu
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    elif isinstance(value, list):
        return [clean_text(v) for v in value]
    elif isinstance(value, dict):
        return {k: clean_text(v) for k, v in value.items()}
    return value

cleaned_data = clean_text(data)

# Simpan hasil
with open("data_clean.json", "w", encoding="utf-8") as f:
    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

print("Selesai! JSON bersih disimpan ke data_clean.json")
