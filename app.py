from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from werkzeug.security import check_password_hash 
from werkzeug.security import generate_password_hash
import os 
from werkzeug.utils import secure_filename
# SEMUA YANG DI ATAS WAJIB DI SERTAKAN!

app = Flask(__name__)
app.secret_key = 'rahasia_kampus_binjai_2026' # Kunci buat tiket sesi

# KONFIGURASI UPLOAD
basedir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads') 
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


#KONEKSI DATABASE
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            host="localhost",
            database="postgres",
            user="postgres",
            password="12345", # password aman kalau untuk local
            port="5432"
        )
    return conn

# RUTE LOGIN
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_input = request.form['username']
        password_input = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users_kampus WHERE username = %s", (username_input,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        # PROSES VERIFIKASI
        if user:
            password_hash_db = user[2] 
            
            if check_password_hash(password_hash_db, password_input):
                
                session['sudah_login'] = True
                session['username'] = user[1]
                session['nama'] = user[3]
                session['role'] = user[4] # (admin/dosen/mahasiswa)
                session['foto'] = user[5]  # <--- TAMBAHAN BARU (Simpan nama file foto)
                # ROLE
                if session['role'] == 'admin':
                    return redirect(url_for('dashboard_admin'))
                elif session['role'] == 'dosen':
                    return redirect(url_for('dashboard_dosen'))
                elif session['role'] == 'mahasiswa':
                    return redirect(url_for('dashboard_mahasiswa'))
            
            else:
                return "Password Salah! Coba ingat-ingat lagi."
        else:
            return "Username tidak terdaftar!"

    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear() # Hapus semua sesi
    return redirect(url_for('login'))

# RUTE SEMENTARA (Biar gak error kalau redirect)
# Nanti kita bikin file HTML-nya terpisah
@app.route('/admin')
def dashboard_admin():
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    kata_kunci = request.args.get('search')

    conn = get_db_connection()
    cur = conn.cursor()

    if kata_kunci:
        query = """
            SELECT * FROM users_kampus 
            WHERE nama_lengkap ILIKE %s OR username ILIKE %s
            ORDER BY role ASC
        """
        search_term = f"%{kata_kunci}%"
        cur.execute(query, (search_term, search_term))
    else:
        cur.execute("SELECT * FROM users_kampus ORDER BY role ASC")
    
    users = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('dashboard_admin.html', data_users=users)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# DASHBOARD DOSEN
@app.route('/dosen')
def dashboard_dosen():
    # CEK ROLE
    if 'sudah_login' not in session or session['role'] != 'dosen':
        # Kalau bukan dosen, tendang balik ke halaman login/home
        return redirect(url_for('login'))

    return render_template('dashboard_dosen.html')


# DASHBOARD MAHASISWA
@app.route('/mahasiswa')
def dashboard_mahasiswa():
    if 'sudah_login' not in session or session['role'] != 'mahasiswa':
        return redirect(url_for('login'))

    siapa_yang_login = session['username']
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM nilai WHERE username_mhs = %s", (siapa_yang_login,))
    transkrip = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('dashboard_mahasiswa.html', data_nilai=transkrip)

# SIMPAN NILAI (ROLE DOSEN)
@app.route('/proses_nilai', methods=['POST'])
def proses_nilai():
    # CEK ROLE
    if 'sudah_login' not in session or session['role'] != 'dosen':
        return redirect(url_for('login'))

    mhs_target = request.form['username_mhs']
    matkul = request.form['matkul']
    sks = request.form['sks']
    nilai = request.form['nilai']
    dosen_pengampu = session['nama']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO nilai (username_mhs, mata_kuliah, sks, nilai_huruf, dosen_pengampu)
        VALUES (%s, %s, %s, %s, %s)
    """, (mhs_target, matkul, sks, nilai, dosen_pengampu))
    
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard_dosen'))

@app.route('/admin/tambah_user', methods=['GET'])
def halaman_tambah_user():
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    return render_template('tambah_user.html')

# SIMPAN USER BARU
@app.route('/admin/tambah_user', methods=['POST'])
def proses_tambah_user():
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    username = request.form['username']
    password_polos = request.form['password']
    nama_lengkap = request.form['nama_lengkap']
    role = request.form['role']

    # UNTUK HASHING PASSWORD
    password_acak = generate_password_hash(password_polos)

    # simpan kedatabase
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

# HAPUS USER
@app.route('/admin/hapus/<int:user_id>')
def hapus_user(user_id):
    if 'sudah_login' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # HAPUS DATA
    cur.execute("DELETE FROM users_kampus WHERE id = %s", (user_id,))
    
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('dashboard_admin'))

# EDIT USER
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

        # LOGIKA UPLOAD FOTO
        filename_foto = None
        
        if 'foto' in request.files:
            file = request.files['foto']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                filename_foto = filename

        # LOGIKA UPDATE DATABASE
        if password_baru and filename_foto:
            pw_hash = generate_password_hash(password_baru)
            cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s, password=%s, foto=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, pw_hash, filename_foto, user_id))
        
        # Ganti Password
        elif password_baru:
            pw_hash = generate_password_hash(password_baru)
            cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s, password=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, pw_hash, user_id))
            
        # Ganti Foto
        elif filename_foto:
             cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s, foto=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, filename_foto, user_id))

        else:
            cur.execute("UPDATE users_kampus SET username=%s, nama_lengkap=%s, role=%s WHERE id=%s", 
                        (username_baru, nama_baru, role_baru, user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('dashboard_admin'))

    cur.execute("SELECT * FROM users_kampus WHERE id = %s", (user_id,))
    data_user_lama = cur.fetchone()
    cur.close()
    conn.close()

    return render_template('edit_user.html', user=data_user_lama)

if __name__ == '__main__':

    app.run(debug=True)
