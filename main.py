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
FOLDER_PROCUREMENT = BASE_DIR / "data procurement document"
FOLDER_PROCUREMENT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# ==========================================
# DATABASE SQLITE (SISTEM LOGIN)
# ==========================================
DB_NAME = BASE_DIR / "database.db"

def init_db():
    """Membuat tabel users jika belum ada, migrasi kolom role, dan inisialisasi akun admin default."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                  password TEXT NOT NULL,
                  role TEXT NOT NULL DEFAULT 'user')''')
    
    # Cek apakah akun admin sudah ada
    c.execute("SELECT password, role FROM users WHERE LOWER(username)='admin'")
    user_admin = c.fetchone()
    if not user_admin:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'admin')", ('admin', generate_password_hash('123'), 'admin'))
    else:
        # Pastikan akun admin memiliki role admin
        if len(user_admin) > 1 and (not user_admin[1] or user_admin[1].lower() != 'admin'):
            c.execute("UPDATE users SET role='admin' WHERE LOWER(username)='admin'")
        # Pastikan password admin selalu ter-hash secara aman
        try:
            if not check_password_hash(user_admin[0], '123') and not check_password_hash(user_admin[0], 'admin123'):
                c.execute("UPDATE users SET password=? WHERE LOWER(username)='admin'", (generate_password_hash('123'),))
        except ValueError:
            # Jika sebelumnya tersimpan sebagai plain text '123'
            c.execute("UPDATE users SET password=? WHERE LOWER(username)='admin'", (generate_password_hash('123'),))
        
    conn.commit()
    conn.close()
    print("[DB] Database SQLite 'database.db' siap dan terhubung!")

init_db()

def is_admin(username):
    """Memeriksa apakah username yang diberikan memiliki role admin di database."""
    if not username:
        return False
    u = username.strip().lower()
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE LOWER(TRIM(username))=LOWER(TRIM(?))", (username,))
        row = c.fetchone()
        if row and row[0] and row[0].strip().lower() in ["admin", "administrator"]:
            conn.close()
            return True
        # Cek apakah username ini adalah akun id 1 (Admin Utama)
        c.execute("SELECT username, role FROM users WHERE id=1")
        row1 = c.fetchone()
        conn.close()
        if row1 and row1[0] and row1[0].strip().lower() == u and row1[1].strip().lower() in ["admin", "administrator"]:
            return True
        return False
    except Exception:
        return False

def is_main_admin_user(username):
    """Memeriksa apakah username yang diberikan adalah akun Admin Utama (ID == 1)."""
    if not username:
        return False
    u = username.strip().lower()
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE id=1")
        row = c.fetchone()
        conn.close()
        if row and row[1] and row[1].strip().lower() == u:
            return True
        return False
    except Exception:
        return False

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = "user"  # Saat daftar akun sendiri, tidak ada pilihan role (default 'user'). Role ditentukan oleh Admin.

    if not username or not password:
        return jsonify({"error": "Username dan password wajib diisi."}), 400

    if len(password) < 4:
        return jsonify({"error": "Password minimal 4 karakter."}), 400

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Cek duplikasi username secara case-insensitive
        c.execute("SELECT id FROM users WHERE LOWER(TRIM(username))=LOWER(TRIM(?))", (username,))
        if c.fetchone():
            conn.close()
            return jsonify({"error": f"Username '{username}' sudah terdaftar. Silakan pilih username lain."}), 400

        hashed_pw = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_pw, role))
        conn.commit()
        conn.close()

        return jsonify({
            "message": f"Akun '{username}' berhasil didaftarkan!",
            "username": username,
            "role": role
        }), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Username '{username}' sudah terdaftar. Silakan pilih username lain."}), 400
    except Exception as e:
        return jsonify({"error": f"Gagal mendaftarkan akun: {str(e)}"}), 500

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password, role, username FROM users WHERE LOWER(username)=LOWER(?)", (username,))
    user = c.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Username atau password salah!"}), 401

    db_password = user[0]
    db_role = user[1] if (len(user) > 1 and user[1]) else "user"
    canonical_username = user[2] if len(user) > 2 and user[2] else username

    # Cek kecocokan password dengan hash (dengan backward-compatibility jika ada akun lama plain text)
    is_valid = False
    try:
        is_valid = check_password_hash(db_password, password)
    except ValueError:
        is_valid = (db_password == password)

    if is_valid:
        # Jika data user lama masih plain text, sekalian amankan menjadi hash
        if db_password == password:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE users SET password=? WHERE LOWER(username)=LOWER(?)", (generate_password_hash(password), canonical_username))
            conn.commit()
            conn.close()
        return jsonify({
            "message": "Login berhasil!",
            "username": canonical_username,
            "role": db_role
        }), 200
    else:
        return jsonify({"error": "Username atau password salah!"}), 401


# ==========================================
# API PROFIL PENGGUNA & GANTI PASSWORD MANDIRI
# ==========================================
@app.post("/api/user/change-password")
def api_user_change_password():
    """Memungkinkan pengguna (baik user biasa maupun admin) untuk mengubah/mereset password akunnya sendiri."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    old_password = data.get("old_password", "").strip()
    new_password = data.get("new_password", "").strip()

    if not username:
        return jsonify({"error": "Sesi username tidak valid."}), 400

    if not old_password:
        return jsonify({"error": "Password saat ini wajib diisi."}), 400

    if not new_password:
        return jsonify({"error": "Password baru wajib diisi."}), 400

    if len(new_password) < 4:
        return jsonify({"error": "Password baru minimal 4 karakter."}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, password, username FROM users WHERE LOWER(TRIM(username))=LOWER(TRIM(?))", (username,))
    user = c.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": f"Pengguna '{username}' tidak ditemukan."}), 404

    user_id, db_pw, canonical_username = user[0], user[1], user[2]

    # Cek verifikasi password saat ini
    is_valid = False
    try:
        is_valid = check_password_hash(db_pw, old_password)
    except ValueError:
        is_valid = (db_pw == old_password)

    if not is_valid:
        conn.close()
        return jsonify({"error": "Password saat ini (lama) tidak sesuai! Silakan periksa kembali."}), 400

    if old_password == new_password:
        conn.close()
        return jsonify({"error": "Password baru tidak boleh sama dengan password saat ini."}), 400

    hashed_pw = generate_password_hash(new_password)
    c.execute("UPDATE users SET password=? WHERE id=?", (hashed_pw, user_id))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Password untuk akun '{canonical_username}' berhasil diubah dan diamankan!"}), 200

@app.get("/api/user/profile")
def api_user_profile():
    """Mengambil detail akun pengguna yang sedang aktif login."""
    username = (request.args.get("username", "") or request.headers.get("X-User", "")).strip()
    if not username:
        return jsonify({"error": "Username wajib diisi."}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE LOWER(TRIM(username))=LOWER(TRIM(?))", (username,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Pengguna tidak ditemukan."}), 404

    is_main = bool(row[0] == 1)
    role_val = row[2] if (len(row) > 2 and row[2]) else "user"

    return jsonify({
        "id": row[0],
        "username": row[1],
        "role": role_val,
        "is_main_admin": is_main
    }), 200

