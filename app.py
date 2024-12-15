from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify
from flask_bcrypt import Bcrypt
from io import StringIO
from webauthn import generate_registration_options, verify_registration_response
from webauthn.helpers import base64url_to_bytes
from datetime import datetime
from dataclasses import asdict
from enum import Enum
import sqlite3
import csv

app = Flask(__name__)
app.secret_key = 'your_secret_key'

bcrypt = Bcrypt(app)  # Initialize Bcrypt


# Database connection
def get_db_connection():
    conn = sqlite3.connect('db.sqlite3')  # Replace with the correct path if needed
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    # Create the `users` table
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL,
                        password TEXT NOT NULL,
                        pin TEXT,
                        face_id TEXT,
                        fingerprint_id TEXT
                    )''')

    # Create the `expenses` table, now including the `notes` field
    conn.execute('''CREATE TABLE IF NOT EXISTS expenses (
                        id INTEGER PRIMARY KEY,
                        description TEXT NOT NULL,
                        amount REAL NOT NULL,
                        category TEXT,
                        date TEXT NOT NULL,
                        notes TEXT,
                        user_id INTEGER,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )''')

    # Create the `webauthn_credentials` table
    conn.execute('''CREATE TABLE IF NOT EXISTS webauthn_credentials (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,  -- Changed to INTEGER for consistency
                        credential_id TEXT NOT NULL,
                        public_key TEXT NOT NULL,
                        sign_count INTEGER NOT NULL
                    )''')

    conn.commit()
    conn.close()

# In-memory "user store" for demonstration purposes
# This will store user data related to WebAuthn (such as credentials).
user_store = {}

# Dummy function to simulate loading credentials from a database
def get_user_credentials(user_id):
    return user_store.get(user_id, [])    
#register biometric route
@app.route('/register_biometric', methods=['POST'])
def register_biometric():
    try:
        # Debug: Print request headers and raw body
        print("Request Headers:", request.headers)
        print("Raw request body:", request.data)

        # Parse the JSON request body
        request_data = request.get_json()
        print("Received request data:", request_data)

        # Extract user_id from the JSON payload
        user_id = request_data.get('user_id')
        print("Raw user_id:", user_id)

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        # Validate user_id
        if not isinstance(user_id, str):
            return jsonify({"error": "user_id must be a string"}), 400

        # Convert user_id to bytes
        user_id_bytes = user_id.encode('utf-8')
        print("Encoded user_id:", user_id_bytes)

        # Generate registration options using WebAuthn library
        options = generate_registration_options(
            rp_name="Your App",
            rp_id="localhost",
            user_id=user_id_bytes,
            user_name="test_user"
        )

        # Serialize the options object to make it JSON-serializable
        def serialize_option(obj):
            if isinstance(obj, bytes):
                return obj.hex()  # Convert bytes to hex string
            elif isinstance(obj, Enum):
                return obj.value  # Convert Enums to their values
            elif hasattr(obj, "__dict__"):
                return {k: serialize_option(v) for k, v in vars(obj).items()}  # Convert objects to dictionaries
            elif isinstance(obj, list):
                return [serialize_option(i) for i in obj]  # Recursively handle lists
            elif isinstance(obj, dict):
                return {k: serialize_option(v) for k, v in obj.items()}  # Recursively handle dictionaries
            else:
                return obj  # Leave other types as is

        # Convert the WebAuthn options into a serializable dictionary
        options_serializable = serialize_option(options)
        print("Serializable registration options:", options_serializable)

        # Send the response back to the client
        return jsonify(options_serializable)

    except ValueError as e:
        print(f"ValueError: {str(e)}")
        return jsonify({"error": f"ValueError: {str(e)}"}), 400
    except Exception as e:
        print(f"Exception: {str(e)}")
        return jsonify({"error": f"Exception: {str(e)}"}), 400

# Get authentication options for the user
@app.route('/get_authentication_options', methods=['POST'])
def get_authentication_options():
    try:
        # Get the user_id from the request (You can also retrieve it from session or cookie)
        request_data = request.get_json()
        user_id = request_data.get('user_id')

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        # Get user credentials from your store (database or session)
        credentials = get_user_credentials(user_id)

        if not credentials:
            return jsonify({"error": "No credentials found for this user"}), 400

        # Generate WebAuthn authentication options
        options = generate_authentication_options(
            rp_id="localhost",
            user_id=user_id.encode('utf-8'),
            allow_credentials=[{
                "id": cred['id'],
                "type": "public-key",
                "transports": ["usb", "nfc", "ble"],
            } for cred in credentials],
        )

        # Serialize options for JSON response (convert bytes to hex)
        def serialize_option(obj):
            if isinstance(obj, bytes):
                return obj.hex()
            elif isinstance(obj, dict):
                return {k: serialize_option(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_option(i) for i in obj]
            else:
                return obj

        options_serializable = serialize_option(options)

        return jsonify(options_serializable)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Verify the biometric authentication assertion (authentication response)
@app.route('/verify_biometric', methods=['POST'])
def verify_biometric():
    try:
        request_data = request.get_json()
        assertion = request_data.get("assertion")
        
        # Convert assertion's data from base64url to bytes
        raw_id = base64url_to_bytes(assertion["rawId"])
        client_data_json = base64url_to_bytes(assertion["response"]["clientDataJSON"])
        authenticator_data = base64url_to_bytes(assertion["response"]["authenticatorData"])
        signature = base64url_to_bytes(assertion["response"]["signature"])

        # Assuming you have a user_store with a user_id and credentials, validate the assertion
        user_id = assertion.get("user_id")
        credentials = get_user_credentials(user_id)
        
        # Use the WebAuthn library to verify the assertion against stored credentials
        is_valid = verify_authentication_assertion(
            assertion_data={
                "raw_id": raw_id,
                "client_data_json": client_data_json,
                "authenticator_data": authenticator_data,
                "signature": signature,
            },
            expected_credentials=credentials
        )

        if is_valid:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# Route for User Registration (optional, not implemented in your current code)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                     (username, hashed_password))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))
    
    return render_template('register.html')


# Route for Home Page (Dashboard)
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    expenses = conn.execute('SELECT * FROM expenses WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template('index.html', expenses=expenses)
# Route for User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            return 'Invalid login credentials'
    
    return render_template('login.html')

# Route for User Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/add_expense_form', methods=['GET'])
def add_expense_form():
    return render_template('add_expense.html')

# Route for add_expense
@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    description = request.form['description']
    amount = float(request.form['amount'])
    category = request.form['category']
    date = request.form['date']
    notes = request.form.get('notes', '')  # Correctly use .get() for optional fields

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO expenses (description, amount, category, date, notes, user_id) VALUES (?, ?, ?, ?, ?, ?)',
        (description, amount, category, date, notes, user_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('index'))


# Route to Update Expense
@app.route('/update_expense/<int:expense_id>', methods=['GET', 'POST'])
def update_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    expense = conn.execute('SELECT * FROM expenses WHERE id = ?', (expense_id,)).fetchone()

    if not expense:
        conn.close()
        return "Expense not found", 404

    if request.method == 'POST':
        # Retrieve form data
        description = request.form['description']
        amount = float(request.form['amount'])
        category = request.form['category']
        date = request.form['date']
        notes = request.form.get('notes', '')  # Handle notes field safely

        # Update the expense
        conn.execute(
            'UPDATE expenses SET description = ?, amount = ?, category = ?, date = ?, notes = ? WHERE id = ?',
            (description, amount, category, date, notes, expense_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('update_expense.html', expense=expense)


# Route to Delete Expense
@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

# Route to View Specific Expense
@app.route('/view_expense/<int:expense_id>', methods=['GET'])
def view_expense(expense_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    expense = conn.execute('SELECT * FROM expenses WHERE id = ? AND user_id = ?', 
                           (expense_id, session['user_id'])).fetchone()
    conn.close()

    if not expense:
        return "Expense not found", 404

    return render_template('view_expense.html', expense=expense)


# Analytics Route
@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    expenses = conn.execute('SELECT * FROM expenses WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()

    categories = {}
    for expense in expenses:
        if expense['category'] in categories:
            categories[expense['category']] += expense['amount']
        else:
            categories[expense['category']] = expense['amount']

    return render_template('analytics.html', categories=categories)

@app.route('/export_csv', methods=['GET'])
def export_csv():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    expenses = conn.execute('SELECT description, amount, category, date FROM expenses WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()

    # Create CSV in memory using StringIO
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Description", "Amount", "Category", "Date"])  # Header
    for expense in expenses:
        writer.writerow([expense['description'], expense['amount'], expense['category'], expense['date']])

    # Generate dynamic file name
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"expenses_{timestamp}.csv"

    # Prepare the response
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

if __name__ == '__main__':
    init_db()  # Initialize the DB when the app starts
    app.run(debug=True)
