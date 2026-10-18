
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
# ==========================================

def normalisasi_teks(teks):
    teks = unicodedata.normalize("NFKC", teks)
    teks = teks.replace("\u00ad", "")
    teks = teks.replace("\u00a0", " ")
    teks = re.sub(r"\s+", " ", teks)
    return teks.casefold().strip()


# ==========================================
# MENCARI KATA DALAM SELURUH PDF
# ==========================================

def cari_kata(kata):
    hasil = []

    kata = kata.strip()

    if not kata:
        return hasil

    kata_normal = normalisasi_teks(kata)

    if not FOLDER_PDF.is_dir():
        app.logger.error(
            "Folder PDF tidak ditemukan: %s",
            FOLDER_PDF
        )
        return hasil

    daftar_pdf = sorted(
        file
        for file in FOLDER_PDF.iterdir()
        if file.is_file()
        and file.suffix.lower() == ".pdf"
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
                "Gagal membaca PDF: %s",
                file_pdf.name
            )

    return hasil


# ==========================================
# HALAMAN WEBSITE
# ==========================================

@app.get("/")
def beranda():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/login.html")
def halaman_login():
    return send_from_directory(BASE_DIR, "login.html")


@app.get("/index.html")
def dashboard():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/procurement-template.html")
def procurementtemplate():
    return send_from_directory(
        BASE_DIR,
        "procurement-template.html"
    )

@app.get("/addendum-skd-panitia.html")
def addskdpanitia():
    return send_from_directory(
        BASE_DIR,
        "addendum-skd-panitia.html"
    )

@app.get("/addsurat-pembentukan-panitia.html")
def pembentukanpanitia():
    return send_from_directory(
        BASE_DIR,
        "addsurat-pembentukan-panitia.html"
    )


@app.get("/ba-pembukaan-dokumen.html")
def pembukaandokumen():
    return send_from_directory(
        BASE_DIR,
        "ba-pembukaan-dokumen.html"
    )

@app.get("/ba-serah-terima.html")
def serahterima():
    return send_from_directory(
        BASE_DIR,
        "ba-serah-terima.html"
    )

@app.get("/hps.html")
def hps():
    return send_from_directory(
        BASE_DIR,
        "hps.html"
    )

@app.get("/ikpp.html")
def ikpp():
    return send_from_directory(
        BASE_DIR,
        "ikpp.html"
    )

@app.get("/lhpp.html")
def lhpp():
    return send_from_directory(
        BASE_DIR,
        "lhpp.html"
    )

@app.get("/pakta-integritas.html")
def pakta():
    return send_from_directory(
        BASE_DIR,
        "pakta-integritas.html"
    )

@app.get("/pengumuman-hasil-pemilihan.html")
def hasilpemilihan():
    return send_from_directory(
        BASE_DIR,
        "pengumuman-hasil-pemilihan.html"
    )

@app.get("/skd-panitia.html")
def skdpanita():
    return send_from_directory(
        BASE_DIR,
        "skd-panitia.html"
    )

@app.get("/surat-panitia.html")
def suratpanita():
    return send_from_directory(
        BASE_DIR,
        "surat-panitia.html"
    )

@app.get("/procurement-document.html")
def procurementdocument():
    return send_from_directory(
        BASE_DIR,
        "procurement-document.html"
    )


@app.get("/regulation-finder.html")
def regulation_finder():
    return send_from_directory(
        BASE_DIR,
        "regulation-finder.html"
    )


# ==========================================
# FILE JAVASCRIPT
# ==========================================

@app.get("/js/<path:nama_file>")
def file_javascript(nama_file):
    return send_from_directory(
        BASE_DIR / "js",
        nama_file
    )


# ==========================================
# FILE LOGO
# ==========================================

@app.get("/logo/<path:nama_file>")
def file_logo(nama_file):
    return send_from_directory(
        BASE_DIR / "logo",
        nama_file
    )


# ==========================================
# MEMBUKA FILE PDF
# ==========================================

@app.get("/data regulation finder/<path:nama_file>")
def buka_pdf(nama_file):
    return send_from_directory(
        FOLDER_PDF,
        nama_file
    )


# ==========================================
# API DAFTAR SEMUA DOKUMEN
# Ditampilkan sebelum pengguna mencari
# ==========================================

@app.get("/api/documents")
def api_documents():
    if not FOLDER_PDF.is_dir():
        return jsonify({
            "documents": [],
            "jumlah": 0,
            "error": "Folder PDF tidak ditemukan."
        }), 404

    daftar_pdf = sorted(
        file.name
        for file in FOLDER_PDF.iterdir()
        if file.is_file()
        and file.suffix.lower() == ".pdf"
    )

    return jsonify({
        "documents": daftar_pdf,
        "jumlah": len(daftar_pdf)
    })


# ==========================================
# API PENCARIAN ISI PDF
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

    if not kata:
        return jsonify({
            "kata": "",
            "jumlah": 0,
            "hasil": []
        })

    if not FOLDER_PDF.is_dir():
        return jsonify({
            "kata": kata,
            "jumlah": 0,
            "hasil": [],
            "pesan": "Folder PDF tidak ditemukan."
        }), 404

    hasil = cari_kata(kata)

    return jsonify({
        "kata": kata,
        "jumlah": len(hasil),
        "hasil": hasil
    })


# ==========================================
# MENJALANKAN SERVER FLASK
# ==========================================

if __name__ == "__main__":
    print("=" * 45)
    print("SERVER REGULATION FINDER")
    print("=" * 45)
    print("Lokasi proyek :", BASE_DIR)
    print("Folder PDF    :", FOLDER_PDF)
    print("Folder tersedia:", FOLDER_PDF.is_dir())

    if FOLDER_PDF.is_dir():
        jumlah_pdf = sum(
            1
            for file in FOLDER_PDF.iterdir()
            if file.is_file()
            and file.suffix.lower() == ".pdf"
        )
        print("Jumlah file PDF:", jumlah_pdf)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