# ==========================================
# API MANAJEMEN PASSWORD & PENGGUNA (ROLE ADMIN)
# ==========================================
@app.get("/api/admin/users")
def api_admin_get_users():
    """Mengambil seluruh daftar pengguna (hanya dapat diakses oleh role admin)."""
    admin_user = (request.headers.get("X-Admin-User", "") or request.args.get("admin", "")).strip()
    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Fitur ini hanya dapat diakses oleh role admin."}), 403

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()

    caller_is_main = is_main_admin_user(admin_user)

    users = []
    for r in rows:
        role_val = r[2] if (len(r) > 2 and r[2]) else "user"
        is_main = bool(r[0] == 1) # Admin Utama HANYA SATU (id == 1)
        users.append({
            "id": r[0],
            "username": r[1],
            "role": role_val,
            "is_main_admin": is_main
        })

    return jsonify({
        "users": users,
        "caller_is_main_admin": caller_is_main
    })

@app.post("/api/admin/add-user")
def api_admin_add_user():
    """Menambahkan akun pengguna baru secara manual oleh admin dengan pilihan role (ditentukan oleh admin utama atau admin biasa)."""
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user").strip().lower()

    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Fitur ini hanya dapat diakses oleh role admin."}), 403

    if not username or not password:
        return jsonify({"error": "Username dan password wajib diisi."}), 400

    if role not in ["admin", "user"]:
        role = "user"

    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_pw, role))
        conn.commit()
        conn.close()
        role_label = "Administrator" if role == "admin" else "Staff Pengadaan"
        return jsonify({"message": f"Pengguna '{username}' sebagai {role_label} berhasil ditambahkan!"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Username '{username}' sudah terdaftar. Silakan gunakan username lain."}), 400

@app.post("/api/admin/edit-user")
def api_admin_edit_user():
    """Mengedit username, role, dan/atau password pengguna oleh admin utama atau admin biasa."""
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    user_id = data.get("user_id")
    new_username = data.get("new_username", "").strip()
    new_password = data.get("new_password", "").strip()
    new_role = data.get("new_role", "user").strip().lower()

    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Fitur ini hanya dapat diakses oleh role admin."}), 403

    if not user_id or not new_username:
        return jsonify({"error": "ID pengguna dan username baru wajib diisi."}), 400

    if new_role not in ["admin", "user"]:
        new_role = "user"

    target_id_int = int(user_id)
    is_caller_main = is_main_admin_user(admin_user)

    if target_id_int == 1 and not is_caller_main:
        return jsonify({"error": "Akses ditolak! Admin biasa tidak berhak mengubah akun atau password Admin Utama."}), 403

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE id=?", (user_id,))
    target = c.fetchone()
    if not target:
        conn.close()
        return jsonify({"error": "Pengguna tidak ditemukan."}), 404

    old_username = target[1]
    old_role = target[2]
    is_self = (old_username.strip().lower() == admin_user.strip().lower())

    if target_id_int == 1:
        new_role = "admin"

    if old_role == "admin" and new_role != "admin":
        c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND id != ?", (user_id,))
        remaining_admins = c.fetchone()[0]
        if remaining_admins == 0:
            conn.close()
            return jsonify({"error": "Tidak dapat mengubah role menjadi user biasa karena harus ada minimal 1 Administrator di sistem."}), 400

    try:
        if new_password:
            hashed_pw = generate_password_hash(new_password)
            c.execute("UPDATE users SET username=?, password=?, role=? WHERE id=?", 
                      (new_username, hashed_pw, new_role, user_id))
        else:
            c.execute("UPDATE users SET username=?, role=? WHERE id=?", 
                      (new_username, new_role, user_id))
        conn.commit()
        conn.close()

        return jsonify({
            "message": f"Data akun '{new_username}' berhasil diperbarui!",
            "old_username": old_username,
            "new_username": new_username,
            "new_role": new_role,
            "is_self": is_self
        }), 200
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"Username '{new_username}' sudah dipakai oleh pengguna lain."}), 400

