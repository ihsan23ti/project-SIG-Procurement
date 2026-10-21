from pathlib import Path
import re
import unicodedata
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import pymupdf
from flask import Flask, jsonify, request, send_from_directory

# ==========================================
# PENGATURAN FOLDER
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
FOLDER_PDF = BASE_DIR / "data regulation finder"
FOLDER_PDF.mkdir(parents=True, exist_ok=True) # Pastikan folder otomatis ada

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
    c.execute("SELECT password FROM users WHERE username='admin'")
    user_admin = c.fetchone()
    if not user_admin:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', generate_password_hash('123')))
    else:
        # Pastikan password admin selalu ter-hash secara aman
        try:
            if not check_password_hash(user_admin[0], '123'):
                c.execute("UPDATE users SET password=? WHERE username='admin'", (generate_password_hash('123'),))
        except ValueError:
            # Jika sebelumnya tersimpan sebagai plain text '123'
            c.execute("UPDATE users SET password=? WHERE username='admin'", (generate_password_hash('123'),))
        
    conn.commit()
    conn.close()
    print("[DB] Database SQLite 'database.db' siap dan terhubung!")

init_db()

def is_admin(username):
    """Memeriksa apakah username yang diberikan memiliki role admin di database."""
    if not username:
        return False
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE LOWER(username)=LOWER(?)", (username,))
        row = c.fetchone()
        conn.close()
        return bool(row and row[0] == "admin")
    except Exception:
        return False

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username dan password wajib diisi."}), 400

    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'user')", (username, hashed_pw))
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
    c.execute("SELECT password, role, username FROM users WHERE LOWER(username)=LOWER(?)", (username,))
    user = c.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Username atau password salah!"}), 401

    db_password = user[0]
    db_role = user[1] if (len(user) > 1 and user[1]) else ("admin" if username.lower() == "admin" else "user")
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
# API MANAJEMEN PASSWORD & PENGGUNA (KHUSUS ROLE ADMIN)
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

    users = []
    for r in rows:
        role_val = r[2] if (len(r) > 2 and r[2]) else ("admin" if r[1].lower() == "admin" else "user")
        users.append({"id": r[0], "username": r[1], "role": role_val})

    return jsonify({"users": users})

@app.post("/api/admin/add-user")
def api_admin_add_user():
    """Menambahkan akun pengguna baru secara manual oleh admin dengan pilihan role."""
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
    """Mengedit username, role, dan/atau password pengguna (termasuk akun admin) oleh admin."""
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

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE id=?", (user_id,))
    target = c.fetchone()
    if not target:
        conn.close()
        return jsonify({"error": "Pengguna tidak ditemukan."}), 404

    old_username = target[1]
    old_role = target[2]

    # Validasi: jika akun yang diedit saat ini adalah admin dan role-nya diubah ke user biasa,
    # pastikan masih ada minimal 1 admin lain di sistem
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

        is_self = (old_username.lower() == admin_user.lower())
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

    hashed_pw = generate_password_hash(new_password)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE LOWER(username)=LOWER(?)", (target_username,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": f"Pengguna '{target_username}' tidak ditemukan."}), 404

    c.execute("UPDATE users SET password=? WHERE id=?", (hashed_pw, user[0]))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Password untuk '{target_username}' berhasil diubah dan diamankan dengan hash!"}), 200

