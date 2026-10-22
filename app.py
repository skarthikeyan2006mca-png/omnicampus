import os
import re
import json
import ssl
import socket
import urllib.request
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
from jinja2.exceptions import TemplateNotFound

app = Flask(__name__)
app.secret_key = 'omni_campus_secure_key'

# Image Upload Folder Configuration
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

RAW_HOST = 'bx81z20ma04pwez5khey-mysql.services.clever-cloud.com'
DB_USER = 'u1pk7sqztt9u5qsg'
DB_PASS = '6NDoEV0FKNPPKXsl0sc4'
DB_NAME = 'bx81z20ma04pwez5khey'

# IPv4 முகவரியை மட்டும் சரிபார்க்கும் செயல்பாடு
def is_valid_ipv4(ip_str):
    pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
    return bool(re.match(pattern, str(ip_str).strip()))

# CNAME-ஐத் தவிர்த்து நேரடி IPv4 முகவரியைக் கண்டறியும் DoH செயல்பாடு
def get_direct_ip(domain):
    endpoints = [
        (f"https://1.1.1.1/dns-query?name={domain}&type=A", {'Accept': 'application/dns-json'}),
        (f"https://dns.google/resolve?name={domain}&type=A", {'User-Agent': 'Mozilla/5.0'}),
        (f"https://9.9.9.9/dns-query?name={domain}&type=A", {'Accept': 'application/dns-json'})
    ]
    
    ctx = ssl._create_unverified_context()
    
    for url, headers in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                data = json.loads(response.read().decode())
                if 'Answer' in data:
                    for ans in data['Answer']:
                        ip_candidate = str(ans.get('data', '')).rstrip('.')
                        if is_valid_ipv4(ip_candidate):
                            print(f"[DNS SUCCESS] {domain} resolved to IP: {ip_candidate}")
                            return ip_candidate
        except Exception as e:
            print(f"[DNS DoH Fail] {url}: {e}")
            
    try:
        ip = socket.gethostbyname(domain)
        if is_valid_ipv4(ip):
            return ip
    except Exception:
        pass

    return domain

def get_db_connection():
    target_host = get_direct_ip(RAW_HOST)
    return mysql.connector.connect(
        host=target_host,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        port=3306,
        connect_timeout=10
    )

def safe_render(template_name, **context):
    try:
        return render_template(template_name, **context)
    except TemplateNotFound:
        return f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 50px 20px; background-color: #fef2f2; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center;">
            <div style="background: white; border: 2px solid #fca5a5; border-radius: 16px; padding: 40px; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
                <h2 style="color: #dc2626; margin-bottom: 10px;">⚠️ File Not Found in Templates</h2>
                <p style="color: #475569; font-size: 1rem; margin-bottom: 20px;">
                    Please create <b>{template_name}</b> inside your <b>templates/</b> folder.
                </p>
                <a href="javascript:history.back()" style="display: inline-block; padding: 10px 20px; background: #0f172a; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">← Go Back</a>
            </div>
        </div>
        """, 404

# ----------------- AUTO TABLE CREATION -----------------
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)

        # 1. Students Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                register_no VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                dob VARCHAR(20) NOT NULL,
                gender VARCHAR(20) DEFAULT 'Male',
                course VARCHAR(100) DEFAULT '',
                email VARCHAR(100) UNIQUE NOT NULL,
                student_mobile VARCHAR(20) DEFAULT '',
                father_name VARCHAR(100) DEFAULT '',
                mother_name VARCHAR(100) DEFAULT '',
                parent_mobile VARCHAR(20) DEFAULT '',
                aadhaar_no VARCHAR(20) DEFAULT '',
                address TEXT,
                password VARCHAR(255) NOT NULL
            )
        """)

        columns_to_add = [
            ("gender", "VARCHAR(20) DEFAULT 'Male'"),
            ("course", "VARCHAR(100) DEFAULT ''"),
            ("student_mobile", "VARCHAR(20) DEFAULT ''"),
            ("father_name", "VARCHAR(100) DEFAULT ''"),
            ("mother_name", "VARCHAR(100) DEFAULT ''"),
            ("parent_mobile", "VARCHAR(20) DEFAULT ''"),
            ("aadhaar_no", "VARCHAR(20) DEFAULT ''"),
            ("address", "TEXT")
        ]
        for col_name, col_type in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        # 2. Coordinators Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coordinators (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                name VARCHAR(100)
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM coordinators")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO coordinators (username, password, role, name) VALUES ('dept_admin', 'dept123', 'dept_rep', 'Department Representative')")
            cursor.execute("INSERT INTO coordinators (username, password, role, name) VALUES ('club_admin', 'club123', 'club_coord', 'Club Coordinator')")
            conn.commit()

        # 3. Clubs Table with 10 Default Clubs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clubs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                club_name VARCHAR(100) UNIQUE NOT NULL
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM clubs")
        if cursor.fetchone()[0] == 0:
            default_clubs = [
                'Green Army', 'Fine Arts', 'Tamil Mantram', 'Photography', 'Music Club',
                'Nature Club', 'Yuva Tourism Club', 'Vishaka Club', 'Sherlock Holmes Club', 'Pyros Club'
            ]
            for c in default_clubs:
                cursor.execute("INSERT INTO clubs (club_name) VALUES (%s)", (c,))
            conn.commit()

        # 4. Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                event_type VARCHAR(50) DEFAULT 'Department Event',
                organizer_name VARCHAR(100),
                contact_person VARCHAR(100),
                contact_phone VARCHAR(20),
                contact_person_2 VARCHAR(100) DEFAULT '',
                contact_phone_2 VARCHAR(20) DEFAULT '',
                event_date VARCHAR(50),
                venue VARCHAR(100),
                image_path VARCHAR(255) DEFAULT ''
            )
        """)

        event_cols = [
            ("image_path", "VARCHAR(255) DEFAULT ''"),
            ("contact_person_2", "VARCHAR(100) DEFAULT ''"),
            ("contact_phone_2", "VARCHAR(20) DEFAULT ''")
        ]
        for col_name, col_type in event_cols:
            try:
                cursor.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        # 5. Event Registrations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_registrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id INT,
                register_no VARCHAR(50),
                name VARCHAR(100),
                phone VARCHAR(20),
                email VARCHAR(100),
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            )
        """)

        try:
            cursor.execute("ALTER TABLE event_registrations ADD UNIQUE KEY unique_event_student (event_id, register_no)")
        except Exception:
            pass

        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database setup error: {e}")