@app.post("/api/admin/change-password")
def api_admin_change_password():
    """Mengubah/mereset password pengguna atau admin itu sendiri."""
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    target_username = data.get("target_username", "").strip()
    new_password = data.get("new_password", "").strip()

    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Fitur ini hanya dapat diakses oleh role admin."}), 403

    if not target_username or not new_password:
        return jsonify({"error": "Username target dan password baru wajib diisi."}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE LOWER(username)=LOWER(?)", (target_username,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": f"Pengguna '{target_username}' tidak ditemukan."}), 404

    target_id, target_name, target_role = user[0], user[1], user[2]
    is_caller_main = is_main_admin_user(admin_user)
    is_self = (target_name.strip().lower() == admin_user.strip().lower())

    if target_id == 1 and not is_caller_main:
        conn.close()
        return jsonify({"error": "Akses ditolak! Admin biasa tidak berhak mengubah password Admin Utama."}), 403

    if target_role == "admin" and target_id != 1 and not is_caller_main and not is_self:
        conn.close()
        return jsonify({"error": "Akses ditolak! Hanya Admin Utama yang berhak mereset password Administrator lain."}), 403

    hashed_pw = generate_password_hash(new_password)
    c.execute("UPDATE users SET password=? WHERE id=?", (hashed_pw, target_id))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Password untuk '{target_name}' berhasil diubah dan diamankan dengan hash!"}), 200

