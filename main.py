
from pathlib import Path
import re
import unicodedata

import pymupdf
from flask import Flask, jsonify, request, send_from_directory


# ==========================================
# PENGATURAN FOLDER
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
FOLDER_PDF = BASE_DIR / "data regulation finder"

app = Flask(__name__)


# ==========================================
# NORMALISASI TEKS
# Menyamakan huruf dan spasi agar pencarian
# lebih tahan terhadap baris baru dalam PDF.
# ==========================================

def normalisasi_teks(teks):
    teks = unicodedata.normalize("NFKC", teks)
    teks = teks.replace("\u00ad", "")
    teks = teks.replace("\u00a0", " ")
    teks = re.sub(r"\s+", " ", teks)
    return teks.casefold().strip()


# ==========================================
# PENCARIAN DALAM SELURUH PDF
# ==========================================

def cari_kata(kata):
    hasil = []

    kata = kata.strip()

    if not kata:
        return hasil

    kata_normal = normalisasi_teks(kata)

    if not FOLDER_PDF.is_dir():
        app.logger.error(
            "Folder PDF tidak ditemukan: %s", FOLDER_PDF
        )
        return hasil

    daftar_pdf = sorted(
        file for file in FOLDER_PDF.iterdir()
        if file.is_file() and file.suffix.lower() == ".pdf"
    )

    for file_pdf in daftar_pdf:
        try:
            with pymupdf.open(file_pdf) as dokumen:
                for nomor_halaman, halaman in enumerate(
                    dokumen, start=1
                ):
                    teks = halaman.get_text("text")

                    if not teks.strip():
                        continue

                    teks_normal = normalisasi_teks(teks)

                    posisi = teks_normal.find(kata_normal)

                    if posisi == -1:
                        continue

                    awal = max(0, posisi - 100)
                    akhir = min(
                        len(teks_normal),
                        posisi + len(kata_normal) + 150
                    )

                    cuplikan = teks_normal[awal:akhir]

                    hasil.append({
                        "file": file_pdf.name,
                        "halaman": nomor_halaman,
                        "cuplikan": cuplikan
                    })

        except Exception:
            app.logger.exception(
                "Gagal membaca PDF: %s", file_pdf.name
            )

    return hasil


# ==========================================
# HALAMAN WEBSITE
# ==========================================

@app.get("/login.html")
def halaman_login():
    return send_from_directory(BASE_DIR, "login.html")


@app.get("/")
def beranda():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/index.html")
def dashboard():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/regulation-finder.html")
def regulation_finder():
    return send_from_directory(
        BASE_DIR, "regulation-finder.html"
    )


@app.get("/js/<path:nama_file>")
def file_javascript(nama_file):
    return send_from_directory(BASE_DIR / "js", nama_file)


@app.get("/logo/<path:nama_file>")
def file_logo(nama_file):
    return send_from_directory(BASE_DIR / "logo", nama_file)


# ==========================================
# MEMBUKA FILE PDF
# ==========================================

@app.get("/data regulation finder/<path:nama_file>")
def buka_pdf(nama_file):
    return send_from_directory(FOLDER_PDF, nama_file)


# ==========================================
# API PENCARIAN
# Dipanggil oleh regulation-finder.js
# ==========================================

@app.post("/api/search")
def api_search():
    data = request.get_json(silent=True) or {}

    kata = data.get("kata", "")

    if not isinstance(kata, str):
        return jsonify({
            "error": "Kata pencarian harus berupa teks."
        }), 400

    kata = kata.strip()

    if len(kata) > 200:
        return jsonify({
            "error": "Kata pencarian maksimal 200 karakter."
        }), 400

    if not FOLDER_PDF.is_dir():
        return jsonify({
            "kata": kata,
            "jumlah": 0,
            "hasil": [],
            "pesan": "Folder PDF tidak ditemukan."
        })

    hasil = cari_kata(kata)

    return jsonify({
        "kata": kata,
        "jumlah": len(hasil),
        "hasil": hasil
    })


# ==========================================
# JALANKAN SERVER
# ==========================================

if __name__ == "__main__":
    print("Server Document Finder")
    print("Folder PDF:", FOLDER_PDF)
    print("Folder tersedia:", FOLDER_PDF.is_dir())

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
