import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import re
import hashlib
import secrets
from contextlib import contextmanager
import json
import sqlalchemy
from sqlalchemy import create_engine, text, exc
from urllib.parse import quote_plus  # 1. यह इम्पोर्ट ज़रूरी है

# --- Database Configuration ---
# 2. हम Pooler URL का इस्तेमाल कर रहे हैं
DB_USER = "postgres.mvvptqulrueqllvqnfrr"
DB_PASS = "AN"  # 3. यहाँ अपना नया, आसान पासवर्ड डालें
DB_HOST = "aws-1-ap-south-1.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres" 

# Create the PostgreSQL connection string and SQLAlchemy engine
try:
    # 4. (यह Pooler का फिक्स है) - यूज़रनेम को एनकोड करें
    ENCODED_USER = quote_plus(DB_USER)
    
    # 5. पासवर्ड को भी एनकोड करें
    ENCODED_PASS = quote_plus(DB_PASS)
    
    # 6. दोनों एनकोडेड वैल्यू का इस्तेमाल करें
    DATABASE_URL = f"postgresql://{ENCODED_USER}:{ENCODED_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    engine = create_engine(DATABASE_URL)
except Exception as e:
    st.error(f"Error creating database engine: {e}")
    st.stop()

# --- Initialize Session State ---
# (बाकी सारा कोड जैसा था वैसा ही रहेगा)
# ...

# --- Initialize Session State ---
# (बाकी सारा कोड जैसा था वैसा ही रहेगा)
# ...

# --- Initialize Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_type' not in st.session_state:
    st.session_state.user_type = None
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# --- Database Helper Functions ---
@contextmanager
def get_db_connection():
    """Context manager for handling database connections."""
    connection = None
    try:
        connection = engine.connect()
        yield connection
    except sqlalchemy.exc.OperationalError as e:
        st.error(f"Database connection error: {e}")
        yield None
    finally:
        if connection:
            connection.close()

def init_database():
    """Initialize all required database tables if they don't exist."""
    with get_db_connection() as conn:
        if conn is None: return False
        try:
            # Wrap all table creation in a single transaction
            with conn.begin():
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS teachers (
                        teacher_id VARCHAR(20) PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password VARCHAR(64) NOT NULL,
                        first_name VARCHAR(50) NOT NULL,
                        last_name VARCHAR(50) NOT NULL,
                        email VARCHAR(100) UNIQUE NOT NULL,
                        subjects JSON,
                        role VARCHAR(10) NOT NULL DEFAULT 'teacher', -- Using VARCHAR instead of ENUM for better cross-DB compatibility
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS students (
                        student_id VARCHAR(20) PRIMARY KEY,
                        first_name VARCHAR(50) NOT NULL,
                        last_name VARCHAR(50) NOT NULL,
                        email VARCHAR(100) UNIQUE NOT NULL,
                        phone VARCHAR(20) NOT NULL,
                        date_of_birth DATE NOT NULL,
                        gender VARCHAR(10) NOT NULL,
                        course VARCHAR(100) NOT NULL,
                        year VARCHAR(20) NOT NULL,
                        semester VARCHAR(20) NOT NULL,
                        address TEXT,
                        emergency_contact VARCHAR(20),
                        enrollment_date DATE NOT NULL,
                        password VARCHAR(64) NOT NULL,
                        status VARCHAR(20) DEFAULT 'Active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS subjects (
                        subject_id VARCHAR(20) PRIMARY KEY,
                        name VARCHAR(100) NOT NULL UNIQUE,
                        credits INT NOT NULL
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS grades (
                        grade_id VARCHAR(20) PRIMARY KEY,
                        student_id VARCHAR(20) NOT NULL,
                        subject VARCHAR(100) NOT NULL,
                        exam_type VARCHAR(20) NOT NULL,
                        marks_obtained DECIMAL(5,2) NOT NULL,
                        total_marks DECIMAL(5,2) NOT NULL,
                        percentage DECIMAL(5,2) NOT NULL,
                        grade CHAR(2) NOT NULL,
                        date DATE NOT NULL,
                        teacher_id VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE
                    )
                """))
                
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS attendance (
                        attendance_id VARCHAR(20) PRIMARY KEY,
                        student_id VARCHAR(20) NOT NULL,
                        date DATE NOT NULL,
                        subject VARCHAR(100) NOT NULL,
                        status VARCHAR(10) NOT NULL,
                        teacher_id VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Removed MySQL-specific 'ON UPDATE'
                        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                        FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
                        UNIQUE (student_id, date, subject) -- Standard SQL for UNIQUE constraint
                    )
                """))
            return True
        except sqlalchemy.exc.SQLAlchemyError as e:
            st.error(f"Error during database initialization: {e}")
            return False

def hash_password(password):
    """Hash password using SHA-256 for secure storage."""
    return hashlib.sha256(password.encode()).hexdigest()

