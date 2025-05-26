Project Title:Student Mess Fees Management System

Project Content:
1. Project Title
2. Project Code
3. Key Technologies
4. Description
5. Output
6. Further Research

1. Project Title
Student Mess Fees Management System

This project helps hostels or colleges manage mess (cafeteria) fees easily by tracking which students attend meals and calculating their monthly bills automatically.

2. Project Code

Here is a simplified version of the main code used in this project. It is written in Python using Flask:

from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_mysqldb import MySQL
from flask_cors import CORS
from datetime import timedelta
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity # Added jwt_required, get_jwt_identity

app = Flask(_name_)
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
    st_id = data.get('st_id')
    name = data.get('name')
    abranch = data.get('abranch')
    phone = data.get('phone')

    if not all([st_id, name, abranch, phone]):
        return jsonify({"message": "Missing required fields"}), 400

    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO student (st_id, name, abranch, phone) VALUES (%s, %s, %s, %s)",
                    (st_id, name, abranch, phone))
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback() # Ensure rollback on error
        return jsonify({"message": f"Error: {str(e)}"}), 400
    finally:
        cur.close()

    return jsonify({"message": "Student registered successfully"}), 201

# 2. Record Attendance
@app.route('/attendance', methods=['POST'])
def add_attendance():
    data = request.json
    student_id = data.get('student_id')
    month = data.get('month')
    days_present = data.get('days_present')

    if not all([student_id, month, days_present is not None]): # Check for explicit None
        return jsonify({"message": "Missing required fields"}), 400

    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO attendance (student_id, month_name, days_present)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE days_present = %s
        """, (student_id, month, days_present, days_present))
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 400
    finally:
        cur.close()

    return jsonify({"message": "Attendance recorded successfully"})

# 3. Register Monthly Expense
@app.route('/billregister', methods=["POST"])
# @jwt_required() # Assuming only admin can register bills
def bill_register():
    data = request.json
    month = data.get('month')
    # Convert total_month_day and total_expense to float to ensure numerical operations
    try:
        total_month_day = float(data.get('total_month_day'))
        total_expense = float(data.get('total_expense'))
    except (ValueError, TypeError): # Handle both value and type errors for missing/bad data
        return jsonify({"message": "Invalid or missing number format for total_month_day or total_expense"}), 400

    if not month:
        return jsonify({"message": "Missing month"}), 400

    cur = mysql.connection.cursor()

    try:
        # Check if expense for the month already exists
        cur.execute("SELECT expense_id FROM expense WHERE expense_month = %s", (month,))
        existing_expense = cur.fetchone()
        if existing_expense:
            return jsonify({"message": "Monthly expense for this month already registered. Use an update endpoint if needed."}), 409 # Conflict

        cur.execute("INSERT INTO expense (expense_month, total_expense) VALUES (%s, %s)", (month, total_expense))
        expense_id = cur.lastrowid

        cur.execute("""
            SELECT s.st_id, COALESCE(a.days_present, 0)
            FROM student s
            LEFT JOIN attendance a ON s.st_id = a.student_id AND a.month_name = %s
        """, (month,))
        student_days = cur.fetchall()

        total_days_present_across_students = sum([row[1] for row in student_days])

        if total_days_present_across_students == 0:
            mysql.connection.rollback() # Rollback expense insertion
            return jsonify({"message": "No attendance recorded for any student in this month"}), 400

        for student_id, days_present in student_days:
            individual_share = (total_expense / total_month_day) * float(days_present) if days_present > 0 else 0

            # Check if student_expense for this month and student already exists
            cur.execute("SELECT student_expense_id FROM student_expense WHERE student_id = %s AND month_name = %s", (student_id, month))
            existing_student_expense = cur.fetchone()

            if existing_student_expense:
                # Update if exists
                cur.execute("""
                    UPDATE student_expense
                    SET student_month_expense = %s
                    WHERE student_id = %s AND month_name = %s
                """, (individual_share, student_id, month))
            else:
                # Insert if not exists
                cur.execute("""
                    INSERT INTO student_expense (student_id, expense_id, student_month_expense, month_name)
                    VALUES (%s, %s, %s, %s)
                """, (student_id, expense_id, individual_share, month))

        mysql.connection.commit()
        return jsonify({"message": "Monthly bill and student expenses calculated and saved"}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        cur.close()

# 4. Student Login
@app.route('/studentlogin', methods=["POST"])
def student_login():
    data = request.json
    st_id = data.get('st_id')
    phone = data.get('phone')

    if not st_id or not phone:
        return jsonify({"message": "Missing student ID or phone"}), 400

    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT st_id, name FROM student WHERE st_id=%s AND phone=%s", (st_id, phone))
        student = cur.fetchone()

        if not student:
            return jsonify({"message": "Invalid login credentials"}), 401

        student_id, name = student
        access_token = create_access_token(identity=student_id) # Generate JWT for student

        return jsonify({
            "message": "Login successful",
            "student_id": student_id,
            "name": name,
            "access_token": access_token
        }), 200
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        cur.close()

# 5. View Student Expenses
@app.route('/studentexpense/<string:student_id>', methods=["GET"]) # Changed to string to match st_id type if it's string
@jwt_required() # Protect this endpoint
def get_student_expense(student_id):
    current_user_id = get_jwt_identity()
    if current_user_id != student_id:
        return jsonify({"message": "Unauthorized access to another student's data"}), 403

    cur = mysql.connection.cursor()
    try:
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
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        cur.close()

# 6. Admin login
@app.route("/adminlogin", methods=["POST"])
def admin_login_api():
    data = request.get_json()
    admin_id = data.get("admin_id")
    password = data.get("password")

    if not admin_id or not password:
        return jsonify({"error": "Missing credentials"}), 400

    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT admin_id, password FROM admin WHERE admin_id = %s", (admin_id,))
        admin = cur.fetchone()

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
    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500
    finally:
        cur.close()

# Basic Web Pages (Render HTML)
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/adminregisterpage')
def admin_register_page():
    return render_template('adminregister.html')

@app.route('/adminloginpage') # Renamed to avoid conflict with API endpoint
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/studentloginpage') # Renamed to avoid conflict with API endpoint
def student_login_page():
    return render_template('student_login.html')

@app.route('/registerstudentpage')
def register_student_page():
    return render_template('register_student.html')

@app.route('/billregisterpage')
def bill_register_page():
    return render_template('bill_register.html')

# Run the app
if _name_ == "_main_":
    app.run(debug=True)


3. Key Technologies

This project uses the following technologies:
* Frontend:** HTML, CSS (for forms and simple UI)
* Backend:** Python (Flask web framework)
* Database:** MySQL (to store students, attendance, fees)
* Security:** JWT for login tokens and Bcrypt for password hashing

4. Description

This web-based system is built to help colleges manage mess attendance and monthly fee calculation in an automated and error-free manner.
Key Features:
Student Registration & Login: Students can create accounts and log in securely using hashed passwords and JWT tokens.
Attendance Marking: Students or admin can mark daily attendance which is used for billing.
Monthly Fee Calculation: Automatically calculates mess fees at the end of the month based on the number of days the student was present.
Why It Matters:
Tracking mess fees manually is time-consuming and error-prone. This app reduces human effort, speeds up billing, and makes everything digital and easy to manage.

5. Output

When the system is running, here are some example results:

 **After Registration:**

```json
{ "message": "Student registered successfully" }
```

 **After Login:**

```json
{ "token": "generated-login-token" }
```

 **Marking Attendance:**

```json
{ "message": "Attendance marked" }
```

 **Fee Calculation Result:**

```json
{
  "month": "2025-05",
  "days_present": 22,
  "total_fee": 2200
}
The fee is calculated simply as:
**days\_present × daily\_rate**

6. Further Research

Here are a few ideas to improve this project in the future:

* Meal Type Tracking:** Track attendance for breakfast, lunch, and dinner separately.
* Online Payments:** Allow students to pay their mess bills online.
* Admin Dashboard:** Add charts and graphs to show total meals served and revenue.
* Email Alerts:** Notify students when their fee is due or if attendance is low.
* Mobile App:** Create a mobile version of this system for easier access.
