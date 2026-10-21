from pathlib import Path
import re
import unicodedata
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import pymupdf
from flask import Flask, jsonify, request, send_from_directory

# --- LIBRARY MACHINE LEARNING LOKAL (TF-IDF) ---
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# ==========================================
# PENGATURAN FOLDER & FLASK
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
FOLDER_PDF = BASE_DIR / "data regulation finder"
FOLDER_PDF.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# ==========================================
# DATABASE SQLITE (SISTEM LOGIN)
# ==========================================
DB_NAME = BASE_DIR / "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                  password TEXT NOT NULL)''')
    
    c.execute("SELECT password FROM users WHERE username='admin'")
    user_admin = c.fetchone()
    if not user_admin:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', generate_password_hash('123')))
    else:
        try:
            if not check_password_hash(user_admin[0], '123') and not check_password_hash(user_admin[0], 'admin123'):
                pass
        except ValueError:
            c.execute("UPDATE users SET password=? WHERE username='admin'", (generate_password_hash('123'),))
        
    conn.commit()
    conn.close()
    print("[DB] Database SQLite 'database.db' siap dan terhubung!")

init_db()

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password: return jsonify({"error": "Username dan password wajib diisi."}), 400
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        conn.close()
        return jsonify({"message": "Akun berhasil didaftarkan!"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username ini sudah terdaftar. Silakan pilih yang lain."}), 400

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()

    is_valid = False
    if user:
        try:
            is_valid = check_password_hash(user[0], password)
        except ValueError:
            is_valid = (user[0] == password)

    if user and is_valid:
        if user[0] == password:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET password=? WHERE username=?", (generate_password_hash(password), username))
            conn.commit()
            conn.close()
        return jsonify({"message": "Login berhasil!"}), 200
    else:
        return jsonify({"error": "Username atau password salah!"}), 401


# ==========================================
# KONFIGURASI GEMINI AI & TF-IDF RAG
# ==========================================
API_KEY = "AQ.Ab8RN6JRt0GJreirZW6gfBfJ6VaF856bd4k31oTjV2pqvwY18g"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')

MEMORY_DOKUMEN = []
vectorizer = TfidfVectorizer()
tfidf_matrix = None

def bersihkan_teks(teks):
    teks = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", teks)
    teks = unicodedata.normalize("NFKC", teks)
    return re.sub(r"\s+", " ", teks.replace("\u00ad", "").replace("\u00a0", " ")).strip()

def chunk_text(teks, chunk_size=800, overlap=150):
    """Memecah teks menjadi potongan paragraf agar TF-IDF lebih tajam."""
    chunks = []
    start = 0
    teks_len = len(teks)
    while start < teks_len:
        end = start + chunk_size
        chunks.append(teks[start:end])
        start += chunk_size - overlap
    return chunks

def load_knowledge_base():
    """Fase TRAINING: Membaca PDF dan melatih model matematika TF-IDF secara lokal."""
    global MEMORY_DOKUMEN, vectorizer, tfidf_matrix
    MEMORY_DOKUMEN = []
    
    if not FOLDER_PDF.is_dir(): return
    
    print("\n[ML] Membaca PDF dan melatih model TF-IDF...")
    daftar_pdf = sorted(f for f in FOLDER_PDF.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")

    for file_pdf in daftar_pdf:
        try:
            with pymupdf.open(file_pdf) as dokumen:
                for nomor_halaman, halaman in enumerate(dokumen, start=1):
                    teks_asli = bersihkan_teks(halaman.get_text("text"))
                    if len(teks_asli) > 50:
                        potongan = chunk_text(teks_asli)
                        for p in potongan:
                            MEMORY_DOKUMEN.append({
                                "file": file_pdf.name,
                                "halaman": nomor_halaman,
                                "teks": p
                            })
        except Exception as e:
            print(f"[ML] Gagal membaca {file_pdf.name}: {e}")

    if MEMORY_DOKUMEN:
        # PROSES PELATIHAN TF-IDF
        tfidf_matrix = vectorizer.fit_transform([doc["teks"] for doc in MEMORY_DOKUMEN])
        print(f"[ML] Selesai! Model TF-IDF dilatih dengan {len(MEMORY_DOKUMEN)} potongan paragraf. Siap digunakan!\n")

load_knowledge_base()

# ==========================================
# API CHATBOT (RETRIEVAL TF-IDF + GENERATION GEMINI)
# ==========================================
@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    pertanyaan = data.get("pesan", "").strip()

    if not pertanyaan: return jsonify({"error": "Pesan tidak boleh kosong"}), 400
    if tfidf_matrix is None or len(MEMORY_DOKUMEN) == 0: 
        return jsonify({"error": "Database dokumen kosong. Upload PDF dulu."}), 400

    try:
        # 1. FASE RETRIEVAL (PENCARIAN LOKAL DENGAN TF-IDF)
        query_vec = vectorizer.transform([pertanyaan])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        # Ambil 5 paragraf dengan skor kecocokan tertinggi
        best_indices = similarities.argsort()[-5:][::-1]
        
        kumpulan_cuplikan = []
        for idx in best_indices:
            if similarities[idx] > 0.01: # Toleransi kemiripan
                chunk = MEMORY_DOKUMEN[idx]
                kumpulan_cuplikan.append(f"- SUMBER: {chunk['file']} (Halaman {chunk['halaman']})\n  ISI: {chunk['teks']}")

        konteks_dokumen = "\n\n".join(kumpulan_cuplikan) if kumpulan_cuplikan else "Tidak ada teks relevan yang ditemukan."

        # 2. FASE GENERATION (MERANGKAI JAWABAN DENGAN GEMINI)
        prompt = f"""
Kamu adalah Asisten AI profesional untuk Portal Pengadaan PT Semen Indonesia (Persero) Tbk (SIG).
Tugasmu adalah menjawab pertanyaan pengguna HANYA berdasarkan potongan dokumen di bawah ini.
Gunakan bahasa Indonesia yang ramah, sopan, jelas, dan profesional.
WAJIB menyebutkan nama SUMBER dan Halaman di akhir penjelasanmu.
Jika informasi tidak ada di dalam dokumen referensi, katakan dengan sopan bahwa informasi tidak tersedia di pedoman pengadaan.

SUMBER DOKUMEN PENGADAAN SIG:
{konteks_dokumen}

Pertanyaan Pengguna: "{pertanyaan}"
"""
        response = model.generate_content(prompt)
        return jsonify({"jawaban": response.text})
        
    except Exception as e:
        app.logger.exception("Gagal memproses RAG")
        return jsonify({"error": f"Server AI error: {str(e)}"}), 500

# ==========================================
# PENCARIAN EXACT-MATCH (UNTUK REGULATION FINDER)
# ==========================================
def normalisasi_teks(teks):
    return bersihkan_teks(teks).casefold()

def ekstrak_cuplikan(teks_asli, teks_cari, kata_cari, panjang_sebelum=500, panjang_sesudah=800):
    posisi = teks_cari.find(kata_cari)
    if posisi == -1: return ""
    panjang_kata = len(kata_cari)
    awal = max(0, posisi - panjang_sebelum)
    akhir = min(len(teks_asli), posisi + panjang_kata + panjang_sesudah)
    
    if awal > 0:
        spasi_awal = teks_asli.find(" ", awal)
        if spasi_awal != -1 and spasi_awal < posisi: awal = spasi_awal + 1
    if akhir < len(teks_asli):
        spasi_akhir = teks_asli.rfind(" ", posisi + panjang_kata, akhir)
        if spasi_akhir != -1 and spasi_akhir > posisi + panjang_kata: akhir = spasi_akhir
        
    cuplikan = teks_asli[awal:akhir].strip()
    return f"... {cuplikan} ..." if awal > 0 else f"{cuplikan} ..."

def cari_kata_cepat(kata):
    hasil = []
    kata = kata.strip()
    if not kata: return hasil
    kata_normal = normalisasi_teks(kata)
    
    for doc in MEMORY_DOKUMEN:
        teks_cari = doc["teks"].casefold()
        if kata_normal in teks_cari:
            cuplikan = ekstrak_cuplikan(doc["teks"], teks_cari, kata_normal)
            hasil.append({
                "file": doc["file"],
                "halaman": doc["halaman"],
                "cuplikan": cuplikan
            })
    return hasil

@app.post("/api/search")
def api_search():
    kata = (request.get_json(silent=True) or {}).get("kata", "").strip()
    if not kata: return jsonify({"kata": "", "jumlah": 0, "hasil": []})
    hasil = cari_kata_cepat(kata)
    return jsonify({"kata": kata, "jumlah": len(hasil), "hasil": hasil})

# ==========================================
# API PENGELOLAAN DOKUMEN (UPLOAD & DELETE)
# ==========================================
@app.post("/api/upload")
def api_upload():
    if 'file' not in request.files: return jsonify({"error": "Tidak ada file"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "Nama file kosong"}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        safe_filename = file.filename.replace("/", "-").replace("\\", "-")
        filepath = FOLDER_PDF / safe_filename
        file.save(filepath)
        load_knowledge_base() # Training ulang TF-IDF secara otomatis
        return jsonify({"message": "Berhasil upload dan model TF-IDF telah dilatih ulang!"}), 200
    return jsonify({"error": "Hanya menerima PDF."}), 400

@app.delete("/api/documents/<path:nama_file>")
def api_delete(nama_file):
    safe_filename = nama_file.replace("/", "-").replace("\\", "-")
    filepath = FOLDER_PDF / safe_filename
    if filepath.exists() and filepath.is_file():
        filepath.unlink() 
        load_knowledge_base() # Training ulang TF-IDF secara otomatis
        return jsonify({"message": "Dihapus"}), 200
    return jsonify({"error": "File tidak ditemukan"}), 404

# ==========================================
# HALAMAN WEBSITE & LAINNYA
# ==========================================
@app.get("/")
def beranda(): return send_from_directory(BASE_DIR, "index.html")

@app.get("/<path:page>")
def serve_pages(page):
    if not page.endswith(".html"): return "Not Found", 404
    return send_from_directory(BASE_DIR, page)

@app.get("/js/<path:nama_file>")
def file_javascript(nama_file): return send_from_directory(BASE_DIR / "js", nama_file)

@app.get("/logo/<path:nama_file>")
def file_logo(nama_file): return send_from_directory(BASE_DIR / "logo", nama_file)

@app.get("/data regulation finder/<path:nama_file>")
def buka_pdf(nama_file): return send_from_directory(FOLDER_PDF, nama_file)

@app.get("/api/documents")
def api_documents():
    if not FOLDER_PDF.is_dir(): return jsonify({"documents": [], "jumlah": 0})
    daftar_pdf = sorted(f.name for f in FOLDER_PDF.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")
    return jsonify({"documents": daftar_pdf, "jumlah": len(daftar_pdf)})

if __name__ == "__main__":
    print("=" * 45)
    print("SERVER REGULATION FINDER & HYBRID RAG")
    print("=" * 45)
    app.run(host="127.0.0.1", port=5000, debug=True)