def initialize_default_data():
    """Initialize the database with a default admin user and subjects if none exist."""
    with get_db_connection() as conn:
        if conn is None: return
        try:
            with conn.begin(): # Start transaction
                # Check for admin
                result = conn.execute(text("SELECT COUNT(*) FROM teachers WHERE username = :user"), {"user": "admin"})
                if result.scalar() == 0:
                    conn.execute(text("""
                        INSERT INTO teachers (teacher_id, username, password, first_name, last_name, email, subjects, role)
                        VALUES (:tid, :user, :pass, :fname, :lname, :email, :subjects, :role)
                    """), {
                        "tid": "TEA001", 
                        "user": "admin", 
                        "pass": hash_password("admin123"),
                        "fname": "Admin", 
                        "lname": "User", 
                        "email": "admin@school.com",
                        "subjects": '["All Subjects"]', 
                        "role": "admin"
                    })
                
                # Check for subjects
                result = conn.execute(text("SELECT COUNT(*) FROM subjects"))
                if result.scalar() == 0:
                    default_subjects = [
                        {"id": "SUB001", "name": "Data Science", "credits": 4},
                        {"id": "SUB002", "name": "Computer Science", "credits": 4},
                        {"id": "SUB003", "name": "Machine Learning", "credits": 4},
                        {"id": "SUB004", "name": "Web Development", "credits": 4},
                        {"id": "SUB005", "name": "Database Systems", "credits": 3},
                        {"id": "SUB006", "name": "Software Engineering", "credits": 3}
                    ]
                    # Use executemany with a list of dictionaries
                    conn.execute(text("INSERT INTO subjects (subject_id, name, credits) VALUES (:id, :name, :credits)"), default_subjects)
        except sqlalchemy.exc.SQLAlchemyError as e:
            st.error(f"Error initializing default data: {e}")