@app.post("/api/admin/delete-user")
def api_admin_delete_user():
    """Menghapus akun pengguna tertentu (tidak bisa menghapus akun sendiri atau admin terakhir di sistem)."""
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    target_username = data.get("target_username", "").strip()

    if not is_admin(admin_user):
        return jsonify({"error": "Akses ditolak. Fitur ini hanya dapat diakses oleh role admin."}), 403

    if target_username.lower() == admin_user.lower():
        return jsonify({"error": "Anda tidak dapat menghapus akun Anda sendiri yang sedang aktif digunakan."}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, role FROM users WHERE LOWER(username)=LOWER(?)", (target_username,))
    target = c.fetchone()
    if not target:
        conn.close()
        return jsonify({"error": f"Pengguna '{target_username}' tidak ditemukan."}), 404

    target_id, target_role = target[0], target[1]
    if target_role == "admin":
        c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        admin_count = c.fetchone()[0]
        if admin_count <= 1:
            conn.close()
            return jsonify({"error": "Tidak dapat menghapus admin ini karena harus tersisa minimal 1 Administrator di sistem."}), 400

    c.execute("DELETE FROM users WHERE id=?", (target_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": f"Pengguna '{target_username}' berhasil dihapus!"}), 200


# ==========================================
# KONFIGURASI GEMINI AI & KNOWLEDGE BASE
# ==========================================
API_KEY = "AQ.Ab8RN6JRt0GJreirZW6gfBfJ6VaF856bd4k31oTjV2pqvwY18g"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')
KNOWLEDGE_BASE = ""

def load_knowledge_base():
    """Mengekstrak teks dari semua PDF dan menyuntikkannya ke otak AI."""
    global KNOWLEDGE_BASE
    KNOWLEDGE_BASE = "" # KOSONGKAN INGATAN LAMA AGAR BISA DI-UPDATE REAL-TIME
    
    if not FOLDER_PDF.is_dir():
        return
    
    print("\n[AI] Mengekstrak teks dari PDF untuk diserap AI...")
    daftar_pdf = sorted(file for file in FOLDER_PDF.iterdir() if file.is_file() and file.suffix.lower() == ".pdf")
    
    for file_pdf in daftar_pdf:
        try:
            with pymupdf.open(file_pdf) as dokumen:
                teks_dokumen = ""
                for halaman in dokumen:
                    teks_dokumen += halaman.get_text("text") + "\n"
                
                # Bersihkan spasi ganda agar rapi saat dibaca AI
                teks_dokumen = re.sub(r"\s+", " ", teks_dokumen).strip()
                KNOWLEDGE_BASE += f"\n\n--- DOKUMEN REFERENSI: {file_pdf.name} ---\n{teks_dokumen}"
        except Exception as e:
            print(f"[AI] Gagal membaca {file_pdf.name} untuk AI: {e}")
            
    print(f"[AI] Selesai! {len(daftar_pdf)} file PDF berhasil diserap. Chatbot AI siap digunakan.\n")

# Panggil fungsi ini agar AI menghafal PDF saat server Flask pertama kali menyala
load_knowledge_base()

# ==========================================
# API CHATBOT (RAG)
# ==========================================
@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    pertanyaan = data.get("pesan", "").strip()

    if not pertanyaan:
        return jsonify({"error": "Pesan tidak boleh kosong"}), 400

    prompt = f"""
Kamu adalah Asisten AI profesional untuk Portal Pengadaan PT Semen Indonesia (Persero) Tbk (SIG).
Tugasmu adalah menjawab pertanyaan pengguna HANYA berdasarkan isi dokumen pengadaan berikut ini.
Gunakan bahasa Indonesia yang ramah, sopan, jelas, dan profesional.
Jika kamu mengutip aturan, sebutkan dari mana nama "DOKUMEN REFERENSI" tersebut berasal.
Jika jawaban tidak ada di dalam dokumen referensi, katakan dengan sopan bahwa informasi tersebut tidak tersedia di pedoman pengadaan.

ISI DOKUMEN PENGADAAN SIG (JADIKAN INI SUMBER KEBENARAN MUTLAK):
{KNOWLEDGE_BASE}

Pertanyaan Pengguna: "{pertanyaan}"
"""
    try:
        response = model.generate_content(prompt)
        return jsonify({"jawaban": response.text})
    except Exception as e:
        app.logger.exception("Gagal memanggil Gemini API")
        return jsonify({"error": f"Server AI error: {str(e)}"}), 500

# ==========================================
# API PENGELOLAAN DOKUMEN (UPLOAD & DELETE)
# ==========================================
@app.post("/api/upload")
def api_upload():
    if 'file' not in request.files:
        return jsonify({"error": "Tidak ada file"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nama file kosong"}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        safe_filename = file.filename.replace("/", "-").replace("\\", "-")
        filepath = FOLDER_PDF / safe_filename
        file.save(filepath)
        
        # SINKRONISASI AI: Langsung suruh AI baca PDF baru tanpa perlu restart server!
        load_knowledge_base()
        return jsonify({"message": "Berhasil upload dan AI telah mempelajarinya!"}), 200
    return jsonify({"error": "Hanya menerima PDF."}), 400

@app.delete("/api/documents/<path:nama_file>")
def api_delete(nama_file):
    safe_filename = nama_file.replace("/", "-").replace("\\", "-")
    filepath = FOLDER_PDF / safe_filename
    if filepath.exists() and filepath.is_file():
        filepath.unlink() # Hapus file fisik
        
        # SINKRONISASI AI: Langsung hapus file dari ingatan AI!
        load_knowledge_base()
        return jsonify({"message": "Dihapus"}), 200
    return jsonify({"error": "File tidak ditemukan"}), 404

# ==========================================
# NORMALISASI & PEMBERSIHAN TEKS
# ==========================================
def bersihkan_teks(teks):
    """Membersihkan teks PDF dengan tetap mempertahankan huruf besar/kecil asli."""
    # Sambungkan kata yang terpenggal tanda hubung dan baris baru di PDF (contoh: penga-\n daan -> pengadaan)
    teks = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", teks)
    teks = unicodedata.normalize("NFKC", teks)
    teks = teks.replace("\u00ad", "")
    teks = teks.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", teks).strip()

def normalisasi_teks(teks):
    """Membersihkan teks dan mengubah menjadi huruf kecil untuk pencarian."""
    return bersihkan_teks(teks).casefold()

def ekstrak_cuplikan(teks_asli, teks_cari, kata_cari, panjang_sebelum=750, panjang_sesudah=1100):
    """Mengekstrak cuplikan/ringkasan yang jauh lebih panjang, utuh, dan rapi dari teks halaman PDF."""
    posisi = teks_cari.find(kata_cari)
    if posisi == -1:
        return ""

    panjang_kata = len(kata_cari)
    awal = max(0, posisi - panjang_sebelum)
    akhir = min(len(teks_asli), posisi + panjang_kata + panjang_sesudah)

    # Rapikan batas awal ke spasi terdekat agar tidak memenggal kata di tengah
    if awal > 0:
        spasi_awal = teks_asli.find(" ", awal)
        if spasi_awal != -1 and spasi_awal < posisi:
            awal = spasi_awal + 1

    # Rapikan batas akhir ke spasi terdekat agar tidak memenggal kata di tengah
    if akhir < len(teks_asli):
        spasi_akhir = teks_asli.rfind(" ", posisi + panjang_kata, akhir)
        if spasi_akhir != -1 and spasi_akhir > posisi + panjang_kata:
            akhir = spasi_akhir

    cuplikan = teks_asli[awal:akhir].strip()

    if awal > 0:
        cuplikan = "... " + cuplikan
    if akhir < len(teks_asli):
        cuplikan = cuplikan + " ..."

    return cuplikan

# ==========================================
# MENCARI KATA / KALIMAT DALAM SELURUH PDF
# ==========================================
def cari_kata(kata):
    hasil = []
    kata = kata.strip()
    if not kata:
        return hasil

    kata_normal = normalisasi_teks(kata)
    if not FOLDER_PDF.is_dir():
        app.logger.error("Folder PDF tidak ditemukan: %s", FOLDER_PDF)
        return hasil

    daftar_pdf = sorted(file for file in FOLDER_PDF.iterdir() if file.is_file() and file.suffix.lower() == ".pdf")

    for file_pdf in daftar_pdf:
        try:
            with pymupdf.open(file_pdf) as dokumen:
                for nomor_halaman, halaman in enumerate(dokumen, start=1):
                    teks = halaman.get_text("text")
                    if not teks.strip():
                        continue

                    teks_asli = bersihkan_teks(teks)
                    teks_cari = teks_asli.casefold()

                    if kata_normal not in teks_cari:
                        continue

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
    return send_from_directory(BASE_DIR, "procurement-template.html")

@app.get("/addendum-skd-panitia.html")
def addskdpanitia():
    return send_from_directory(BASE_DIR, "addendum-skd-panitia.html")

@app.get("/addsurat-pembentukan-panitia.html")
def pembentukanpanitia():
    return send_from_directory(BASE_DIR, "addsurat-pembentukan-panitia.html")

@app.get("/ba-pembukaan-dokumen.html")
def pembukaandokumen():
    return send_from_directory(BASE_DIR, "ba-pembukaan-dokumen.html")

@app.get("/ba-serah-terima.html")
def serahterima():
    return send_from_directory(BASE_DIR, "ba-serah-terima.html")

@app.get("/hps.html")
def hps():
    return send_from_directory(BASE_DIR, "hps.html")

@app.get("/ikpp.html")
def ikpp():
    return send_from_directory(BASE_DIR, "ikpp.html")

@app.get("/lhpp.html")
def lhpp():
    return send_from_directory(BASE_DIR, "lhpp.html")

@app.get("/pakta-integritas.html")
def pakta():
    return send_from_directory(BASE_DIR, "pakta-integritas.html")

@app.get("/pengumuman-hasil-pemilihan.html")
def hasilpemilihan():
    return send_from_directory(BASE_DIR, "pengumuman-hasil-pemilihan.html")

@app.get("/skd-panitia.html")
def skdpanita():
    return send_from_directory(BASE_DIR, "skd-panitia.html")

@app.get("/surat-panitia.html")
def suratpanita():
    return send_from_directory(BASE_DIR, "surat-panitia.html")

@app.get("/procurement-document.html")
def procurementdocument():
    return send_from_directory(BASE_DIR, "procurement-document.html")

@app.get("/regulation-finder.html")
def regulation_finder():
    return send_from_directory(BASE_DIR, "regulation-finder.html")

@app.get("/manajemen-password.html")
def halaman_manajemen_password():
    return send_from_directory(BASE_DIR, "manajemen-password.html")

# ==========================================
# FILE JAVASCRIPT & LOGO
# ==========================================
@app.get("/js/<path:nama_file>")
def file_javascript(nama_file):
    return send_from_directory(BASE_DIR / "js", nama_file)

@app.get("/logo/<path:nama_file>")
def file_logo(nama_file):
    return send_from_directory(BASE_DIR / "logo", nama_file)

@app.get("/data regulation finder/<path:nama_file>")
def buka_pdf(nama_file):
    return send_from_directory(FOLDER_PDF, nama_file)

# ==========================================
# API DAFTAR SEMUA DOKUMEN & PENCARIAN
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
        jumlah_pdf = sum(1 for file in FOLDER_PDF.iterdir() if file.is_file() and file.suffix.lower() == ".pdf")
        print("Jumlah file PDF:", jumlah_pdf)

    app.run(host="127.0.0.1", port=5000, debug=True)