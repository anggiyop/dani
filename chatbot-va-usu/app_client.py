import requests

BASE_URL = "http://127.0.0.1:8000/chat"

def main():
    print("=== Client Chatbot SOP (CTRL+C untuk keluar) ===")
    while True:
        try:
            msg = input("\nAnda : ").strip()
            if not msg:
                continue

            payload = {"message": msg}
            headers = {"Content-Type": "application/json"}

            resp = requests.post(BASE_URL, json=payload, headers=headers, timeout=300)

            # Kalau backend error (500, 422, dll), tampilkan isi respons
            if resp.status_code != 200:
                print(f"[ERROR] Status: {resp.status_code}")
                print("Response:", resp.text)
                continue

            data = resp.json()
            print(f"Asisten ({data['intent']}): {data['answer']}\n")

            if data.get("sources"):
                print("Sumber:")
                for s in data["sources"]:
                    print(
                        f"- {s.get('judul_sop')} | Bagian: {s.get('bagian')} "
                        f"| Langkah: {s.get('no_urut')} | Halaman: {s.get('halaman')}"
                    )

        except KeyboardInterrupt:
            print("\nKeluar.")
            break
        except Exception as e:
            print("Terjadi error:", e)

if __name__ == "__main__":
    main()
