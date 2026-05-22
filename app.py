from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import base64
import numpy as np
import datetime
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.mobilenet import preprocess_input
import io
from PIL import Image
import random

app = Flask(__name__)
CORS(app)  # Allow frontend access

DB_NAME = "database.db"

# Initialize DB
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                wasteType TEXT NOT NULL,
                amount TEXT NOT NULL,
                date TEXT NOT NULL,
                is_verified INTEGER DEFAULT 0,
                is_collected INTEGER DEFAULT 0,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        
        # New table: user_points (one row per user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        
        # New table: transactions (log of points added/subtracted)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT NOT NULL,      -- 'add' or 'subtract'
                points INTEGER NOT NULL,
                description TEXT,
                date TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        conn.commit()


init_db()

# Load TensorFlow model
model = load_model('waste_classifier.h5')

# Labels and ranges for waste classification
class_names = ['biological', 'mix_waste', 'non_biological']
weight_ranges = {
    'biological': (1000, 35000),
    'non_biological': (10000, 45000),
    'mix_waste': (250000, 750000)
}

def add_points(user_id, points, description="Points added"):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_points SET balance = balance + ? WHERE user_id = ?", (points, user_id))
        cursor.execute("""
            INSERT INTO transactions (user_id, type, points, description, date)
            VALUES (?, 'add', ?, ?, ?)
        """, (user_id, points, description, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

def subtract_points(user_id, points, description="Points subtracted"):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_points SET balance = balance - ? WHERE user_id = ?", (points, user_id))
        cursor.execute("""
            INSERT INTO transactions (user_id, type, points, description, date)
            VALUES (?, 'subtract', ?, ?, ?)
        """, (user_id, points, description, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

# -------------------- ROUTES --------------------

# User Registration Route
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"message": "All fields are required"}), 400

    hashed_pw = generate_password_hash(password)

    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", 
               (name, email, hashed_pw))
            conn.commit()

            user_id = cursor.lastrowid  # get inserted user id

            cursor.execute("INSERT INTO user_points (user_id, balance) VALUES (?, ?)", (user_id, 0))
            conn.commit()
            return jsonify({"message": "Registered successfully!"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"message": "User with this email already exists"}), 409

# User Login Route
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            return jsonify({
                    "message": "Login successful",
                    "name": user["name"],
                    "userId": user["id"],
                    "email": user["email"]  # ✅ Add this
                }), 200

        else:
            return jsonify({"message": "Invalid email or password"}), 401

# Dashboard Route
@app.route("/dashboard/<email>", methods=["GET"])
def get_dashboard(email):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            if not user:
                return jsonify({"message": "User not found"}), 404

            cursor.execute("SELECT balance FROM user_points WHERE user_id = ?", (user["id"],))
            points_row = cursor.fetchone()
            points = points_row["balance"] if points_row else 0

            # Sample mock data for the dashboard
            reports = [
                {"location": "Park", "wasteType": "Plastic", "amount": "2kg"},
                {"location": "Beach", "wasteType": "Glass", "amount": "1.5kg"}
            ]
            collected = [
                {"reportId": 1, "collector": "Worker A"},
                {"reportId": 2, "collector": "Worker B"}
            ]
            notifications = [
                {"message": "You earned 10 points for a report!"},
                {"message": "Your reward has been updated!"}
            ]

            return jsonify({
                "name": user["name"],
                "points": points,
                "reports": reports,
                "collected": collected,
                "notifications": notifications
            })
    except Exception as e:
        print("Error fetching dashboard:", e)
        return jsonify({"message": "Internal server error"}), 500


# Verify Waste Route
@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify(success=False, error="Missing image data"), 400

        # Decode base64 image
        img_base64 = data['image']
        img_bytes = base64.b64decode(img_base64)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img = img.resize((224, 224))

        img_array = image.img_to_array(img)
        img_array = preprocess_input(img_array)
        img_array = np.expand_dims(img_array, axis=0)

        predictions = model.predict(img_array)
        predicted_index = int(np.argmax(predictions))
        confidence = float(np.max(predictions))
        predicted_class = class_names[predicted_index]

        # Estimate random quantity
        weight_min, weight_max = weight_ranges[predicted_class]
        predicted_weight_kg = round(random.uniform(weight_min, weight_max) / 1000, 2)

        return jsonify(success=True, result={
            'wasteType': predicted_class,
            'confidence': confidence,
            'quantity': predicted_weight_kg
        })

    except Exception as e:
        print("Error in /verify:", str(e))
        return jsonify(success=False, error=str(e)), 500

# Submit Report Route (Original working version)
@app.route('/submit-report', methods=['POST'])
def submit_report():
    try:
        data = request.get_json()
        print("Received data in /submit-report:", data)  # <--- Add this line
        location = data.get('location')
        waste_type = data.get('wasteType')
        amount = data.get('amount')
        email = data.get('email')

        if not (location and waste_type and amount and email):
            print("Missing data detected:", location, waste_type, amount, email)  # <--- debug print
            return jsonify(success=False, error="Missing data"), 400

        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get user_id from email
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            if not user:
                return jsonify(success=False, error="User not found"), 404

            user_id = user["id"]

            cursor.execute("""
                INSERT INTO reports (location, wasteType, amount, date, user_id)
                VALUES (?, ?, ?, ?, ?)
            """, (location, waste_type, amount, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
            conn.commit()

        return jsonify(success=True, message="Report submitted successfully.")
    except Exception as e:
        print("Error in /submit-report:", str(e))
        return jsonify(success=False, error=str(e)), 500


# Get Recent Reports Route
@app.route('/recent-reports', methods=['GET'])
def recent_reports():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    reports.location,
                    reports.wasteType,
                    reports.amount,
                    reports.date,
                    reports.user_id,
                    users.name AS userName,
                    reports.is_verified,
                    reports.is_collected
                FROM reports
                LEFT JOIN users ON reports.user_id = users.id
                ORDER BY reports.date DESC
            """)
            reports_data = cursor.fetchall()

        reports_list = []
        for report in reports_data:
            reports_list.append({
                'location': report['location'],
                'wasteType': report['wasteType'],
                'amount': report['amount'],
                'date': report['date'],
                'userId': report['user_id'],
                'userName': report['userName'],
                'isVerified': report['is_verified'],
                'isCollected': report['is_collected']
            })

        return jsonify(reports=reports_list)
    except Exception as e:
        print("Error in /recent-reports:", str(e))
        return jsonify(success=False, error=str(e)), 500

# admin reward    
@app.route('/reward-list', methods=['GET'])
def reward_list():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT users.id, users.name, IFNULL(user_points.balance, 0) AS points
                FROM users
                LEFT JOIN user_points ON users.id = user_points.user_id
            """)
            users = cursor.fetchall()

        rewards = []
        for user in users:
            rewards.append({
                "userId": user["id"],
                "userName": user["name"],
                "points": user["points"]
            })

        return jsonify({"rewards": rewards})

    except Exception as e:
        print("Error in /reward-list:", str(e))
        return jsonify(success=False, error=str(e)), 500


@app.route('/reward-user', methods=['POST'])
def reward_user():
    try:
        data = request.get_json()
        user_id = data.get("userId")
        points = data.get("points")
        description = data.get("description", "Admin reward")

        if not user_id or not points:
            return jsonify(success=False, error="Missing userId or points"), 400

        add_points(user_id, int(points), description)
        return jsonify(success=True, message=f"{points} points added to user {user_id}")

    except Exception as e:
        print("Error in /reward-user:", str(e))
        return jsonify(success=False, error=str(e)), 500

@app.route('/add-reward', methods=['POST'])
def add_reward():
    try:
        data = request.get_json()
        username = data.get("username")
        points = data.get("points", 50)
        if not username:
            return jsonify(success=False, error="Missing username"), 400

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE name = ?", (username,))
            user = cursor.fetchone()
            if not user:
                return jsonify(success=False, error="User not found"), 404

            user_id = user[0]
            add_points(user_id, points, "Auto reward from admin panel")
            return jsonify(success=True, message=f"{points} points added to {username}")

    except Exception as e:
        print("Error in /add-reward:", str(e))
        return jsonify(success=False, error=str(e)), 500


@app.route('/remove-reward', methods=['POST'])
def remove_reward():
    try:
        data = request.get_json()
        username = data.get("username")
        points = data.get("points", 50)
        if not username:
            return jsonify(success=False, error="Missing username"), 400

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE name = ?", (username,))
            user = cursor.fetchone()
            if not user:
                return jsonify(success=False, error="User not found"), 404

            user_id = user[0]
            subtract_points(user_id, points, "Reward removed from admin panel")
            return jsonify(success=True, message=f"{points} points removed from {username}")

    except Exception as e:
        print("Error in /remove-reward:", str(e))
        return jsonify(success=False, error=str(e)), 500

@app.route('/update-toggle', methods=['POST'])
def update_toggle():
    try:
        data = request.get_json()
        user_id = data.get('userId')
        waste_type = data.get('wasteType')
        amount = data.get('amount')
        field = data.get('field')  # 'is_verified' or 'is_collected'
        value = data.get('value')  # true or false

        if field not in ['is_verified', 'is_collected']:
            return jsonify(success=False, error="Invalid field"), 400

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE reports 
                SET {field} = ? 
                WHERE user_id = ? AND wasteType = ? AND amount = ?
            """, (1 if value else 0, user_id, waste_type, amount))
            conn.commit()

        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/get-toggle-state', methods=['GET'])
def get_toggle_state():
    user_id = request.args.get('userId')
    waste_type = request.args.get('wasteType')
    amount = request.args.get('amount')

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_verified, is_collected 
            FROM reports 
            WHERE user_id = ? AND wasteType = ? AND amount = ?
        """, (user_id, waste_type, amount))
        result = cursor.fetchone()

        if result:
            return jsonify({
                'verified': bool(result[0]),
                'collected': bool(result[1])
            })
        else:
            return jsonify({'verified': False, 'collected': False})



# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)