init_db()

# ----------------- HOME & PORTAL -----------------
@app.route('/')
def home():
    return safe_render('index.html')

@app.route('/login')
@app.route('/login_portal')
def portal_login():
    return safe_render('login_portal.html')

# ----------------- CLUB COORDINATOR VIEW -----------------
@app.route('/clubs')
def clubs_list():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM clubs ORDER BY id ASC")
    clubs = cursor.fetchall()
    cursor.close()
    conn.close()
    return safe_render('clubs_list.html', clubs=clubs)

@app.route('/club_select/<int:club_id>')
def club_select(club_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM clubs WHERE id = %s", (club_id,))
    club = cursor.fetchone()
    cursor.close()
    conn.close()

    if club:
        session['selected_club_name'] = club['club_name']
        flash(f"Selected {club['club_name']}. Please login as Coordinator to upload events.", 'info')
        return redirect(url_for('coordinator_login'))
    return redirect(url_for('clubs_list'))

# ----------------- ADMIN CLUB MANAGEMENT -----------------
@app.route('/admin_clubs')
def admin_clubs():
    if session.get('user_type') != 'admin':
        flash('Security Alert: Only Admin can access Club Management!', 'danger')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM clubs ORDER BY id ASC")
    clubs = cursor.fetchall()
    cursor.close()
    conn.close()
    return safe_render('admin_clubs.html', clubs=clubs)

@app.route('/add_club', methods=['GET', 'POST'])
def add_club():
    if session.get('user_type') != 'admin':
        flash('Security Alert: Only Admin is authorized to add new clubs!', 'danger')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        club_name = request.form.get('club_name', '').strip()
        if not club_name:
            flash('Validation Error: Club name cannot be empty!', 'danger')
            return safe_render('add_club.html', mode='add')

        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute("INSERT INTO clubs (club_name) VALUES (%s)", (club_name,))
            conn.commit()
            flash('New Club Added Successfully!', 'success')
            return redirect(url_for('admin_clubs'))
        except Exception:
            flash('Club name already exists!', 'danger')
        finally:
            cursor.close()
            conn.close()

    return safe_render('add_club.html', mode='add')

@app.route('/edit_club/<int:club_id>', methods=['GET', 'POST'])
def edit_club(club_id):
    if session.get('user_type') != 'admin':
        flash('Security Alert: Only Admin is authorized to edit club names!', 'danger')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    if request.method == 'POST':
        new_name = request.form.get('club_name', '').strip()
        if not new_name:
            flash('Validation Error: Club name cannot be empty!', 'danger')
        else:
            try:
                cursor.execute("UPDATE clubs SET club_name = %s WHERE id = %s", (new_name, club_id))
                conn.commit()
                flash('Club Name Updated Successfully!', 'success')
                return redirect(url_for('admin_clubs'))
            except Exception:
                flash('Error updating club name or name already exists!', 'danger')
            finally:
                cursor.close()
                conn.close()

    cursor.execute("SELECT * FROM clubs WHERE id = %s", (club_id,))
    club = cursor.fetchone()
    cursor.close()
    conn.close()
    return safe_render('add_club.html', mode='edit', club=club)

@app.route('/delete_club/<int:club_id>')
def delete_club(club_id):
    if session.get('user_type') != 'admin':
        flash('Security Alert: Only Admin is authorized to delete clubs!', 'danger')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(buffered=True)
    try:
        cursor.execute("DELETE FROM clubs WHERE id = %s", (club_id,))
        conn.commit()
        flash('Club Deleted Successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting club: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_clubs'))

