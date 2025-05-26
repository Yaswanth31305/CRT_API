from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_mysqldb import MySQL
from flask_cors import CORS
from datetime import timedelta
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token

app = Flask(__name__)  # ✅ Fixed typo here
CORS(app)  
# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'student_expense_db1'
app.config['JWT_SECRET_KEY'] = 'messbillcalculation' 
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=10) 

mysql = MySQL(app)
bcrypt = Bcrypt(app)

 
jwt = JWTManager(app)

# 1. Register Student
@app.route('/registerstudent', methods=["POST"])
def register_student():
    data = request.json
    st_id = data['st_id']
    name = data['name']
    abranch = data['abranch']
    phone = data['phone']

    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO student (st_id, name, abranch, phone) VALUES (%s, %s, %s, %s)",
                    (st_id, name, abranch, phone))
        mysql.connection.commit()
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 400

    return jsonify({"message": "Student registered successfully"}), 201

# 2. Record Attendance
@app.route('/attendance', methods=['POST'])
def add_attendance():
    data = request.json
    student_id = data['student_id']
    month = data['month']
    days_present = data['days_present']

    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO attendance (student_id, month_name, days_present)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE days_present = %s
        """, (student_id, month, days_present, days_present))
        mysql.connection.commit()
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 400

    return jsonify({"message": "Attendance recorded successfully"})

# 3. Register Monthly Expense
@app.route('/billregister', methods=["POST"])
def bill_register():
    data = request.json
    month = data['month']
    # Convert total_month_day and total_expense to float to ensure numerical operations
    try:
        total_month_day = float(data['total_month_day'])
        total_expense = float(data['total_expense'])
    except ValueError:
        return jsonify({"message": "Invalid number format for total_month_day or total_expense"}), 400

    cur = mysql.connection.cursor()

    try:
        cur.execute("INSERT INTO expense (expense_month, total_expense) VALUES (%s, %s)", (month, total_expense))
        expense_id = cur.lastrowid

        cur.execute("""
            SELECT s.st_id, COALESCE(a.days_present, 0)
            FROM student s
            LEFT JOIN attendance a ON s.st_id = a.student_id AND a.month_name = %s
        """, (month,))
        student_days = cur.fetchall()

        total_days_present = sum([row[1] for row in student_days])

        if total_days_present == 0:
            return jsonify({"message": "No attendance recorded for any student in this month"}), 400

        for student_id, days_present in student_days:
            # Ensure days_present is also treated as a number for calculation
            individual_share = (total_expense / total_month_day) * float(days_present) if days_present > 0 else 0

            cur.execute("""
                INSERT INTO student_expense (student_id, expense_id, student_month_expense, month_name)
                VALUES (%s, %s, %s, %s)
            """, (student_id, expense_id, individual_share, month))

        mysql.connection.commit()
        return jsonify({"message": "Monthly bill and student expenses calculated and saved"}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500


# 4. Student Login 
@app.route('/studentlogin', methods=["POST"])
def student_login():
    data = request.json
    st_id = data.get('st_id')
    phone = data.get('phone')

    if not st_id or not phone:
        return jsonify({"message": "Missing student ID or phone"}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT st_id, name FROM student WHERE st_id=%s AND phone=%s", (st_id, phone))
    student = cur.fetchone()

    if not student:
        return jsonify({"message": "Invalid login credentials"}), 401

    student_id, name = student

    # Optionally generate a token here if needed (JWT etc.)
    return jsonify({
        "message": "Login successful",
        "student_id": student_id,
        "name": name
    }), 200

# 5. View Student Expenses
@app.route('/studentexpense/<int:student_id>', methods=["GET"])
def get_student_expense(student_id):
    cur = mysql.connection.cursor()
    
    # Optionally verify the student exists (for cleaner error handling)
    cur.execute("SELECT name FROM student WHERE st_id=%s", (student_id,))
    student = cur.fetchone()

    if not student:
        return jsonify({"message": "Student not found"}), 404

    cur.execute("""
        SELECT month_name, student_month_expense
        FROM student_expense
        WHERE student_id=%s
        ORDER BY month_name
    """, (student_id,))
    expenses = cur.fetchall()

    history = [{"month": row[0], "amount": float(row[1])} for row in expenses]

    return jsonify({
        "student_id": student_id,
        "name": student[0],
        "expense_history": history
    }), 200

# 6. Admin login
@app.route("/adminlogin", methods=["POST"])
def admin_login_api():
    data = request.get_json()
    admin_id = data.get("admin_id")
    password = data.get("password")

    if not admin_id or not password:
        return jsonify({"error": "Missing credentials"}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT admin_id, password FROM admin WHERE admin_id = %s", (admin_id,))
    admin = cur.fetchone()
    cur.close()

    if not admin:
        return jsonify({"error": "Admin not found"}), 404

    db_admin_id, password_hash = admin

    if bcrypt.check_password_hash(password_hash, password):
        access_token = create_access_token(identity=db_admin_id)
        return jsonify({
            "message": "Admin login successful",
            "access_token": access_token
        }), 200
    else:
        return jsonify({"error": "Invalid password"}), 401

if __name__ == "__main__":
    app.run(debug=True)

# Basic Web Pages (Render HTML)
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/adminregisterpage')
def admin_register_page():
    return render_template('adminregister.html')  

@app.route('/adminlogin')
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/studentlogin')
def student_login_page():
    return render_template('student_login.html')

@app.route('/registerstudentpage')
def register_student_page():
    return render_template('register_student.html')

@app.route('/billregisterpage')
def bill_register_page():
    return render_template('bill_register.html')

# Run the app
if __name__ == '__main__':
    app.run(debug=True)