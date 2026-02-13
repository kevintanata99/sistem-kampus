from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
# Impor alat pengecek password
from werkzeug.security import check_password_hash 
from werkzeug.security import generate_password_hash
import os 
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'rahasia_kampus_binjai_2026' # Kunci buat tiket sesi

# --- KONFIGURASI UPLOAD ---
# Tentukan folder penyimpanan (static/uploads)
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads') 
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


# ---KONEKSI DATABASE---
# Pastikan sudah import os dan psycopg2
def get_db_connection():
    # Apakah ada alamat database dari Cloud?
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        # 1: Sedang di Cloud
        conn = psycopg2.connect(db_url)
    else:
        # 2: Sedang Pakai Localhost
        conn = psycopg2.connect(
            host="localhost",
            database="postgres",
            user="postgres",
            password="12345", # password aman kalau untuk local
            port="5432"
        )
    return conn

# --- RUTE LOGIN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # A. Tangkap inputan user
        username_input = request.form['username']
        password_input = request.form['password']
        
        # B. Cari user di database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users_kampus WHERE username = %s", (username_input,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        # C. PROSES VERIFIKASI (Jantungnya Sistem Login)
        if user:
            # user[2] adalah password hash dari database
            password_hash_db = user[2] 
            
            # Cek: Apakah 'password_input' cocok dengan 'hash' di database?
            if check_password_hash(password_hash_db, password_input):
                
                # KALAU COCOK: Simpan data penting di Sesi (Gelang Konser)
                session['sudah_login'] = True
                session['username'] = user[1]  # <--- TAMBAHAN PENTING! (Simpan username: mhs1)
                session['nama'] = user[3] # Nama Lengkap
                session['role'] = user[4] # Role (admin/dosen/mahasiswa)
                session['foto'] = user[5]  # <--- TAMBAHAN BARU (Simpan nama file foto)
                # D. LOGIKA ROLE (Lampu Merah)
                # Arahkan ke halaman sesuai jabatannya
                if session['role'] == 'admin':
                    return redirect(url_for('dashboard_admin'))
                elif session['role'] == 'dosen':
                    return redirect(url_for('dashboard_dosen'))
                elif session['role'] == 'mahasiswa':
                    return redirect(url_for('dashboard_mahasiswa'))
            
            else:
                # Password salah (tapi usernamenya ketemu)
                return "Password Salah! Coba ingat-ingat lagi."
        else:
            # Username tidak ditemukan
            return "Username tidak terdaftar!"

    # Kalau metode GET (baru buka), tampilkan file login
    return render_template('login.html')

# --- RUTE LOGOUT ---
@app.route('/logout')
def logout():
    session.clear() # Hapus semua sesi
    return redirect(url_for('login'))

# --- RUTE SEMENTARA (Biar gak error kalau redirect) ---
# Nanti kita bikin file HTML-nya terpisah
@app.route('/admin')
def dashboard_admin():
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    # 1. Ambil kata kunci dari URL (misal: /admin?search=leon)
    kata_kunci = request.args.get('search')

    conn = get_db_connection()
    cur = conn.cursor()

    if kata_kunci:
        # 2. Jika ada kata kunci, cari yang mirip (nama_lengkap atau username)
        query = """
            SELECT * FROM users_kampus 
            WHERE nama_lengkap ILIKE %s OR username ILIKE %s
            ORDER BY role ASC
        """
        # Kita bungkus kata kunci dengan tanda %
        search_term = f"%{kata_kunci}%"
        cur.execute(query, (search_term, search_term))
    else:
        # 3. Jika tidak ada pencarian, tampilkan semua seperti biasa
        cur.execute("SELECT * FROM users_kampus ORDER BY role ASC")
    
    users = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('dashboard_admin.html', data_users=users)


# Fungsi Cek File (Hanya boleh gambar)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- RUTE DASHBOARD DOSEN ---
@app.route('/dosen')
def dashboard_dosen():
    # 1. CEK SATPAM: Apakah dia login? Apakah dia Dosen?
    if 'sudah_login' not in session or session['role'] != 'dosen':
        # Kalau bukan dosen, tendang balik ke halaman login/home
        return redirect(url_for('login'))

    # 2. Tampilkan HTML Dosen
    return render_template('dashboard_dosen.html')


# --- RUTE DASHBOARD MAHASISWA ---
@app.route('/mahasiswa')
def dashboard_mahasiswa():
    # 1. CEK SATPAM
    if 'sudah_login' not in session or session['role'] != 'mahasiswa':
        return redirect(url_for('login'))

    # 2. AMBIL DATA NILAI DARI DATABASE (Spesifik punya dia aja)
    siapa_yang_login = session['username'] # Ambil 'mhs1' dari sesi
    
    conn = get_db_connection()
    cur = conn.cursor()
    # Cari nilai WHERE username_mhs = 'mhs1'
    cur.execute("SELECT * FROM nilai WHERE username_mhs = %s", (siapa_yang_login,))
    transkrip = cur.fetchall()
    cur.close()
    conn.close()

    # 3. Kirim data 'transkrip' ke HTML
    return render_template('dashboard_mahasiswa.html', data_nilai=transkrip)

