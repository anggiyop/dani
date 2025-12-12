import pandas as pd
import numpy as np
import json

# Baca Excel
df = pd.read_excel("pengumuman_usu.xlsx")

# Ganti semua NaN/NaT dengan None
df = df.replace({np.nan: None})

# Convert ke dict
data = df.to_dict(orient="records")

# Simpan ke JSON
with open("pengumuman_usu.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