@app.post("/api/admin/delete-user")
def api_admin_delete_user():
    """Menghapus akun pengguna atau admin lain (Admin Utama kebal dari penghapusan)."""
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    target_username = data.get("target_username", "").strip()
    target_id = data.get("target_id")

    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Fitur ini hanya dapat diakses oleh role admin."}), 403

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if target_id:
        c.execute("SELECT id, role, username FROM users WHERE id=?", (target_id,))
    else:
        c.execute("SELECT id, role, username FROM users WHERE LOWER(TRIM(username))=LOWER(TRIM(?))", (target_username,))
    target = c.fetchone()

    if not target:
        conn.close()
        return jsonify({"error": "Akun pengguna tidak ditemukan."}), 404

    target_id, target_role, actual_username = target[0], target[1], target[2]
    is_caller_main = is_main_admin_user(admin_user)

    if target_id == 1:
        conn.close()
        return jsonify({"error": "Akun Admin Utama tidak dapat dihapus demi keamanan sistem."}), 400

    if actual_username.strip().lower() == admin_user.strip().lower():
        conn.close()
        return jsonify({"error": "Anda tidak dapat menghapus akun Anda sendiri yang sedang aktif digunakan."}), 400

    is_target_admin = bool(target_role and target_role.strip().lower() in ["admin", "administrator"])
    if is_target_admin and not is_caller_main:
        conn.close()
        return jsonify({"error": "Akses ditolak! Hanya Admin Utama yang berhak menghapus akun Administrator."}), 403

    if is_target_admin:
        c.execute("SELECT COUNT(*) FROM users WHERE LOWER(TRIM(role)) IN ('admin', 'administrator')")
        admin_count = c.fetchone()[0]
        if admin_count <= 1:
            conn.close()
            return jsonify({"error": "Tidak dapat menghapus admin ini karena harus tersisa minimal 1 Administrator di sistem."}), 400

    c.execute("DELETE FROM users WHERE id=?", (target_id,))
    conn.commit()
    conn.close()

    role_label = "Administrator" if is_target_admin else "Pengguna"
    return jsonify({"message": f"{role_label} '{actual_username}' berhasil dihapus!"}), 200

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
    """Membersihkan teks PDF dengan tetap mempertahankan huruf besar/kecil asli."""
    teks = re.sub(r"(\w+)-\s*\s*(\w+)", r"  ", teks)
    teks = unicodedata.normalize("NFKC", teks)
    teks = teks.replace("颅", "")
    teks = teks.replace("聽", " ")
    return re.sub(r"\s+", " ", teks).strip()

def normalisasi_teks(teks):
    """Membersihkan teks dan mengubah menjadi huruf kecil untuk pencarian."""
    return bersihkan_teks(teks).casefold()

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
        query_vec = vectorizer.transform([pertanyaan])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        best_indices = similarities.argsort()[-5:][::-1]
        
        kumpulan_cuplikan = []
        for idx in best_indices:
            if similarities[idx] > 0.01:
                chunk = MEMORY_DOKUMEN[idx]
                kumpulan_cuplikan.append(f"- SUMBER: {chunk['file']} (Halaman {chunk['halaman']})\n  ISI: {chunk['teks']}")

        konteks_dokumen = "\n\n".join(kumpulan_cuplikan) if kumpulan_cuplikan else "Tidak ada teks relevan yang ditemukan."

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
def ekstrak_cuplikan(teks_asli, teks_cari, kata_cari, panjang_sebelum=750, panjang_sesudah=1100):
    """Mengekstrak cuplikan/ringkasan yang jauh lebih panjang, utuh, dan rapi dari teks halaman PDF."""
    posisi = teks_cari.find(kata_cari)
    if posisi == -1: return ""

    panjang_kata = len(kata_cari)
    awal = max(0, posisi - panjang_sebelum)
    akhir = min(len(teks_asli), posisi + panjang_kata + panjang_sesudah)

    if awal > 0:
        spasi_awal = teks_asli.find(" ", awal)
        if spasi_awal != -1 and spasi_awal < posisi:
            awal = spasi_awal + 1

    if akhir < len(teks_asli):
        spasi_akhir = teks_asli.rfind(" ", posisi + panjang_kata, akhir)
        if spasi_akhir != -1 and spasi_akhir > posisi + panjang_kata:
            akhir = spasi_akhir

    cuplikan = teks_asli[awal:akhir].strip()

    if awal > 0: cuplikan = "... " + cuplikan
    if akhir < len(teks_asli): cuplikan = cuplikan + " ..."

    return cuplikan

def cari_kata(kata):
    hasil = []
    kata = kata.strip()
    if not kata: return hasil

    kata_normal = normalisasi_teks(kata)
    if not FOLDER_PDF.is_dir(): return hasil

    daftar_pdf = sorted(file for file in FOLDER_PDF.iterdir() if file.is_file() and file.suffix.lower() == ".pdf")

    for file_pdf in daftar_pdf:
        try:
            with pymupdf.open(file_pdf) as dokumen:
                for nomor_halaman, halaman in enumerate(dokumen, start=1):
                    teks = halaman.get_text("text")
                    if not teks.strip(): continue

                    teks_asli = bersihkan_teks(teks)
                    teks_cari = teks_asli.casefold()

                    if kata_normal not in teks_cari: continue

                    cuplikan = ekstrak_cuplikan(
                        teks_asli=teks_asli,
                        teks_cari=teks_cari,
                        kata_cari=kata_normal,
                        panjang_sebelum=750,
                        panjang_sesudah=1100
                    )

                    hasil.append({
                        "file": file_pdf.name,
                        "halaman": nomor_halaman,
                        "cuplikan": cuplikan
                    })
        except Exception:
            app.logger.exception("Gagal membaca PDF: %s", file_pdf.name)

    return hasil

