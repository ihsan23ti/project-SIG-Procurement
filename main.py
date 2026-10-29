from pathlib import Path
import re
import unicodedata
import os
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import pymupdf
from flask import Flask, jsonify, request, send_from_directory, redirect
from supabase import create_client, Client

# --- LIBRARY MACHINE LEARNING LOKAL (TF-IDF) ---
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from dotenv import load_dotenv

# Muat variabel dari file .env untuk penggunaan lokal
#load_dotenv()

# ==========================================
# PENGATURAN FLASK & SUPABASE
# ==========================================
BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)

# Mengambil kredensial dari Environment Variables Vercel
SUPABASE_URL = os.environ.get("SUPABASE_URL", "ANTI_DENGAGN_URL_SUPABASE_KAMU_JIKA_LOKAL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "GANTI_DENGAN_KEY_SUPABASE_KAMU_JIKA_LOKAL")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Nama Bucket Storage di Supabase
BUCKET_NAME = "data-procurement"

# ==========================================
# DATABASE SUPABASE (SISTEM LOGIN)
# ==========================================
def is_admin(username):
    """Memeriksa apakah username yang diberikan memiliki role admin di Supabase."""
    if not username: return False
    try:
        res = supabase.table("users").select("role").ilike("username", username.strip()).execute()
        if res.data and res.data[0].get("role", "").strip().lower() in ["admin", "administrator"]:
            return True
        # Cek apakah dia akun ID 1 (Admin Utama)
        res_main = supabase.table("users").select("username, role").eq("id", 1).execute()
        if res_main.data:
            main_user = res_main.data[0]
            if main_user.get("username", "").strip().lower() == username.strip().lower() and \
               main_user.get("role", "").strip().lower() in ["admin", "administrator"]:
                return True
        return False
    except Exception:
        return False

def is_main_admin_user(username):
    """Memeriksa apakah username yang diberikan adalah akun Admin Utama (ID == 1)."""
    if not username: return False
    try:
        res = supabase.table("users").select("username").eq("id", 1).execute()
        if res.data and res.data[0].get("username", "").strip().lower() == username.strip().lower():
            return True
        return False
    except Exception:
        return False

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = "user"

    if not username or not password:
        return jsonify({"error": "Username dan password wajib diisi."}), 400
    if len(password) < 4:
        return jsonify({"error": "Password minimal 4 karakter."}), 400

    try:
        # Cek duplikasi
        cek = supabase.table("users").select("id").ilike("username", username).execute()
        if cek.data:
            return jsonify({"error": f"Username '{username}' sudah terdaftar. Silakan pilih username lain."}), 400

        hashed_pw = generate_password_hash(password)
        supabase.table("users").insert({"username": username, "password": hashed_pw, "role": role}).execute()

        return jsonify({"message": f"Akun '{username}' berhasil didaftarkan!", "username": username, "role": role}), 200
    except Exception as e:
        return jsonify({"error": f"Gagal mendaftarkan akun: {str(e)}"}), 500

@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    try:
        res = supabase.table("users").select("*").ilike("username", username).execute()
        if not res.data:
            return jsonify({"error": "Username atau password salah!"}), 401
        
        user = res.data[0]
        db_password = user.get("password")
        db_role = user.get("role", "user")
        canonical_username = user.get("username")

        is_valid = False
        try:
            is_valid = check_password_hash(db_password, password)
        except ValueError:
            is_valid = (db_password == password)

        if is_valid:
            if db_password == password:
                supabase.table("users").update({"password": generate_password_hash(password)}).eq("id", user["id"]).execute()
            
            return jsonify({"message": "Login berhasil!", "username": canonical_username, "role": db_role}), 200
        else:
            return jsonify({"error": "Username atau password salah!"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# API PROFIL PENGGUNA & GANTI PASSWORD MANDIRI
# ==========================================
@app.post("/api/user/change-password")
def api_user_change_password():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    old_password = data.get("old_password", "").strip()
    new_password = data.get("new_password", "").strip()

    if not username or not old_password or not new_password:
        return jsonify({"error": "Semua kolom password wajib diisi."}), 400
    if len(new_password) < 4:
        return jsonify({"error": "Password baru minimal 4 karakter."}), 400
    if old_password == new_password:
        return jsonify({"error": "Password baru tidak boleh sama dengan password saat ini."}), 400

    try:
        res = supabase.table("users").select("id, password, username").ilike("username", username).execute()
        if not res.data:
            return jsonify({"error": f"Pengguna '{username}' tidak ditemukan."}), 404
        
        user = res.data[0]
        try:
            is_valid = check_password_hash(user["password"], old_password)
        except ValueError:
            is_valid = (user["password"] == old_password)

        if not is_valid:
            return jsonify({"error": "Password saat ini (lama) tidak sesuai!"}), 400

        hashed_pw = generate_password_hash(new_password)
        supabase.table("users").update({"password": hashed_pw}).eq("id", user["id"]).execute()

        return jsonify({"message": f"Password untuk akun '{user['username']}' berhasil diubah!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/user/profile")
def api_user_profile():
    username = (request.args.get("username", "") or request.headers.get("X-User", "")).strip()
    if not username: return jsonify({"error": "Username wajib diisi."}), 400

    res = supabase.table("users").select("id, username, role").ilike("username", username).execute()
    if not res.data: return jsonify({"error": "Pengguna tidak ditemukan."}), 404

    row = res.data[0]
    return jsonify({
        "id": row["id"],
        "username": row["username"],
        "role": row.get("role", "user"),
        "is_main_admin": bool(row["id"] == 1)
    }), 200

# ==========================================
# API MANAJEMEN PENGGUNA (ROLE ADMIN)
# ==========================================
@app.get("/api/admin/users")
def api_admin_get_users():
    admin_user = (request.headers.get("X-Admin-User", "") or request.args.get("admin", "")).strip()
    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403

    res = supabase.table("users").select("id, username, role").order("id").execute()
    caller_is_main = is_main_admin_user(admin_user)

    users = []
    for r in res.data:
        users.append({
            "id": r["id"],
            "username": r["username"],
            "role": r.get("role", "user"),
            "is_main_admin": bool(r["id"] == 1)
        })

    return jsonify({"users": users, "caller_is_main_admin": caller_is_main})

@app.post("/api/admin/add-user")
def api_admin_add_user():
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user").strip().lower()

    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403
    if not username or not password: return jsonify({"error": "Wajib diisi."}), 400
    if role not in ["admin", "user"]: role = "user"

    try:
        cek = supabase.table("users").select("id").ilike("username", username).execute()
        if cek.data: return jsonify({"error": "Username sudah terdaftar."}), 400

        supabase.table("users").insert({"username": username, "password": generate_password_hash(password), "role": role}).execute()
        return jsonify({"message": f"Pengguna '{username}' berhasil ditambahkan!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/admin/edit-user")
def api_admin_edit_user():
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    user_id = data.get("user_id")
    new_username = data.get("new_username", "").strip()
    new_password = data.get("new_password", "").strip()
    new_role = data.get("new_role", "user").strip().lower()

    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403
    if not user_id or not new_username: return jsonify({"error": "ID dan username wajib diisi."}), 400
    if new_role not in ["admin", "user"]: new_role = "user"

    target_id_int = int(user_id)
    is_caller_main = is_main_admin_user(admin_user)

    if target_id_int == 1 and not is_caller_main:
        return jsonify({"error": "Admin biasa tidak berhak mengubah akun Admin Utama."}), 403

    res = supabase.table("users").select("*").eq("id", target_id_int).execute()
    if not res.data: return jsonify({"error": "Pengguna tidak ditemukan."}), 404
    
    target = res.data[0]
    old_role = target.get("role", "user")
    if target_id_int == 1: new_role = "admin"

    if old_role == "admin" and new_role != "admin":
        res_admins = supabase.table("users").select("id", count="exact").eq("role", "admin").neq("id", target_id_int).execute()
        if res_admins.count == 0:
            return jsonify({"error": "Harus ada minimal 1 Administrator di sistem."}), 400

    try:
        update_data = {"username": new_username, "role": new_role}
        if new_password:
            update_data["password"] = generate_password_hash(new_password)
            
        supabase.table("users").update(update_data).eq("id", target_id_int).execute()
        return jsonify({"message": f"Data akun '{new_username}' berhasil diperbarui!"}), 200
    except Exception as e:
        return jsonify({"error": "Username mungkin sudah dipakai."}), 400

@app.post("/api/admin/change-password")
def api_admin_change_password():
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    target_username = data.get("target_username", "").strip()
    new_password = data.get("new_password", "").strip()

    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403
    
    res = supabase.table("users").select("*").ilike("username", target_username).execute()
    if not res.data: return jsonify({"error": "Pengguna tidak ditemukan."}), 404
    
    target = res.data[0]
    is_caller_main = is_main_admin_user(admin_user)
    is_self = (target["username"].strip().lower() == admin_user.strip().lower())

    if target["id"] == 1 and not is_caller_main:
        return jsonify({"error": "Admin biasa tidak berhak mengubah password Admin Utama."}), 403
    if target.get("role") == "admin" and target["id"] != 1 and not is_caller_main and not is_self:
        return jsonify({"error": "Hanya Admin Utama yang berhak mereset password Administrator lain."}), 403

    supabase.table("users").update({"password": generate_password_hash(new_password)}).eq("id", target["id"]).execute()
    return jsonify({"message": f"Password untuk '{target['username']}' berhasil diubah!"}), 200

@app.post("/api/admin/delete-user")
def api_admin_delete_user():
    data = request.get_json(silent=True) or {}
    admin_user = (data.get("admin_user", "") or request.headers.get("X-Admin-User", "")).strip()
    target_id = data.get("target_id")
    target_username = data.get("target_username", "").strip()

    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403

    if target_id:
        res = supabase.table("users").select("*").eq("id", target_id).execute()
    else:
        res = supabase.table("users").select("*").ilike("username", target_username).execute()
        
    if not res.data: return jsonify({"error": "Akun tidak ditemukan."}), 404
    target = res.data[0]
    
    if target["id"] == 1: return jsonify({"error": "Akun Admin Utama tidak dapat dihapus."}), 400
    if target["username"].strip().lower() == admin_user.strip().lower():
        return jsonify({"error": "Anda tidak dapat menghapus akun Anda sendiri."}), 400

    is_target_admin = bool(target.get("role", "") in ["admin", "administrator"])
    is_caller_main = is_main_admin_user(admin_user)

    if is_target_admin and not is_caller_main:
        return jsonify({"error": "Hanya Admin Utama yang berhak menghapus akun Administrator."}), 403
    if is_target_admin:
        res_admins = supabase.table("users").select("id", count="exact").eq("role", "admin").execute()
        if res_admins.count <= 1:
            return jsonify({"error": "Harus tersisa minimal 1 Administrator di sistem."}), 400

    supabase.table("users").delete().eq("id", target["id"]).execute()
    return jsonify({"message": f"Akun '{target['username']}' berhasil dihapus!"}), 200

# ==========================================
# KONFIGURASI GEMINI AI & TF-IDF RAG (VIA SUPABASE STORAGE)
# ==========================================
API_KEY = "AQ.Ab8RN6JRt0GJreirZW6gfBfJ6VaF856bd4k31oTjV2pqvwY18g"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')

MEMORY_DOKUMEN = []
vectorizer = TfidfVectorizer()
tfidf_matrix = None

def bersihkan_teks(teks):
    teks = re.sub(r"(\w+)-\s*\s*(\w+)", r"  ", teks)
    teks = unicodedata.normalize("NFKC", teks)
    teks = teks.replace("颅", "").replace("聽", " ")
    return re.sub(r"\s+", " ", teks).strip()

def normalisasi_teks(teks):
    return bersihkan_teks(teks).casefold()

def chunk_text(teks, chunk_size=800, overlap=150):
    chunks = []
    start = 0
    teks_len = len(teks)
    while start < teks_len:
        end = start + chunk_size
        chunks.append(teks[start:end])
        start += chunk_size - overlap
    return chunks

def load_knowledge_base():
    """Mengunduh PDF dari Supabase Storage ke memori untuk melatih TF-IDF."""
    global MEMORY_DOKUMEN, vectorizer, tfidf_matrix
    MEMORY_DOKUMEN = []
    
    print("\n[ML] Membaca PDF dari Supabase Storage dan melatih model TF-IDF...")
    try:
        files = supabase.storage.from_(BUCKET_NAME).list("regulasi")
    except Exception as e:
        print(f"[ML] Gagal akses Supabase Storage: {e}")
        return

    for f in files:
        file_name = f.get('name')
        if not file_name or not file_name.lower().endswith(".pdf"): continue
        
        try:
            res = supabase.storage.from_(BUCKET_NAME).download(f"regulasi/{file_name}")
            with pymupdf.open(stream=res, filetype="pdf") as dokumen:
                for nomor_halaman, halaman in enumerate(dokumen, start=1):
                    teks_asli = bersihkan_teks(halaman.get_text("text"))
                    if len(teks_asli) > 50:
                        potongan = chunk_text(teks_asli)
                        for p in potongan:
                            MEMORY_DOKUMEN.append({
                                "file": file_name,
                                "halaman": nomor_halaman,
                                "teks": p
                            })
        except Exception as e:
            print(f"[ML] Gagal memproses {file_name}: {e}")

    if MEMORY_DOKUMEN:
        tfidf_matrix = vectorizer.fit_transform([doc["teks"] for doc in MEMORY_DOKUMEN])
        print(f"[ML] Selesai! Model TF-IDF dilatih dengan {len(MEMORY_DOKUMEN)} potongan paragraf.\n")

# Load saat server pertama kali menyala (DIBUAT NONAKTIF AGAR TIDAK TIMEOUT DI VERCEL)
# load_knowledge_base()

@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    pertanyaan = data.get("pesan", "").strip()

    if not pertanyaan: return jsonify({"error": "Pesan tidak boleh kosong"}), 400
    
    # === PERUBAHAN BARU: Memuat model AI di dalam route, hanya ketika diperlukan ===
    if tfidf_matrix is None or len(MEMORY_DOKUMEN) == 0: 
        load_knowledge_base()
        
        if tfidf_matrix is None or len(MEMORY_DOKUMEN) == 0:
            return jsonify({"error": "Database dokumen kosong. Upload PDF dulu."}), 400
    # ===============================================================================

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
        return jsonify({"error": f"Server AI error: {str(e)}"}), 500

# ==========================================
# PENCARIAN EXACT-MATCH (REGULATION FINDER)
# ==========================================
def ekstrak_cuplikan(teks_asli, teks_cari, kata_cari, panjang_sebelum=750, panjang_sesudah=1100):
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
    if awal > 0: cuplikan = "... " + cuplikan
    if akhir < len(teks_asli): cuplikan = cuplikan + " ..."
    return cuplikan

def cari_kata(kata):
    hasil = []
    kata_normal = normalisasi_teks(kata)
    
    try:
        files = supabase.storage.from_(BUCKET_NAME).list("regulasi")
    except:
        return hasil

    for f in files:
        file_name = f.get('name')
        if not file_name or not file_name.lower().endswith(".pdf"): continue
        try:
            res = supabase.storage.from_(BUCKET_NAME).download(f"regulasi/{file_name}")
            with pymupdf.open(stream=res, filetype="pdf") as dokumen:
                for nomor_halaman, halaman in enumerate(dokumen, start=1):
                    teks = halaman.get_text("text")
                    if not teks.strip(): continue
                    teks_asli = bersihkan_teks(teks)
                    teks_cari = teks_asli.casefold()

                    if kata_normal in teks_cari:
                        cuplikan = ekstrak_cuplikan(teks_asli, teks_cari, kata_normal)
                        hasil.append({"file": file_name, "halaman": nomor_halaman, "cuplikan": cuplikan})
        except Exception:
            pass
    return hasil

@app.post("/api/search")
def api_search():
    data = request.get_json(silent=True) or {}
    kata = data.get("kata", "").strip()

    if not kata: return jsonify({"kata": "", "jumlah": 0, "hasil": []})
    if len(kata) > 1000: return jsonify({"error": "Pencarian maksimal 1000 karakter."}), 400

    hasil = cari_kata(kata)
    return jsonify({"kata": kata, "jumlah": len(hasil), "hasil": hasil})

# ==========================================
# PENGELOLAAN UPLOAD & DOKUMEN REGULASI
# ==========================================
def get_auth_admin_user():
    user = (request.headers.get("X-Admin-User", "") or request.form.get("admin_user", "") or request.args.get("admin_user", "")).strip()
    if not user and request.is_json:
        user = (request.get_json(silent=True) or {}).get("admin_user", "").strip()
    return user

@app.post("/api/upload")
@app.post("/api/regulations/upload")
def api_upload():
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403

    if 'file' not in request.files: return jsonify({"error": "Tidak ada file"}), 400
    file = request.files['file']
    
    if file and file.filename.lower().endswith('.pdf'):
        safe_filename = file.filename.replace("/", "-").replace("\\", "-")
        supabase.storage.from_(BUCKET_NAME).upload(
            path=f"regulasi/{safe_filename}",
            file=file.read(),
            file_options={"content-type": "application/pdf"}
        )
        # Hapus memori lama agar data diperbarui pada request selanjutnya
        global tfidf_matrix, MEMORY_DOKUMEN
        tfidf_matrix = None
        MEMORY_DOKUMEN = []
        return jsonify({"message": f"Dokumen '{safe_filename}' berhasil diunggah ke Cloud!"}), 200
    return jsonify({"error": "Hanya menerima PDF."}), 400

@app.delete("/api/documents/<path:nama_file>")
@app.delete("/api/regulations/<path:nama_file>")
def api_delete(nama_file):
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403

    safe_filename = nama_file.replace("/", "-").replace("\\", "-")
    supabase.storage.from_(BUCKET_NAME).remove([f"regulasi/{safe_filename}"])
    
    # Hapus memori lama agar data diperbarui pada request selanjutnya
    global tfidf_matrix, MEMORY_DOKUMEN
    tfidf_matrix = None
    MEMORY_DOKUMEN = []
    return jsonify({"message": f"Dokumen '{safe_filename}' berhasil dihapus!"}), 200

@app.get("/api/documents")
@app.get("/api/regulations")
def api_documents():
    try:
        files = supabase.storage.from_(BUCKET_NAME).list("regulasi")
        daftar_pdf = sorted([f['name'] for f in files if f.get('name') and f['name'].endswith('.pdf')])
        return jsonify({"documents": daftar_pdf, "jumlah": len(daftar_pdf)})
    except Exception:
        return jsonify({"documents": [], "jumlah": 0})

# ==========================================
# PENGELOLAAN DOKUMEN PROCUREMENT
# ==========================================
@app.get("/api/procurement-documents")
def api_procurement_documents():
    try:
        files = supabase.storage.from_(BUCKET_NAME).list("procurement")
        daftar_pdf = sorted([f['name'] for f in files if f.get('name') and f['name'].endswith('.pdf')])
        return jsonify({"documents": daftar_pdf, "jumlah": len(daftar_pdf)})
    except:
        return jsonify({"documents": [], "jumlah": 0})

@app.post("/api/procurement-documents/upload")
def api_procurement_upload():
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403

    if 'file' not in request.files: return jsonify({"error": "Tidak ada file"}), 400
    file = request.files['file']
    
    if file and file.filename.lower().endswith('.pdf'):
        safe_filename = file.filename.replace("/", "-").replace("\\", "-")
        supabase.storage.from_(BUCKET_NAME).upload(
            path=f"procurement/{safe_filename}",
            file=file.read(),
            file_options={"content-type": "application/pdf"}
        )
        return jsonify({"message": f"Dokumen '{safe_filename}' berhasil diunggah ke Cloud!"}), 200
    return jsonify({"error": "Hanya menerima PDF."}), 400

@app.delete("/api/procurement-documents/<path:nama_file>")
def api_procurement_delete(nama_file):
    admin_user = get_auth_admin_user()
    if not is_admin(admin_user): return jsonify({"error": "Akses ditolak."}), 403

    safe_filename = nama_file.replace("/", "-").replace("\\", "-")
    supabase.storage.from_(BUCKET_NAME).remove([f"procurement/{safe_filename}"])
    return jsonify({"message": f"Dokumen '{safe_filename}' berhasil dihapus!"}), 200

# ==========================================
# SERVING FILES (HTML, JS, LOGO & PDF URL)
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

# Redirect untuk membaca PDF langsung dari Cloud Storage Supabase
@app.get("/data regulation finder/<path:nama_file>")
def buka_pdf(nama_file):
    url = supabase.storage.from_(BUCKET_NAME).get_public_url(f"regulasi/{nama_file}")
    return redirect(url)

@app.get("/data procurement document/<path:nama_file>")
def buka_procurement_pdf(nama_file):
    url = supabase.storage.from_(BUCKET_NAME).get_public_url(f"procurement/{nama_file}")
    return redirect(url)

# ==========================================
# MENJALANKAN SERVER FLASK
# ==========================================
if __name__ == "__main__":
    print("=" * 45)
    print("SERVER BERJALAN MENGGUNAKAN SUPABASE")
    print("=" * 45)
    app.run(host="127.0.0.1", port=5000, debug=True)