# ----------------- ADMIN PORTAL -----------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin123':
            session['user_type'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        flash('Invalid Admin Credentials!', 'danger')
    return safe_render('admin_login.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        reg_no = request.form['register_no']
        name = request.form['name']
        dob = request.form['dob']
        gender = request.form['gender']
        course = request.form['course']
        email = request.form['email']
        student_mobile = request.form['student_mobile']
        father_name = request.form['father_name']
        mother_name = request.form['mother_name']
        parent_mobile = request.form['parent_mobile']
        aadhaar_no = request.form['aadhaar_no']
        address = request.form['address']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute(
                """INSERT INTO students 
                (register_no, name, dob, gender, course, email, student_mobile, father_name, mother_name, parent_mobile, aadhaar_no, address, password) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (reg_no, name, dob, gender, course, email, student_mobile, father_name, mother_name, parent_mobile, aadhaar_no, address, password)
            )
            conn.commit()
            flash('Full Student Details Added Successfully!', 'success')
        except Exception as e:
            flash(f'Error adding student: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()
            
    return safe_render('admin_dashboard.html')

@app.route('/view_students')
def view_students():
    if session.get('user_type') != 'admin':
        flash('Please login as Admin to view students!', 'danger')
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM students ORDER BY id DESC")
    students = cursor.fetchall()
    cursor.close()
    conn.close()

    return safe_render('view_students.html', students=students)

# ----------------- COORDINATOR AUTH -----------------
@app.route('/coordinator_login', methods=['GET', 'POST'])
def coordinator_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM coordinators WHERE username = %s AND password = %s", (username, password))
        coord = cursor.fetchone()
        cursor.close()
        conn.close()

        if coord:
            session['user_type'] = coord['role']
            session['coord_name'] = session.get('selected_club_name', coord['name'])
            flash(f"Welcome {session['coord_name']}! You can now post events.", 'success')
            return redirect(url_for('add_event'))
        else:
            flash('Invalid Coordinator Username or Password!', 'danger')

    return safe_render('coordinator_login.html')

# ----------------- STUDENT AUTH -----------------
@app.route('/student_register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        reg_no = request.form['register_no']
        name = request.form['name']
        dob = request.form['dob']
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        try:
            cursor.execute(
                "INSERT INTO students (register_no, name, dob, email, password) VALUES (%s, %s, %s, %s, %s)",
                (reg_no, name, dob, email, password)
            )
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('student_login'))
        except Exception:
            flash('Register No / Email already exists!', 'danger')
        finally:
            cursor.close()
            conn.close()

    return safe_render('student_register.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        reg_no = request.form['register_no']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM students WHERE register_no = %s AND password = %s", (reg_no, password))
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        if student:
            session['user_type'] = 'student'
            session['student_reg_no'] = student['register_no']
            session['student_name'] = student['name']
            session['student_email'] = student['email']
            return redirect(url_for('events_feed'))
        else:
            flash('Invalid Register Number or Password!', 'danger')

    return safe_render('student_login.html')

# ----------------- EVENT UPLOAD -----------------
@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    user_type = session.get('user_type')
    if user_type not in ['dept_rep', 'club_coord', 'admin']:
        flash('Security Alert: You must login as Representative/Coordinator first!', 'danger')
        return redirect(url_for('coordinator_login'))

    is_club = (user_type == 'club_coord')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        organizer = request.form['organizer_name']
        contact_person = request.form.get('contact_person', '')
        contact_phone = request.form.get('contact_phone', '')
        contact_person_2 = request.form.get('contact_person_2', '')
        contact_phone_2 = request.form.get('contact_phone_2', '')
        event_date = request.form['event_date']
        venue = request.form['venue']
        event_type = 'Club Event' if is_club else 'Department Event'

        image_path = ''
        if 'event_image' in request.files:
            file = request.files['event_image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = f"uploads/{filename}"

        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute(
            """INSERT INTO events (title, description, event_type, organizer_name, contact_person, contact_phone, contact_person_2, contact_phone_2, event_date, venue, image_path) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (title, description, event_type, organizer, contact_person, contact_phone, contact_person_2, contact_phone_2, event_date, venue, image_path)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Event Advertisement posted successfully!', 'success')
        return redirect(url_for('events_feed'))

    default_organizer = session.get('selected_club_name', '') if is_club else ''
    return safe_render('add_event.html', default_organizer=default_organizer, is_club=is_club)

# ----------------- EVENTS VIEW WITH STRICT ROLE SEPARATION -----------------
@app.route('/events')
def events_feed():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    today_str = date.today().strftime('%Y-%m-%d')
    user_type = session.get('user_type')

    # AUTOMATIC DELETE EXPIRED EVENTS FROM DATABASE
    try:
        cursor.execute("DELETE FROM events WHERE event_date < %s", (today_str,))
        conn.commit()
    except Exception as e:
        print(f"Error auto-deleting expired events: {e}")

    # STRICT FILTERING ACCORDING TO ROLE
    if user_type == 'dept_rep':
        cursor.execute("SELECT * FROM events WHERE event_type = 'Department Event' ORDER BY event_date DESC")
    elif user_type == 'club_coord':
        selected_club = session.get('selected_club_name', '')
        if selected_club:
            cursor.execute("SELECT * FROM events WHERE event_type = 'Club Event' AND organizer_name = %s ORDER BY event_date DESC", (selected_club,))
        else:
            cursor.execute("SELECT * FROM events WHERE event_type = 'Club Event' ORDER BY event_date DESC")
    elif user_type == 'student':
        cursor.execute("SELECT * FROM events WHERE event_date >= %s ORDER BY event_date ASC", (today_str,))
    else:
        cursor.execute("SELECT * FROM events ORDER BY event_date DESC")
        
    events = cursor.fetchall()
    cursor.close()
    conn.close()
    return safe_render('events_feed.html', events=events, today=today_str)

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()
    cursor.close()
    conn.close()
    
    today_str = date.today().strftime('%Y-%m-%d')
    return safe_render('event_detail.html', event=event, today=today_str)

@app.route('/register_event/<int:event_id>', methods=['POST'])
def register_event(event_id):
    if 'student_reg_no' not in session:
        flash('Security Alert: You must login as a student first!', 'danger')
        return redirect(url_for('student_login'))

    logged_in_reg_no = session.get('student_reg_no')
    submitted_reg_no = request.form.get('register_no')

    if logged_in_reg_no != submitted_reg_no:
        flash(f'Security Error: Submitted Register No ({submitted_reg_no}) does not match your Logged-in Session ID ({logged_in_reg_no})!', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT event_date FROM events WHERE id = %s", (event_id,))
    ev = cursor.fetchone()
    today_str = date.today().strftime('%Y-%m-%d')
    if ev and ev['event_date'] < today_str:
        cursor.close()
        conn.close()
        flash('Registration Closed: This event date has expired!', 'danger')
        return redirect(url_for('events_feed'))

    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')

    cursor.execute(
        "SELECT * FROM event_registrations WHERE event_id = %s AND register_no = %s",
        (event_id, submitted_reg_no)
    )
    already_registered = cursor.fetchone()

    if already_registered:
        cursor.close()
        conn.close()
        flash('You have ALREADY registered for this event!', 'danger')
        return redirect(url_for('event_detail', event_id=event_id))

    try:
        cursor.execute(
            "INSERT INTO event_registrations (event_id, register_no, name, phone, email) VALUES (%s, %s, %s, %s, %s)",
            (event_id, submitted_reg_no, name, phone, email)
        )
        conn.commit()
        flash('Event Registered Successfully!', 'success')
    except Exception:
        flash('You have already registered for this event!', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('events_feed'))

# ----------------- VIEW EVENT REGISTRATIONS -----------------
@app.route('/view_registrations/<int:event_id>')
def view_registrations(event_id):
    user_type = session.get('user_type')
    if user_type not in ['dept_rep', 'club_coord', 'admin']:
        flash('Security Alert: You must login as Representative or Admin to view registrations!', 'danger')
        return redirect(url_for('coordinator_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)
    
    cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()

    if not event:
        cursor.close()
        conn.close()
        flash('Event not found!', 'danger')
        return redirect(url_for('events_feed'))

    if user_type == 'club_coord':
        selected_club = session.get('selected_club_name', '')
        if selected_club and event['organizer_name'] != selected_club:
            cursor.close()
            conn.close()
            flash(f'Security Alert: You can only view registrations for {selected_club} events!', 'danger')
            return redirect(url_for('events_feed'))

    cursor.execute("SELECT * FROM event_registrations WHERE event_id = %s ORDER BY id DESC", (event_id,))
    registrations = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return safe_render('view_registrations.html', event=event, registrations=registrations)

# ----------------- LOGOUT -----------------
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('portal_login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