@app.post("/api/search")
def api_search():
    data = request.get_json(silent=True) or {}
    kata = data.get("kata", "")

    if not isinstance(kata, str):
        return jsonify({"error": "Kata pencarian harus berupa teks."}), 400

    kata = kata.strip()
    if len(kata) > 1000:
        return jsonify({"error": "Kata atau kalimat pencarian maksimal 1000 karakter."}), 400

    if not kata:
        return jsonify({"kata": "", "jumlah": 0, "hasil": []})

    if not FOLDER_PDF.is_dir():
        return jsonify({"kata": kata, "jumlah": 0, "hasil": [], "pesan": "Folder PDF tidak ditemukan."}), 404

    hasil = cari_kata(kata)
    return jsonify({"kata": kata, "jumlah": len(hasil), "hasil": hasil})

# ==========================================
# API PENGELOLAAN DOKUMEN REGULASI (UPLOAD, DELETE, LIST)
# ==========================================
def get_auth_admin_user():
    """Mengambil username pemanggil dari Header HTTP, Form Data, atau Query Parameter."""
    user = (request.headers.get("X-Admin-User", "") or 
            request.form.get("admin_user", "") or 
            request.args.get("admin_user", "")).strip()
    if not user and request.is_json:
        user = (request.get_json(silent=True) or {}).get("admin_user", "").strip()
    return user

@app.post("/api/upload")
@app.post("/api/regulations/upload")
def api_upload():
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Hanya Administrator yang berhak menambahkan dokumen regulasi."}), 403

    if 'file' not in request.files: return jsonify({"error": "Tidak ada file yang dipilih"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "Nama file kosong"}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        safe_filename = file.filename.replace("/", "-").replace("\\", "-")

        filepath = FOLDER_PDF / safe_filename
        file.save(filepath)
        load_knowledge_base() 
        return jsonify({"message": f"Dokumen regulasi '{safe_filename}' berhasil diunggah dan model AI telah diperbarui!"}), 200
    return jsonify({"error": "Hanya menerima file berformat PDF (.pdf)."}), 400

@app.delete("/api/documents/<path:nama_file>")
@app.delete("/api/regulations/<path:nama_file>")
def api_delete(nama_file):
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Hanya Administrator yang berhak menghapus dokumen regulasi."}), 403

    safe_filename = nama_file.replace("/", "-").replace("\\", "-")
    filepath = FOLDER_PDF / safe_filename
    if filepath.exists() and filepath.is_file():
        filepath.unlink() 
        load_knowledge_base() 
        return jsonify({"message": f"Dokumen regulasi '{safe_filename}' berhasil dihapus!"}), 200
    return jsonify({"error": "File tidak ditemukan"}), 404

@app.get("/api/documents")
@app.get("/api/regulations")
def api_documents():
    if not FOLDER_PDF.is_dir(): 
        return jsonify({"documents": [], "jumlah": 0})
    daftar_pdf = sorted(file.name for file in FOLDER_PDF.iterdir() if file.is_file() and file.suffix.lower() == ".pdf")
    return jsonify({
        "documents": daftar_pdf,
        "jumlah": len(daftar_pdf)
    })

# ==========================================
# API PENGELOLAAN DOKUMEN PROCUREMENT (TERPISAH DARI REGULASI)
# ==========================================
@app.get("/api/procurement-documents")
def api_procurement_documents():
    if not FOLDER_PROCUREMENT.is_dir():
        return jsonify({"documents": [], "jumlah": 0})
    daftar_pdf = sorted(file.name for file in FOLDER_PROCUREMENT.iterdir() if file.is_file() and file.suffix.lower() == ".pdf")
    return jsonify({
        "documents": daftar_pdf,
        "jumlah": len(daftar_pdf)
    })

@app.post("/api/procurement-documents/upload")
def api_procurement_upload():
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Hanya Administrator yang berhak menambahkan dokumen procurement."}), 403

    if 'file' not in request.files:
        return jsonify({"error": "Tidak ada file yang dipilih"}), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "Nama file kosong"}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        safe_filename = file.filename.replace("/", "-").replace("\\", "-")
        filepath = FOLDER_PROCUREMENT / safe_filename
        file.save(filepath)
        return jsonify({"message": f"Dokumen procurement '{safe_filename}' berhasil diunggah!"}), 200
    return jsonify({"error": "Hanya menerima file berformat PDF (.pdf)."}), 400