# --- Utility Functions ---
def validate_email(email):
    """Validate email format using regex."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_id(prefix, table_name, column_name):
    """Generic function to generate a new sequential ID."""
    with get_db_connection() as conn:
        if conn is None: return f"{prefix}001"
        try:
            # Use f-string for table/column names, which is safe as they are not user-input
            query = text(f"SELECT {column_name} FROM {table_name} ORDER BY {column_name} DESC LIMIT 1")
            result = conn.execute(query).fetchone()
            if result:
                last_id = int(result[0][len(prefix):])
                return f"{prefix}{last_id + 1:03d}"
            return f"{prefix}001"
        except sqlalchemy.exc.SQLAlchemyError as e:
            st.error(f"Error generating ID: {e}")
            return f"{prefix}001"

def generate_student_id():
    return generate_id("STU", "students", "student_id")

def generate_teacher_id():
    return generate_id("TEA", "teachers", "teacher_id")

def generate_grade_id():
    return generate_id("GRA", "grades", "grade_id")

def generate_attendance_id():
    return generate_id("ATT", "attendance", "attendance_id")

def generate_password():
    """Generate a random, secure 8-character password."""
    return secrets.token_urlsafe(8)

def calculate_grade(percentage):
    """Calculate letter grade based on percentage."""
    if percentage >= 90:
        return 'A+'
    elif percentage >= 85:
        return 'A'
    elif percentage >= 80:
        return 'B+'
    elif percentage >= 75:
        return 'B'
    elif percentage >= 70:
        return 'C+'
    elif percentage >= 65:
        return 'C'
    elif percentage >= 60:
        return 'D'
    else:
        return 'F'

# --- Authentication ---
def authenticate_user(username, password, user_type):
    """Authenticate a user by checking credentials against the database."""
    with get_db_connection() as conn:
        if conn is None: return None
        hashed_pass = hash_password(password)
        try:
            if user_type == "student":
                query = text("SELECT * FROM students WHERE student_id = :user AND password = :pass")
            else: # teacher or admin
                query = text("SELECT * FROM teachers WHERE username = :user AND password = :pass")
            
            result = conn.execute(query, {"user": username, "pass": hashed_pass})
            # .mappings().fetchone() returns a dict-like object (replaces dictionary=True)
            user = result.mappings().fetchone()
            return user
        except sqlalchemy.exc.SQLAlchemyError as e:
            st.error(f"Authentication error: {e}")
            return None

def login_page():
    """Display the main login interface."""
    st.title("🎓 School Management System")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["👨‍🎓 Student Login", "👨‍🏫 Staff Login (Teacher/Admin)"])

    with tab1:
        with st.form("student_login"):
            username = st.text_input("Student ID", placeholder="Enter your Student ID")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login", type="primary")
            if submitted:
                student = authenticate_user(username, password, "student")
                if student:
                    st.session_state.logged_in = True
                    st.session_state.user_type = "student"
                    st.session_state.current_user = student
                    st.rerun()
                else:
                    st.error("Invalid credentials!")
    
    with tab2:
        with st.form("staff_login"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login", type="primary")
            if submitted:
                staff_user = authenticate_user(username, password, "staff")
                if staff_user:
                    st.session_state.logged_in = True
                    st.session_state.user_type = staff_user['role']
                    st.session_state.current_user = staff_user
                    st.rerun()
                else:
                    st.error("Invalid credentials!")

    with st.expander("ℹ️ Demo Credentials"):
        st.write("**Default Admin Login:**")
        st.code("Username: admin\nPassword: admin123")

def logout():
    """Clear session state to log the user out."""
    st.session_state.logged_in = False
    st.session_state.user_type = None
    st.session_state.current_user = None
    st.rerun()

# --- Data Retrieval Functions ---
# pd.read_sql works fine with the SQLAlchemy connection and %s param style for psycopg2
def get_student_grades(student_id):
    with get_db_connection() as conn:
        if conn is None: return []
        try:
            return pd.read_sql("SELECT * FROM grades WHERE student_id = %s ORDER BY date DESC", conn, params=(student_id,)).to_dict('records')
        except Exception as e:
            st.error(f"Error fetching grades: {e}")
            return []

def get_student_attendance(student_id):
    with get_db_connection() as conn:
        if conn is None: return []
        try:
            return pd.read_sql("SELECT * FROM attendance WHERE student_id = %s ORDER BY date DESC", conn, params=(student_id,)).to_dict('records')
        except Exception as e:
            st.error(f"Error fetching attendance: {e}")
            return []

def get_all_students():
    with get_db_connection() as conn:
        if conn is None: return []
        try:
            return pd.read_sql("SELECT * FROM students ORDER BY first_name, last_name", conn).to_dict('records')
        except Exception as e:
            st.error(f"Error fetching students: {e}")
            return []

def get_all_teachers():
    with get_db_connection() as conn:
        if conn is None: return []
        try:
            return pd.read_sql("SELECT teacher_id, username, first_name, last_name, email, role FROM teachers ORDER BY first_name", conn).to_dict('records')
        except Exception as e:
            st.error(f"Error fetching teachers: {e}")
            return []

def get_all_subjects():
    with get_db_connection() as conn:
        if conn is None: return []
        try:
            return pd.read_sql("SELECT * FROM subjects ORDER BY name", conn).to_dict('records')
        except Exception as e:
            st.error(f"Error fetching subjects: {e}")
            return []

# --- Admin Dashboard Functions ---
def admin_dashboard():
    """The main dashboard for the admin user."""
    st.title(f"👑 Admin Dashboard")
    st.sidebar.markdown(f"**Welcome, {st.session_state.current_user['first_name']}**")
    st.sidebar.button("Logout", on_click=logout)

    menu = ["📊 Dashboard", "👨‍🏫 Manage Teachers", "👨‍🎓 Manage Students", "📚 Manage Subjects"]
    choice = st.selectbox("Navigation", menu)

    if choice == "📊 Dashboard":
        admin_home()
    elif choice == "👨‍🏫 Manage Teachers":
        manage_teachers_admin()
    elif choice == "👨‍🎓 Manage Students":
        manage_students_admin()
    elif choice == "📚 Manage Subjects":
        manage_subjects_admin()

def admin_home():
    """The home page of the admin dashboard with overview stats."""
    st.subheader("📊 System Overview")
    students = get_all_students()
    teachers = get_all_teachers()
    subjects = get_all_subjects()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Students", len(students))
    col2.metric("Total Teachers", len(teachers))
    col3.metric("Total Subjects", len(subjects))

def manage_teachers_admin():
    """Admin interface for managing teachers."""
    st.subheader("👨‍🏫 Manage Teachers")
    
    if 'new_teacher_credentials' in st.session_state:
        creds = st.session_state.new_teacher_credentials
        st.success("Teacher added successfully! ✅")
        st.info(f"**Teacher ID:** `{creds['id']}`")
        st.info(f"**Username:** `{creds['username']}`")
        if creds.get('password'):
            st.info(f"**Password:** `{creds['password']}`")
            st.warning("Please copy these credentials securely.")
        del st.session_state.new_teacher_credentials
    
    with st.expander("➕ Add a New Teacher"):
        
        st.write("**Password Options**")
        password_option = st.radio(
            "Choose password method", 
            ("Generate Automatically", "Set Manually"), 
            horizontal=True,
            key="teacher_pwd_option",
            label_visibility="collapsed"
        )
        
        with st.form("new_teacher_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username*")
                first_name = st.text_input("First Name*")
                last_name = st.text_input("Last Name*")
            with col2:
                email = st.text_input("Email*")
            
            st.markdown("---")
            
            manual_password = ""
            confirm_password = ""
            if password_option == "Set Manually":
                st.write("Enter password details:")
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    manual_password = st.text_input("Enter Password*", type="password", key="teacher_pwd")
                with p_col2:
                    confirm_password = st.text_input("Confirm Password*", type="password", key="teacher_pwd_confirm")
            
            submitted = st.form_submit_button("Add Teacher")
            if submitted:
                if not all([username, first_name, last_name, email]):
                    st.error("Please fill all required fields marked with *")
                elif not validate_email(email):
                    st.error("Please enter a valid email address.")
                else:
                    password = None
                    show_password = False
                    
                    if password_option == "Generate Automatically":
                        password = generate_password()
                        show_password = True
                    else:
                        if not manual_password:
                            st.error("Manual password cannot be empty.")
                            return
                        if manual_password != confirm_password:
                            st.error("Passwords do not match.")
                            return
                        password = manual_password
                    
                    if password:
                        try:
                            teacher_id = generate_teacher_id()
                            with get_db_connection() as conn:
                                if conn is None: raise Exception("Database connection failed")
                                with conn.begin(): # Start transaction
                                    conn.execute(text("""
                                        INSERT INTO teachers (teacher_id, username, password, first_name, last_name, email, role)
                                        VALUES (:tid, :user, :pass, :fname, :lname, :email, 'teacher')
                                    """), {
                                        "tid": teacher_id,
                                        "user": username,
                                        "pass": hash_password(password),
                                        "fname": first_name,
                                        "lname": last_name,
                                        "email": email
                                    })
                            
                            st.session_state.new_teacher_credentials = {
                                'id': teacher_id,
                                'username': username,
                                'password': password if show_password else None
                            }
                            st.rerun()
                        except sqlalchemy.exc.IntegrityError as e:
                            if "username" in str(e).lower():
                                st.error("Username already exists!")
                            elif "email" in str(e).lower():
                                st.error("Email already exists!")
                            else:
                                st.error(f"Error adding teacher: {e}")
                        except Exception as e:
                            st.error(f"An error occurred: {e}")

    st.markdown("---")
    st.write("**All Teachers List**")
    teachers = get_all_teachers()
    
    if 'teacher_password_reset_info' in st.session_state:
        info = st.session_state.teacher_password_reset_info
        st.success(f"Password for teacher {info['teacher_id']} has been reset!")
        st.info(f"**New Generated Password:** `{info['new_password']}`")
        st.warning("Please share this new password securely.")
        del st.session_state.teacher_password_reset_info
    
    if teachers:
        df_teachers = pd.DataFrame(teachers)
        df_teachers_display = df_teachers[df_teachers['role'] != 'admin']
        
        if not df_teachers_display.empty:
            st.dataframe(df_teachers_display, use_container_width=True)
            
            teacher_options = {f"{t['teacher_id']} - {t['first_name']} {t['last_name']}": t['teacher_id'] 
                               for t in teachers if t['role'] != 'admin'}
            selected_teacher_label = st.selectbox("Select a teacher to manage", options=[""] + list(teacher_options.keys()))
            
            if selected_teacher_label:
                teacher_id = teacher_options[selected_teacher_label]
                
                with st.expander("🔑 Manage Selected Teacher", expanded=True):
                    st.write(f"**Actions for:** {selected_teacher_label}")
                    
                    if st.button("Generate & Set New Password", key=f"gen_teacher_pw_{teacher_id}"):
                        new_pw = generate_password()
                        try:
                            with get_db_connection() as conn:
                                if conn is None: raise Exception("Database connection failed")
                                with conn.begin():
                                    conn.execute(text("UPDATE teachers SET password = :pass WHERE teacher_id = :tid"),
                                                 {"pass": hash_password(new_pw), "tid": teacher_id})
                            st.session_state.teacher_password_reset_info = {
                                'teacher_id': teacher_id, 
                                'new_password': new_pw
                            }
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error resetting password: {e}")

                    with st.form(key=f"custom_teacher_pw_{teacher_id}"):
                        st.write("Or, set a custom password:")
                        custom_pw = st.text_input("New Custom Password", type="password", key=f"custom_pwd_{teacher_id}")
                        if st.form_submit_button("Set Custom Password"):
                            if custom_pw:
                                try:
                                    with get_db_connection() as conn:
                                        if conn is None: raise Exception("Database connection failed")
                                        with conn.begin():
                                            conn.execute(text("UPDATE teachers SET password = :pass WHERE teacher_id = :tid"),
                                                         {"pass": hash_password(custom_pw), "tid": teacher_id})
                                    st.success(f"Successfully set a new password for {teacher_id}.")
                                except Exception as e:
                                    st.error(f"Error setting password: {e}")
                            else:
                                st.warning("Password cannot be empty.")
                    
                    st.markdown("---")
                    if st.button("🗑️ Delete This Teacher", type="primary", key=f"del_teacher_{teacher_id}"):
                        try:
                            with get_db_connection() as conn:
                                if conn is None: raise Exception("Database connection failed")
                                with conn.begin():
                                    conn.execute(text("DELETE FROM teachers WHERE teacher_id = :tid"), {"tid": teacher_id})
                            st.success(f"Teacher {teacher_id} has been deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting teacher: {e}")
        else:
            st.info("No teachers found (besides admin). Add some teachers above.")

def manage_subjects_admin():
    """Admin interface for managing subjects."""
    st.subheader("📚 Manage Subjects")
    
    with st.form("new_subject_form", clear_on_submit=True):
        name = st.text_input("Subject Name*")
        credits = st.number_input("Credits*", min_value=1, max_value=10, step=1)
        submitted = st.form_submit_button("Add Subject")
        if submitted and name:
            try:
                subject_id = generate_id("SUB", "subjects", "subject_id")
                with get_db_connection() as conn:
                    if conn is None: raise Exception("Database connection failed")
                    with conn.begin():
                        conn.execute(text("INSERT INTO subjects (subject_id, name, credits) VALUES (:sid, :name, :credits)"),
                                     {"sid": subject_id, "name": name, "credits": credits})
                    st.success(f"Subject '{name}' added!")
                    st.rerun()
            except sqlalchemy.exc.IntegrityError:
                st.error("Subject name already exists!")
            except Exception as e:
                st.error(f"Error adding subject: {e}")

    subjects = get_all_subjects()
    if subjects:
        st.dataframe(pd.DataFrame(subjects), use_container_width=True)

# --- Teacher Dashboard ---
def teacher_dashboard():
    """Complete teacher dashboard with all functionality."""
    st.title(f"👨‍🏫 Teacher Dashboard")
    st.sidebar.markdown(f"**Welcome, {st.session_state.current_user['first_name']}**")
    st.sidebar.button("Logout", on_click=logout)

    menu = ["📊 Dashboard", "👨‍🎓 Manage Students", "📝 Record Grades", "📅 Mark Attendance", "📈 View Reports"]
    choice = st.selectbox("Navigation", menu)

    if choice == "📊 Dashboard":
        teacher_home()
    elif choice == "👨‍🎓 Manage Students":
        teacher_manage_students()
    elif choice == "📝 Record Grades":
        teacher_record_grades()
    elif choice == "📅 Mark Attendance":
        teacher_mark_attendance()
    elif choice == "📈 View Reports":
        teacher_view_reports()

def teacher_home():
    """Teacher dashboard home page."""
    st.subheader("📊 Teacher Overview")
    
    students = get_all_students()
    subjects = get_all_subjects()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Students", len(students))
    col2.metric("Available Subjects", len(subjects))
    
    with get_db_connection() as conn:
        if conn:
            try:
                # Fixed MySQL-specific DATE_SUB/CURDATE to Postgres equivalent
                recent_grades = pd.read_sql("""
                    SELECT COUNT(*) as count FROM grades 
                    WHERE teacher_id = %s AND date >= (CURRENT_DATE - INTERVAL '7 days')
                """, conn, params=(st.session_state.current_user['teacher_id'],))
                col3.metric("Grades This Week", recent_grades['count'].iloc[0] if not recent_grades.empty else 0)
            except Exception as e:
                st.error(f"Error loading dashboard stats: {e}")
                col3.metric("Grades This Week", "Error")


def teacher_record_grades():
    """Teacher interface for recording grades."""
    st.subheader("📝 Record Student Grades")
    
    students = get_all_students()
    subjects = get_all_subjects()
    
    if not students:
        st.warning("No students found. Please add students first.")
        return
    
    if not subjects:
        st.warning("No subjects found. Please contact admin to add subjects.")
        return
    
    with st.form("grade_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            student_options = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
            selected_student = st.selectbox("Select Student*", options=student_options)
            
            subject_options = [s['name'] for s in subjects]
            selected_subject = st.selectbox("Select Subject*", options=subject_options)
            
            exam_type = st.selectbox("Exam Type*", options=["Mid-term", "Final", "Quiz", "Assignment", "Project"])
        
        with col2:
            marks_obtained = st.number_input("Marks Obtained*", min_value=0.0, max_value=1000.0, step=0.5)
            total_marks = st.number_input("Total Marks*", min_value=1.0, max_value=1000.0, step=0.5, value=100.0)
            exam_date = st.date_input("Exam Date*", value=date.today())
        
        submitted = st.form_submit_button("Record Grade")
        
        if submitted:
            if selected_student and selected_subject and marks_obtained is not None and total_marks > 0:
                student_id = selected_student.split(" - ")[0]
                percentage = (marks_obtained / total_marks) * 100
                grade = calculate_grade(percentage)
                grade_id = generate_grade_id()
                
                try:
                    with get_db_connection() as conn:
                        if conn is None: raise Exception("Database connection failed")
                        with conn.begin():
                            conn.execute(text("""
                                INSERT INTO grades (grade_id, student_id, subject, exam_type, marks_obtained, total_marks, percentage, grade, date, teacher_id)
                                VALUES (:gid, :sid, :sub, :etype, :mobt, :mtot, :perc, :grade, :date, :tid)
                            """), {
                                "gid": grade_id, "sid": student_id, "sub": selected_subject, "etype": exam_type,
                                "mobt": marks_obtained, "mtot": total_marks, "perc": percentage,
                                "grade": grade, "date": exam_date, "tid": st.session_state.current_user['teacher_id']
                            })
                    st.success(f"Grade recorded successfully! Grade: {grade} ({percentage:.1f}%)")
                except Exception as e:
                    st.error(f"Error recording grade: {e}")
            else:
                st.error("Please fill all required fields.")
    
    st.markdown("---")
    st.subheader("📊 Recent Grades Recorded")
    
    with get_db_connection() as conn:
        if conn:
            try:
                recent_grades = pd.read_sql("""
                    SELECT g.grade_id, g.student_id, s.first_name, s.last_name, g.subject, g.exam_type, 
                           g.marks_obtained, g.total_marks, g.percentage, g.grade, g.date
                    FROM grades g
                    JOIN students s ON g.student_id = s.student_id
                    WHERE g.teacher_id = %s
                    ORDER BY g.date DESC
                    LIMIT 10
                """, conn, params=(st.session_state.current_user['teacher_id'],))
                
                if not recent_grades.empty:
                    st.dataframe(recent_grades, use_container_width=True)
                else:
                    st.info("No grades recorded by you yet.")
            except Exception as e:
                st.error(f"Error loading recent grades: {e}")

def teacher_mark_attendance():
    """Teacher interface for marking attendance."""
    st.subheader("📅 Mark Student Attendance")
    
    students = get_all_students()
    subjects = get_all_subjects()
    
    if not students:
        st.warning("No students found.")
        return
    if not subjects:
        st.warning("No subjects found.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        subject_options = [s['name'] for s in subjects]
        selected_subject = st.selectbox("Select Subject", options=subject_options)
    with col2:
        attendance_date = st.date_input("Date", value=date.today())
    
    if selected_subject and attendance_date:
        st.markdown("---")
        st.subheader(f"Marking Attendance for {selected_subject} on {attendance_date}")

        existing_attendance = {}
        with get_db_connection() as conn:
            if conn:
                try:
                    query = "SELECT student_id, status FROM attendance WHERE date = %s AND subject = %s"
                    existing_df = pd.read_sql(query, conn, params=(attendance_date, selected_subject))
                    existing_attendance = dict(zip(existing_df['student_id'], existing_df['status']))
                except Exception as e:
                    st.error(f"Error loading existing attendance: {e}")
        
        with st.form("attendance_form"):
            attendance_data = {}
            for student in students:
                student_id = student['student_id']
                current_status = existing_attendance.get(student_id, 'Present')
                status_index = 0 if current_status == 'Present' else 1
                
                cols = st.columns([3, 2])
                cols[0].write(f"{student['first_name']} {student['last_name']} ({student_id})")
                attendance_data[student_id] = cols[1].radio(
                    "Status", 
                    ['Present', 'Absent'], 
                    index=status_index, 
                    key=f"status_{student_id}", 
                    horizontal=True,
                    label_visibility="collapsed"
                )
            
            if st.form_submit_button("Save Attendance"):
                try:
                    with get_db_connection() as conn:
                        if conn is None: raise Exception("Database connection failed")
                        
                        # Use list of dicts for executemany with named parameters
                        records_to_insert = []
                        for student_id, status in attendance_data.items():
                            records_to_insert.append({
                                "aid": generate_attendance_id(),
                                "sid": student_id,
                                "date": attendance_date,
                                "sub": selected_subject,
                                "status": status,
                                "tid": st.session_state.current_user['teacher_id']
                            })
                        
                        with conn.begin(): # Start transaction
                            # Delete existing records for this day/subject first
                            delete_query = text("DELETE FROM attendance WHERE date = :date AND subject = :subject")
                            conn.execute(delete_query, {"date": attendance_date, "subject": selected_subject})

                            # Insert all new records
                            insert_query = text("""
                                INSERT INTO attendance (attendance_id, student_id, date, subject, status, teacher_id)
                                VALUES (:aid, :sid, :date, :sub, :status, :tid)
                            """)
                            if records_to_insert:
                                conn.execute(insert_query, records_to_insert)
                        
                        st.success("Attendance saved successfully!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error saving attendance: {e}")

def teacher_view_reports():
    """Teacher interface for viewing reports."""
    st.subheader("📈 Student Reports")
    
    students = get_all_students()
    if not students:
        st.warning("No students found.")
        return
    
    student_options = [""] + [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
    selected_student = st.selectbox("Select Student for Detailed Report", options=student_options)
    
    if selected_student:
        student_id = selected_student.split(" - ")[0]
        student_info = next((s for s in students if s['student_id'] == student_id), None)
        
        if student_info:
            st.markdown("---")
            st.subheader(f"Report for {student_info['first_name']} {student_info['last_name']}")
            
            grades = get_student_grades(student_id)
            if grades:
                st.write("**Grades:**")
                df_grades = pd.DataFrame(grades)
                st.dataframe(df_grades[['subject', 'exam_type', 'marks_obtained', 'total_marks', 'percentage', 'grade', 'date']], use_container_width=True)
            else:
                st.info("No grades recorded for this student.")
            
            attendance = get_student_attendance(student_id)
            if attendance:
                st.write("**Attendance:**")
                df_attendance = pd.DataFrame(attendance)
                st.dataframe(df_attendance[['date', 'subject', 'status']], use_container_width=True)
                
                total = len(attendance)
                present = len([a for a in attendance if a['status'] == 'Present'])
                percent = (present / total * 100) if total > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Classes", total)
                col2.metric("Classes Present", present)
                col3.metric("Attendance %", f"{percent:.1f}%")
            else:
                st.info("No attendance recorded for this student.")

# --- Student Dashboard ---
def student_dashboard():
    """Complete student dashboard."""
    st.title(f"👨‍🎓 Student Dashboard")
    st.sidebar.markdown(f"**Welcome, {st.session_state.current_user['first_name']}**")
    st.sidebar.button("Logout", on_click=logout)

    menu = ["📊 Dashboard", "📝 View Grades", "📅 View Attendance", "👤 Profile"]
    choice = st.selectbox("Navigation", menu)

    if choice == "📊 Dashboard":
        student_home()
    elif choice == "📝 View Grades":
        student_view_grades()
    elif choice == "📅 View Attendance":
        student_view_attendance()
    elif choice == "👤 Profile":
        student_profile()

def student_home():
    """Student dashboard home page."""
    st.subheader("📊 Your Academic Overview")
    student_id = st.session_state.current_user['student_id']
    grades = get_student_grades(student_id)
    attendance = get_student_attendance(student_id)
    
    col1, col2, col3 = st.columns(3)
    if grades:
        avg_percentage = sum(float(g['percentage']) for g in grades) / len(grades) # Ensure float
        col1.metric("Overall Average", f"{avg_percentage:.1f}%")
    else:
        col1.metric("Overall Average", "N/A")
    
    col2.metric("Total Exams Logged", len(grades))
    
    if attendance:
        present_count = len([a for a in attendance if a['status'] == 'Present'])
        attendance_percentage = (present_count / len(attendance)) * 100
        col3.metric("Attendance", f"{attendance_percentage:.1f}%")
    else:
        col3.metric("Attendance", "N/A")

def student_view_grades():
    """Student interface for viewing grades."""
    st.subheader("📝 Your Grades")
    grades = get_student_grades(st.session_state.current_user['student_id'])
    
    if grades:
        df_grades = pd.DataFrame(grades)
        # Ensure percentage is numeric for aggregation
        df_grades['percentage'] = pd.to_numeric(df_grades['percentage'])
        
        st.dataframe(df_grades[['subject', 'exam_type', 'marks_obtained', 'total_marks', 'percentage', 'grade', 'date']], use_container_width=True)
        
        st.markdown("---")
        st.subheader("📊 Grade Analysis by Subject")
        
        subject_averages = df_grades.groupby('subject')['percentage'].mean().reset_index()
        subject_averages.rename(columns={'percentage': 'Average Percentage'}, inplace=True)
        st.bar_chart(subject_averages.set_index('subject'))

    else:
        st.info("No grades available yet.")

def student_view_attendance():
    """Student interface for viewing attendance."""
    st.subheader("📅 Your Attendance")
    attendance = get_student_attendance(st.session_state.current_user['student_id'])
    
    if attendance:
        df_attendance = pd.DataFrame(attendance)
        st.dataframe(df_attendance[['date', 'subject', 'status']], use_container_width=True)
        
        st.markdown("---")
        st.subheader("📊 Attendance Summary")
        
        total = len(attendance)
        present = len([a for a in attendance if a['status'] == 'Present'])
        absent = total - present
        percent = (present / total * 100) if total > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Classes", total)
        col2.metric("Present", present)
        col3.metric("Absent", absent)
        col4.metric("Attendance %", f"{percent:.1f}%")
        
        st.write("**Subject-wise Attendance:**")
        subject_summary = df_attendance.groupby('subject')['status'].apply(lambda s: (s == 'Present').sum() / s.count() * 100).reset_index()
        subject_summary.rename(columns={'status': 'Attendance Percentage'}, inplace=True)
        st.bar_chart(subject_summary.set_index('subject'))

    else:
        st.info("No attendance records available yet.")

def student_profile():
    """Student profile page."""
    st.subheader("👤 Your Profile")
    user = st.session_state.current_user
    
    # Use .get() to avoid errors if a key is missing
    st.write(f"**Student ID:** {user.get('student_id', 'N/A')}")
    st.write(f"**Name:** {user.get('first_name', '')} {user.get('last_name', '')}")
    st.write(f"**Email:** {user.get('email', 'N/A')}")
    st.write(f"**Phone:** {user.get('phone', 'N/A')}")
    st.write(f"**Date of Birth:** {user.get('date_of_birth', 'N/A')}")
    st.write(f"**Gender:** {user.get('gender', 'N/A')}")
    st.write(f"**Course:** {user.get('course', 'N/A')}")
    st.write(f"**Year & Semester:** {user.get('year', '')}, {user.get('semester', '')}")
    st.write(f"**Enrollment Date:** {user.get('enrollment_date', 'N/A')}")
    st.write(f"**Status:** {user.get('status', 'N/A')}")

# --- Student Management Section ---
def add_student_form():
    """A form for adding new students with password options."""
    if 'new_student_credentials' in st.session_state:
        creds = st.session_state.new_student_credentials
        st.success("Student added successfully! ✅")
        st.info(f"**Student ID:** `{creds['id']}`")
        if creds['password']:
            st.info(f"**Generated Password:** `{creds['password']}`")
            st.warning("Please copy these credentials and share them securely with the student.")
        del st.session_state.new_student_credentials

    with st.expander("📝 Add New Student", expanded=False):
        
        # --- WIDGETS THAT CONTROL OTHER WIDGETS ARE MOVED OUTSIDE THE FORM ---
        
        # Controller 1: Password Option
        st.write("**Password Options**")
        password_option = st.radio(
            "Choose password method", 
            ("Generate Automatically", "Set Manually"), 
            horizontal=True,
            key="student_pwd_option",
            label_visibility="collapsed"
        )
        
        # Controller 2: Year Selection (This triggers the semester update)
        st.write("**Course Details**")
        year_options = ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        year = st.selectbox("Year*", year_options, key="student_year_selector")

        # The logic to determine semester options now runs immediately when 'year' is changed.
        semester_map = {
            "1st Year": ["1st Semester", "2nd Semester"],
            "2nd Year": ["3rd Semester", "4th Semester"],
            "3rd Year": ["5th Semester", "6th Semester"],
            "4th Year": ["7th Semester", "8th Semester"],
        }
        semester_options = semester_map.get(year, [])
        
        # --- THE FORM ITSELF STARTS HERE ---
        with st.form("add_student_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Personal Details**")
                first_name = st.text_input("First Name*")
                last_name = st.text_input("Last Name*")
                email = st.text_input("Email*")
                phone = st.text_input("Phone Number*")
                date_of_birth = st.date_input("Date of Birth*", value=date.today() - timedelta(days=6570)) # Default to ~18 years
            with col2:
                # The 'year' is already selected outside, so we just show other course fields here.
                st.write("‎") # Empty space for alignment
                gender = st.selectbox("Gender*", ["Male", "Female", "Other"])
                course = st.selectbox("Course*", ["Data Science", "Computer Science", "Machine Learning", "Web Development", "Software Engineering"])
                
                # The semester dropdown now correctly uses the options calculated outside the form.
                semester = st.selectbox("Semester*", semester_options)

            st.markdown("---")
            
            manual_password = ""
            confirm_password = ""
            # This logic correctly shows password fields based on the radio button choice.
            if password_option == "Set Manually":
                st.write("Enter password details:")
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    manual_password = st.text_input("Enter Password*", type="password", key="student_pwd")
                with p_col2:
                    confirm_password = st.text_input("Confirm Password*", type="password", key="student_pwd_confirm")
            
            # The submit button captures all inputs at once.
            submitted = st.form_submit_button("Add Student")
            if submitted:
                # We use the 'year' variable defined outside the form for validation and insertion.
                if not all([first_name, last_name, email, phone, course, year, semester]):
                    st.error("Please fill all required fields marked with *")
                    return
                if not validate_email(email):
                    st.error("Please enter a valid email address.")
                    return

                password = None
                show_password_in_message = False

                if password_option == "Generate Automatically":
                    password = generate_password()
                    show_password_in_message = True
                else: 
                    if not manual_password:
                        st.error("Manual password cannot be empty.")
                        return
                    if manual_password != confirm_password:
                        st.error("Passwords do not match.")
                        return
                    password = manual_password

                if password:
                    try:
                        student_id = generate_student_id()
                        with get_db_connection() as conn:
                            if conn is None: raise Exception("Database connection failed")
                            with conn.begin():
                                conn.execute(text("""
                                    INSERT INTO students (student_id, first_name, last_name, email, phone, date_of_birth, 
                                                          gender, course, year, semester, enrollment_date, password, status)
                                    VALUES (:sid, :fname, :lname, :email, :phone, :dob, :gender, :course, :year, :sem, :edate, :pass, 'Active')
                                """), {
                                    "sid": student_id, "fname": first_name, "lname": last_name, "email": email, "phone": phone,
                                    "dob": date_of_birth, "gender": gender, "course": course, "year": year, "sem": semester,
                                    "edate": date.today(), "pass": hash_password(password)
                                })
                        
                        st.session_state.new_student_credentials = {
                            "id": student_id,
                            "password": password if show_password_in_message else None
                        }
                        st.rerun()
                    except sqlalchemy.exc.IntegrityError as e:
                        if "email" in str(e).lower():
                            st.error("Email already exists!")
                        else:
                            st.error(f"Database error: {e}")
                    except Exception as e:
                        st.error(f"An error occurred: {e}")

def student_management_interface(can_delete=False):
    """A reusable UI component for viewing and managing students."""
    st.markdown("---")
    st.subheader("Student List & Management")
    students = get_all_students()

    if not students:
        st.info("No students found.")
        return

    df_students = pd.DataFrame(students)
    st.dataframe(df_students[['student_id', 'first_name', 'last_name', 'gender', 'course', 'email', 'phone', 'status']], use_container_width=True)

    if 'password_reset_info' in st.session_state:
        info = st.session_state.password_reset_info
        st.success(f"Password for student {info['student_id']} has been reset!")
        st.info(f"**New Generated Password:** `{info['new_password']}`")
        st.warning("Please share this new password with the student securely.")
        del st.session_state.password_reset_info

    student_options = {f"{s['student_id']} - {s['first_name']} {s['last_name']}": s['student_id'] for s in students}
    selected_label = st.selectbox("Select a student to manage", [""] + list(student_options.keys()), key="student_manage_select")

    if selected_label:
        student_id = student_options[selected_label]
        
        with st.expander("🔑 Manage Selected Student", expanded=True):
            st.write(f"**Actions for:** {selected_label}")
            
            if st.button("Generate & Set New Password", key=f"gen_pw_{student_id}"):
                new_pw = generate_password()
                try:
                    with get_db_connection() as conn:
                        if conn is None: raise Exception("Database connection failed")
                        with conn.begin():
                            conn.execute(text("UPDATE students SET password = :pass WHERE student_id = :sid"),
                                         {"pass": hash_password(new_pw), "sid": student_id})
                    st.session_state.password_reset_info = {'student_id': student_id, 'new_password': new_pw}
                    st.rerun()
                except Exception as e:
                    st.error(f"Error resetting password: {e}")

            with st.form(key=f"custom_pw_{student_id}"):
                st.write("Or, set a custom password:")
                custom_pw = st.text_input("New Custom Password", type="password", key=f"custom_pwd_{student_id}")
                if st.form_submit_button("Set Custom Password"):
                    if custom_pw:
                        try:
                            with get_db_connection() as conn:
                                if conn is None: raise Exception("Database connection failed")
                                with conn.begin():
                                    conn.execute(text("UPDATE students SET password = :pass WHERE student_id = :sid"),
                                                 {"pass": hash_password(custom_pw), "sid": student_id})
                            st.success(f"Successfully set a new password for {student_id}.")
                        except Exception as e:
                            st.error(f"Error setting password: {e}")
                    else:
                        st.warning("Password cannot be empty.")
            
            if can_delete:
                st.markdown("---")
                if st.button("🗑️ Delete This Student", type="primary", key=f"del_student_{student_id}"):
                    try:
                        with get_db_connection() as conn:
                            if conn is None: raise Exception("Database connection failed")
                            with conn.begin():
                                conn.execute(text("DELETE FROM students WHERE student_id = :sid"), {"sid": student_id})
                        st.success(f"Student {student_id} has been deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting student: {e}")

def manage_students_admin():
    """Admin interface for managing students."""
    st.subheader("👨‍🎓 Manage Students")
    add_student_form()
    student_management_interface(can_delete=True)

def teacher_manage_students():
    """Teacher interface for managing students."""
    st.subheader("👨‍🎓 Student Management")
    add_student_form()
    student_management_interface(can_delete=False) # Teachers can't delete

# --- Main Application Logic ---
def main():
    """The main function to run the Streamlit application."""
    st.set_page_config(page_title="School Management System", layout="wide", page_icon="🎓")
    
    if 'db_initialized' not in st.session_state:
        st.info("Initializing database... Please wait.")
        if init_database():
            initialize_default_data()
            st.session_state.db_initialized = True
            st.rerun()
        else:
            st.error("DATABASE INITIALIZATION FAILED. Please check your database credentials and ensure the Postgres server is running.")
            st.stop()

    if not st.session_state.get('logged_in'):
        login_page()
    else:
        user_type = st.session_state.user_type
        if user_type == "admin":
            admin_dashboard()
        elif user_type == "teacher":
            teacher_dashboard()
        elif user_type == "student":
            student_dashboard()
        else:
            st.error("Unknown user type. Logging out.")
            logout()

if __name__ == "__main__":
    main()