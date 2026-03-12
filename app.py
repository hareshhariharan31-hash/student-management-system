from flask import Flask, request, redirect, session, render_template, send_file
import sqlite3
import json
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from io import BytesIO
from datetime import datetime, timezone
import random
import smtplib

from email.mime.text import MIMEText
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet

import random

app = Flask(__name__)
app.secret_key = "super_secret_key"
app.permanent_session_lifetime = timedelta(minutes=30)

def send_email_otp(receiver_email, otp):
    sender_email = "hareshhariharan31@gmail.com"
    sender_password = "uuvgbbfracwfwoow"

    msg = MIMEText(f"Your OTP for password reset is: {otp}")
    msg["Subject"] = "Password Reset OTP"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent successfully to:", receiver_email)
    except Exception as e:
        print("❌ Email sending failed:", e)
DB_PATH = "database.db"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # STUDENTS TABLE
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS students(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT,
                   email TEXT,
                   department TEXT,
                   phone TEXT,
                   age INTEGER,
                   parent_name TEXT,
                   parent_email TEXT,
                   parent_mobile TEXT,
                   address TEXT
                   )
                   """)

    # Staff Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT,
                   age INTEGER,
                   email TEXT,
                   mobile TEXT,
                   address TEXT
)
""")
    # USERS TABLE (ONLY ONCE)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        mobile TEXT,
        student_id INTEGER,
        theme TEXT DEFAULT 'light'
    )
    """)

    # MARKS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        subject TEXT,
        marks INTEGER
    )
    """)

    # ATTENDANCE TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        total_classes INTEGER,
        attended_classes INTEGER
    )
    """)

    # OTP TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otp(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    otp_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# ---------------- ROLE DECORATOR ----------------
def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "username" not in session:
                return redirect("/login")
            if session.get("role") != role:
                return "Access Denied"
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ---------------- LOGIN ----------------
@app.route('/')
def home():
    return render_template("home.html")

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        session.permanent = True
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["student_id"] = user["student_id"]
            session["theme"] = user["theme"]

            if user["role"] == "admin":
                return redirect("/admin")
            elif user["role"] == "staff":
                return redirect("/staff")
            elif user["role"] == "student":
                return redirect("/student")

        return "Invalid Login"

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect("/login")

# ---------------- ADMIN ----------------
@app.route('/admin')
@role_required("admin")
def admin():
    conn = get_db()

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    total_staff = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='staff'"
    ).fetchone()[0]

    avg_marks = conn.execute(
        "SELECT AVG(marks) FROM marks"
    ).fetchone()[0]

    subjects_data = conn.execute("""
        SELECT subject, AVG(marks)
        FROM marks
        GROUP BY subject
    """).fetchall()

    conn.close()

    avg_marks = avg_marks if avg_marks else 0

    subjects = [row[0] for row in subjects_data]
    averages = [round(row[1],2) for row in subjects_data]

    return render_template(
        "admin.html",
        total_students=total_students,
        total_staff=total_staff,
        avg_marks=round(avg_marks,2),
        subjects=json.dumps(subjects),
        averages=json.dumps(averages)
    )

@app.route('/admin/students')
@role_required("admin")
def admin_students():
    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    return render_template("admin_students.html", students=students)

@app.route('/admin/staff')
@role_required("admin")
def admin_staff():
    conn = get_db()
    staff = conn.execute(
        "SELECT * FROM users WHERE role='staff'"
    ).fetchall()
    conn.close()

    return render_template("admin_staff.html", staff=staff)

# ---------------- ADD STAFF ----------------
@app.route('/add_staff', methods=['GET','POST'])
@role_required("admin")
def add_staff():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        mobile = request.form["mobile"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users(username,password,role,mobile) VALUES(?,?,?,?)",
                (username,password,"staff",mobile)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists!"
        conn.close()
        return redirect("/admin")

    return render_template("add_staff.html")

@app.route('/admin/delete_student/<int:student_id>')
@role_required("admin")
def delete_student(student_id):
    conn = get_db()

    # delete student marks & attendance first
    conn.execute("DELETE FROM marks WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM users WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM students WHERE id=?", (student_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/students")

@app.route('/admin/delete_staff/<int:user_id>')
@role_required("admin")
def delete_staff(user_id):
    conn = get_db()

    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect("/admin/staff")

@app.route('/admin/promote/<int:user_id>')
@role_required("admin")
def promote_staff(user_id):
    conn = get_db()

    conn.execute(
        "UPDATE users SET role='admin' WHERE id=?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin/staff")

@app.route('/admin/edit_staff/<int:user_id>', methods=['GET','POST'])
@role_required("admin")
def edit_staff(user_id):

    conn = get_db()

    if request.method == "POST":
        mobile = request.form["mobile"]

        conn.execute(
            "UPDATE users SET mobile=? WHERE id=?",
            (mobile, user_id)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/staff")

    staff = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    conn.close()

    return render_template("edit_staff.html", staff=staff)

# ---------------- STAFF ----------------
@app.route('/staff')
@role_required("staff")
def staff():
    conn = get_db()

    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    avg_marks = conn.execute("SELECT AVG(marks) FROM marks").fetchone()[0]

    conn.close()

    avg_marks = avg_marks if avg_marks else 0

    return render_template(
        "staff_dashboard.html",
        total_students=total_students,
        avg_marks=round(avg_marks,2)
    )

# Staff Edit
@app.route('/staff/edit', methods=['GET','POST'])
@role_required("staff")
def edit_staff_profile():

    username = session["username"]
    conn = get_db()

    if request.method == "POST":

        mobile = request.form["mobile"]
        
        conn.execute(
    "UPDATE users SET mobile=? WHERE username=?",
    (mobile, username)
)

        conn.commit()
        conn.close()

        return redirect("/staff")

    staff = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()

    conn.close()

    return render_template("staff_edit.html", staff=staff)

# ---------------- ADD STUDENT ----------------
@app.route('/add_student', methods=['GET','POST'])
def add_student():

    if "username" not in session or session["role"] not in ["staff", "admin"]:
        return "Access Denied"

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        department = request.form["department"]
        phone = request.form["phone"]
        username = request.form["username"]
        age = request.form["age"]
        parent_name = request.form["parent_name"]
        parent_email = request.form["parent_email"]
        parent_mobile = request.form["parent_mobile"]
        address = request.form["address"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()

        conn.execute("""
                     INSERT INTO students
                     (name,email,department,phone,age,parent_name,parent_email,parent_mobile,address)
                     VALUES (?,?,?,?,?,?,?,?,?)
                     """,(name,email,department,phone,age,parent_name,parent_email,parent_mobile,address))
        student_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO users(username,password,role,student_id) VALUES(?,?,?,?)",
            (username,password,"student",student_id)
        )

        conn.commit()
        conn.close()

        # Redirect based on role
        if session["role"] == "admin":
            return redirect("/admin/students")
        else:
            return redirect("/view_students")

    return render_template("add_student.html")

@app.route('/manage_students')
@role_required("staff")
def manage_students():
    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    return render_template("view_students.html", students=students)

@app.route('/view_students')
@role_required("staff")
def view_students():
    conn = get_db()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    return render_template("view_students.html", students=students)

@app.route('/add_marks/<int:student_id>', methods=['GET', 'POST'])
@role_required("staff")
def add_marks(student_id):

    conn = get_db()

    if request.method == "POST":
        subject = request.form["subject"]
        marks = request.form["marks"]

        conn.execute(
            "INSERT INTO marks(student_id, subject, marks) VALUES(?,?,?)",
            (student_id, subject, marks)
        )
        conn.commit()
        conn.close()
        return redirect("/view_students")

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (student_id,)
    ).fetchone()

    conn.close()

    return render_template("add_marks.html", student=student)

@app.route('/add_attendance/<int:student_id>', methods=['GET', 'POST'])
@role_required("staff")
def add_attendance(student_id):

    conn = get_db()

    if request.method == "POST":
        total = request.form["total"]
        attended = request.form["attended"]

        conn.execute(
            "INSERT INTO attendance(student_id, total_classes, attended_classes) VALUES(?,?,?)",
            (student_id, total, attended)
        )
        conn.commit()
        conn.close()
        return redirect("/view_students")

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (student_id,)
    ).fetchone()

    conn.close()

    return render_template("add_attendance.html", student=student)

# ---------------- STUDENT DASHBOARD ----------------
@app.route('/student')
@role_required("student")
def student():

    student_id = session.get("student_id")
    conn = get_db()

    student_info = conn.execute(
        "SELECT name,department FROM students WHERE id=?",
        (student_id,)
    ).fetchone()

    marks = conn.execute(
        "SELECT subject,marks FROM marks WHERE student_id=?",
        (student_id,)
    ).fetchall()

    attendance = conn.execute(
        "SELECT total_classes,attended_classes FROM attendance WHERE student_id=?",
        (student_id,)
    ).fetchone()

    conn.close()

    subjects = [m["subject"] for m in marks]
    scores = [m["marks"] for m in marks]

    avg_marks = round(sum(scores)/len(scores),2) if scores else 0
    total = attendance["total_classes"] if attendance else 0
    attended = attendance["attended_classes"] if attendance else 0
    attendance_percent = round((attended/total)*100,2) if total else 0

    return render_template(
        "student_dashboard.html",
        student_info=student_info,
        subjects=json.dumps(subjects),
        scores=json.dumps(scores),
        avg_marks=avg_marks,
        total=total,
        attended=attended,
        attendance_percent=attendance_percent
    )

@app.route('/student/edit', methods=['GET','POST'])
@role_required("student")
def edit_student():

    student_id = session["student_id"]
    conn = get_db()

    if request.method == "POST":

        age = request.form["age"]
        parent_name = request.form["parent_name"]
        parent_email = request.form["parent_email"]
        parent_mobile = request.form["parent_mobile"]
        address = request.form["address"]

        conn.execute("""
        UPDATE students
        SET age=?, parent_name=?, parent_email=?, parent_mobile=?, address=?
        WHERE id=?
        """,(age,parent_name,parent_email,parent_mobile,address,student_id))

        conn.commit()
        conn.close()

        return redirect("/student")

    student = conn.execute(
        "SELECT * FROM students WHERE id=?",
        (student_id,)
    ).fetchone()

    conn.close()

    return render_template("student_edit.html", student=student)

# ---------------- EXPORT PDF ----------------
@app.route('/export_pdf')
@role_required("student")
def export_pdf():

    student_id = session.get("student_id")
    conn = get_db()

    student = conn.execute(
        "SELECT name FROM students WHERE id=?",
        (student_id,)
    ).fetchone()

    marks = conn.execute(
        "SELECT subject,marks FROM marks WHERE student_id=?",
        (student_id,)
    ).fetchall()

    conn.close()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Marksheet - {student['name']}", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [["Subject", "Marks"]]
    for m in marks:
        data.append([m["subject"], m["marks"]])

    table = Table(data)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="marksheet.pdf",
        mimetype="application/pdf"
    )

# ---------------- OTP FORGOT PASSWORD ----------------
@app.route('/forgot', methods=['GET','POST'])
def forgot():

    if request.method == 'POST':

        username = request.form['username']
        otp = str(random.randint(100000,999999))

        session['otp'] = otp
        session['otp_expiry'] = datetime.now(timezone.utc) + timedelta(minutes=5)
        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if not user:
            conn.close()
            return "User not found!"
        
        if user["role"] == "student":
            data = conn.execute(
            "SELECT email FROM students WHERE id=?",
            (user["student_id"],)
        ).fetchone()
    
        elif user["role"] == "staff" or user["role"] == "admin":
            data = conn.execute(
            "SELECT email FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if data and data["email"]:
            send_email_otp(data["email"], otp)
        else:
            return "Email not found!"
        
        conn.execute("DELETE FROM otp WHERE username=?", (username,))

        conn.execute(
            "INSERT INTO otp(username,otp_code) VALUES(?,?)",
            (username, otp)
        )

        conn.commit()
        conn.close()

        send_email_otp(data["email"], otp)

        return "OTP sent to your registered email!"

    return render_template("forgot.html")

from email.mime.text import MIMEText

def send_email_otp(to_email, otp):
    try:
        sender_email = "yourgmail@gmail.com"
        password = "your_app_password"

        msg = MIMEText(f"Your OTP is: {otp}")
        msg["Subject"] = "Password Reset OTP"
        msg["From"] = sender_email
        msg["To"] = to_email

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
        server.login(sender_email, password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()

        print("OTP sent successfully")

    except Exception as e:
        print("Email sending failed:", e)

@app.route('/reset', methods=['GET','POST'])
def reset():

    if request.method == 'POST':

        username = request.form['username']
        otp_entered = request.form['otp']
        new_password = generate_password_hash(request.form['password'])

        if 'otp' not in session:
            return "OTP not generated!"

        if datetime.now(timezone.utc) > session['otp_expiry']:
            return "OTP Expired!"

        if otp_entered != session['otp']:
            return "Invalid OTP!"

        conn = get_db()

        conn.execute(
            "UPDATE users SET password=? WHERE username=?",
            (new_password, username)
        )

        conn.commit()
        conn.close()

        session.pop('otp', None)
        session.pop('otp_expiry', None)

        return redirect("/login")

    return render_template("reset.html")

@app.route('/toggle_theme')
def toggle_theme():

    if "username" not in session:
        return redirect("/login")

    conn = get_db()

    user = conn.execute(
        "SELECT theme FROM users WHERE username=?",
        (session["username"],)
    ).fetchone()

    new_theme = "dark" if user["theme"] == "light" else "light"

    conn.execute(
        "UPDATE users SET theme=? WHERE username=?",
        (new_theme, session["username"])
    )
    conn.commit()
    session["theme"] = new_theme
    conn.close()

    return redirect(request.referrer or "/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()   
    app.run(debug=True)