@app.delete("/api/procurement-documents/<path:nama_file>")
def api_procurement_delete(nama_file):
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Hanya Administrator yang berhak menghapus dokumen procurement."}), 403

    safe_filename = nama_file.replace("/", "-").replace("\\", "-")
    filepath = FOLDER_PROCUREMENT / safe_filename
    if filepath.exists() and filepath.is_file():
        filepath.unlink()
        return jsonify({"message": f"Dokumen procurement '{safe_filename}' berhasil dihapus!"}), 200
    return jsonify({"error": "Dokumen tidak ditemukan"}), 404

# ==========================================
# HALAMAN WEBSITE & ROUTING LAINNYA
# ==========================================
@app.get("/")
def beranda(): return send_from_directory(BASE_DIR, "index.html")

@app.get("/<path:page>")
def serve_pages(page):
    if not page.endswith(".html"): return "Not Found", 404
    return send_from_directory(BASE_DIR, page)

@app.get("/index.html")
def dashboard(): return send_from_directory(BASE_DIR, "index.html")

@app.get("/procurement-template.html")
def procurementtemplate(): return send_from_directory(BASE_DIR, "procurement-template.html")

@app.get("/addendum-skd-panitia.html")
def addskdpanitia(): return send_from_directory(BASE_DIR, "addendum-skd-panitia.html")

@app.get("/addsurat-pembentukan-panitia.html")
def pembentukanpanitia(): return send_from_directory(BASE_DIR, "addsurat-pembentukan-panitia.html")

@app.get("/ba-pembukaan-dokumen.html")
def pembukaandokumen(): return send_from_directory(BASE_DIR, "ba-pembukaan-dokumen.html")

@app.get("/ba-serah-terima.html")
def serahterima(): return send_from_directory(BASE_DIR, "ba-serah-terima.html")

@app.get("/hps.html")
def hps(): return send_from_directory(BASE_DIR, "hps.html")

@app.get("/ikpp.html")
def ikpp(): return send_from_directory(BASE_DIR, "ikpp.html")

@app.get("/lhpp.html")
def lhpp(): return send_from_directory(BASE_DIR, "lhpp.html")

@app.get("/pakta-integritas.html")
def pakta(): return send_from_directory(BASE_DIR, "pakta-integritas.html")

@app.get("/pengumuman-hasil-pemilihan.html")
def hasilpemilihan(): return send_from_directory(BASE_DIR, "pengumuman-hasil-pemilihan.html")

@app.get("/skd-panitia.html")
def skdpanita(): return send_from_directory(BASE_DIR, "skd-panitia.html")

@app.get("/surat-panitia.html")
def suratpanita(): return send_from_directory(BASE_DIR, "surat-panitia.html")

@app.get("/procurement-document.html")
def procurementdocument(): return send_from_directory(BASE_DIR, "procurement-document.html")

@app.get("/regulation-finder.html")
def regulation_finder(): return send_from_directory(BASE_DIR, "regulation-finder.html")

@app.get("/manajemen-password.html")
def halaman_manajemen_password(): return send_from_directory(BASE_DIR, "manajemen-password.html")

@app.get("/js/<path:nama_file>")
def file_javascript(nama_file): return send_from_directory(BASE_DIR / "js", nama_file)

@app.get("/logo/<path:nama_file>")
def file_logo(nama_file): return send_from_directory(BASE_DIR / "logo", nama_file)

@app.get("/data regulation finder/<path:nama_file>")
def buka_pdf(nama_file): return send_from_directory(FOLDER_PDF, nama_file)

@app.get("/data procurement document/<path:nama_file>")
def buka_procurement_pdf(nama_file): return send_from_directory(FOLDER_PROCUREMENT, nama_file)

# ==========================================
# MENJALANKAN SERVER FLASK
# ==========================================
if __name__ == "__main__":
    print("=" * 45)
    print("SERVER REGULATION FINDER & HYBRID RAG")
    print("=" * 45)
    app.run(host="127.0.0.1", port=5000, debug=True)