# --- PROSES SIMPAN NILAI (DARI DOSEN) ---
@app.route('/proses_nilai', methods=['POST'])
def proses_nilai():
    # 1. Cek Keamanan (Wajib Dosen!)
    if 'sudah_login' not in session or session['role'] != 'dosen':
        return redirect(url_for('login'))

    # 2. Tangkap Data dari Form HTML
    mhs_target = request.form['username_mhs']
    matkul = request.form['matkul']
    sks = request.form['sks']
    nilai = request.form['nilai']
    dosen_pengampu = session['nama'] # Ambil nama dosen yg lagi login otomatis

    # 3. Simpan ke Database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO nilai (username_mhs, mata_kuliah, sks, nilai_huruf, dosen_pengampu)
        VALUES (%s, %s, %s, %s, %s)
    """, (mhs_target, matkul, sks, nilai, dosen_pengampu))
    
    conn.commit() # Jangan lupa commit kalau INSERT/UPDATE
    cur.close()
    conn.close()

    # 4. Balik lagi ke dashboard dosen (kasih pesan sukses dikit boleh)
    return redirect(url_for('dashboard_dosen'))

@app.route('/admin/tambah_user', methods=['GET'])
def halaman_tambah_user():
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    return render_template('tambah_user.html')

# --- RUTE PROSES SIMPAN USER BARU ---
@app.route('/admin/tambah_user', methods=['POST'])
def proses_tambah_user():
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    # 1. Ambil data dari form
    username = request.form['username']
    password_polos = request.form['password']
    nama_lengkap = request.form['nama_lengkap']
    role = request.form['role']

    # 2. HASH PASSWORD (Wajib demi keamanan!)
    password_acak = generate_password_hash(password_polos)

    # 3. Simpan ke Database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users_kampus (username, password, nama_lengkap, role)
            VALUES (%s, %s, %s, %s)
        """, (username, password_acak, nama_lengkap, role))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('dashboard_admin'))
    except Exception as e:
        return f"Gagal menambah user: {e} (Mungkin username sudah ada)"

# --- RUTE HAPUS USER ---
@app.route('/admin/hapus/<int:user_id>')
def hapus_user(user_id):
    # 1. Cek Keamanan (Cuma Admin yang boleh hapus)
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # 2. HAPUS DATA (User Kampus)
    # Hati-hati! Kalau user ini mahasiswa, nilainya juga harus dihapus gak?
    # Untuk sekarang kita hapus user-nya aja dulu.
    cur.execute("DELETE FROM users_kampus WHERE id = %s", (user_id,))
    
    conn.commit()
    cur.close()
    conn.close()

    # 3. Balik lagi ke Dashboard
    return redirect(url_for('dashboard_admin'))

# --- RUTE EDIT USER (GET & POST) ---
@app.route('/admin/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        username_baru = request.form['username']
        nama_baru = request.form['nama_lengkap']
        role_baru = request.form['role']
        password_baru = request.form['password']

        # --- LOGIKA UPLOAD FOTO ---
        # 1. Cek apakah ada file yang dikirim?
        filename_foto = None
        
        if 'foto' in request.files:
            file = request.files['foto']
            # Kalau user pilih file dan ekstensinya benar
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Simpan file ke folder static/uploads
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                filename_foto = filename # Simpan nama filenya buat database

        # --- LOGIKA UPDATE DATABASE ---
        # Kita pakai logika bersusun:
        # A. Ganti Password + Ganti Foto
        if password_baru and filename_foto:
            pw_hash = generate_password_hash(password_baru)
            cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s, password=%s, foto=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, pw_hash, filename_foto, user_id))
        
        # B. Ganti Password aja (Foto tetap lama)
        elif password_baru:
            pw_hash = generate_password_hash(password_baru)
            cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s, password=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, pw_hash, user_id))
            
        # C. Ganti Foto aja (Password tetap lama)
        elif filename_foto:
             cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s, foto=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, filename_foto, user_id))

        # D. Gak ganti apa-apa (Cuma data teks biasa)
        else:
            cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('dashboard_admin'))

    # Bagian GET (Tampilkan Form)
    cur.execute("SELECT * FROM users_kampus WHERE id = %s", (user_id,))
    data_user_lama = cur.fetchone()
    cur.close()
    conn.close()

    return render_template('edit_user.html', user=data_user_lama)

if __name__ == '__main__':
    app.run(debug=True)