from flask import Flask, render_template, request, redirect, session, jsonify, flash
import sqlite3
import uuid
import pandas as pd
from datetime import datetime, timedelta
from config import SECRET_CODE
from utils import switch_commission_tier
from datetime import datetime, timedelta
from flask import jsonify, redirect, request, session


# Flask Application
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database Connection
def get_db_connection():
    conn = sqlite3.connect('app.db', timeout=10)  # Increase timeout
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')  # Enable WAL mode
    return conn






@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d'):
    if isinstance(value, datetime):
        return value.strftime(format)
    return value  # Return as-is if not a datetime


# Connect to SQLite database
def get_db_connection():
    conn = sqlite3.connect('app.db', timeout=10)  # Set timeout to prevent lock errors
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')  # Enable WAL for concurrency
    return conn


# Initialize in-memory DataFrame
data = pd.DataFrame({
    'Client': ['John Doe', 'Jane Smith', 'Alice Johnson', 'Bob Brown', 'Charlie Green'],
    'State': ['Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California'],
    'Lead Source': ['TV Callin', 'Facebook', 'Referral', 'Re-Write', 'Weblead'],
    'Date of Birth': ['1960-01-01', '1970-02-02', '1980-03-03', '1990-04-04', '2000-05-05'],
    'Carrier': ['Mutual of Omaha', 'American Amicable', 'Wellabe GW', 'Liberty Bankers', 'Corebridge AIG'],
    'Product': ['Living Promise Level (ages 45-75)',
                'Senior Choice Immediate (Ages 0-79)',
                'Great Assurance Immediate',
                'SIMPL Preferred & Standard',
                'Guaranteed Issue WL'],
    'Annual Premium': [1200, 1500, 900, 1000, 800],
    'Total Commission': [1500, 1800, 1080, 1200, 960],
    'Commision Paid': [1000, 1300, 700, 800, 600],
    'Status Filter': ['Inforce', 'Pending Lapse', 'Lapse', 'Inforce', 'Inforce'],
    'Policy Date': [
        (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'),  # 1 month in the past
        datetime.now().strftime('%Y-%m-%d'),                        # Current month
        (datetime.now() + timedelta(days=20)).strftime('%Y-%m-%d'), # 1 month in the future
        (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'), # 10 days ago
        (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')  # 1 month in the future
    ]
})

# Routes

@app.route('/')
def index():
    """Home page with summary metrics and chart."""
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Fetch agent data
        cursor.execute('SELECT username, commission_level FROM agents WHERE username = ?', (username,))
        agent_data = cursor.fetchone()
        if not agent_data:
            print("Agent not found.")
            return "Agent not found", 404

        commission_level = agent_data['commission_level'].upper()
        commission_rate = 0.05 if commission_level == 'LOA5' else 0.20

        # Total Premium
        cursor.execute('''SELECT COALESCE(SUM(annual_premium), 0) FROM clients WHERE username = ?''', (username,))
        total_premium = cursor.fetchone()[0]

        # Total Commission Paid (Inforce Policies)
        cursor.execute('''SELECT COALESCE(SUM(annual_premium * ?), 0) FROM clients WHERE username = ? AND LOWER(status) = "inforce"''', (commission_rate, username))
        total_commission_paid = cursor.fetchone()[0]

        # Total Policies
        cursor.execute('SELECT COUNT(*) FROM clients WHERE username = ?', (username,))
        total_policies = cursor.fetchone()[0]

        # Fetch month-over-month commission data for chart
        cursor.execute(''' 
            SELECT strftime('%Y-%m', policy_date) AS month, 
                COALESCE(SUM(annual_premium * ?), 0) AS commission_paid
            FROM clients 
            WHERE username = ? 
            GROUP BY strftime('%Y-%m', policy_date) 
            ORDER BY month
        ''', (commission_rate, username))

        month_data = [{'month': row['month'], 'commission_paid': row['commission_paid']} for row in cursor.fetchall()]
        commission_data = month_data  # Reuse month_data for commission data since they have the same structure

        # Ensure that data is always passed as valid lists
        month_data = month_data if month_data else []
        commission_data = commission_data if commission_data else []

        # Format currency values
        total_premium = f"{total_premium:,.2f}"
        total_commission_paid = f"{total_commission_paid:,.2f}"

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return f"Database error: {e}", 500
    finally:
        conn.close()

    # Pass the fetched data to the template for chart rendering
    return render_template(
        'index.html',
        total_policies=total_policies,
        total_premium=total_premium,
        total_commission_paid=total_commission_paid,
        month_data=month_data,
        commission_data=commission_data
    )





@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')  # Render the registration page

    # Handle POST request (registering the user)
    username = request.form.get('username')
    password = request.form.get('password')
    commission_tier = request.form.get('commission_tier', 'LOA5')  # Default to LOA5
    hire_date = request.form.get('hire_date')  # Get the hire date from the form

      # Convert the hire_date to a datetime object
    hire_date_obj = datetime.strptime(hire_date, '%Y-%m-%d')  # Assuming the format is YYYY-MM-DD
    today = datetime.today()
    days_since_hire = (today - hire_date_obj).days

    # If the agent has been with the company for more than 180 days, set commission level to LOA20
    if days_since_hire > 180:
        commission_tier = 'LOA20'

    # Generate secret_code
    secret_code = str(uuid.uuid4())  # Generate unique secret code

    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # Insert new agent with provided hire_date
    cursor.execute("""
        INSERT INTO agents (username, password, commission_level, hire_date, secret_code)
        VALUES (?, ?, ?, ?, ?)
    """, (username, password, commission_tier, hire_date, secret_code))
    conn.commit()
    conn.close()

    return redirect('/login')




# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agents WHERE username = ? AND password = ?",
            (username, password),
        )
        agent = cursor.fetchone()
        conn.close()

        if agent:
            session['username'] = agent['username']
            session['commission_level'] = agent['commission_level']
            return redirect('/')
        return "Invalid username or password", 401

    return render_template('login.html')


# Logout Route
@app.route('/logout')
def logout():
    """Logs out the current user."""
    session.pop('username', None)  # Clear the username from the session
    return redirect('/login')  # Redirect to login page

import json  # Ensure JSON is imported for serializing data.



@app.route('/dashboard')
def dashboard():
    """Dashboard with actionable insights for the logged-in agent."""
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Fetch agent data (including hire_date)
        cursor.execute('SELECT username, commission_level, hire_date FROM agents WHERE username = ?', (username,))
        agent_data = cursor.fetchone()

        if not agent_data:
            return "Agent not found", 404

        # Get commission rate based on commission level
        commission_level = agent_data['commission_level'].upper()
        commission_rate = 0.05 if commission_level == 'LOA5' else 0.20

        # Format the hire date to a more readable format (e.g., 'Jan 01, 2024')
        hire_date_obj = datetime.strptime(agent_data['hire_date'], '%Y-%m-%d')  # Assuming 'YYYY-MM-DD'
        formatted_hire_date = hire_date_obj.strftime('%b %d, %Y')  # Format as 'Jan 01, 2024'

        agent = {
            "username": agent_data['username'],
            "commission_tier": agent_data['commission_level'],
            "hire_date": formatted_hire_date,
        }

        # Total Commissions Paid
        cursor.execute('''
            SELECT COALESCE(SUM(annual_premium * ?), 0)
            FROM clients
            WHERE username = ? AND LOWER(status) = "inforce"
        ''', (commission_rate, username))
        total_commission_paid = cursor.fetchone()[0]

        # Total Commissions Unpaid (Awaiting Funds)
        cursor.execute('''
            SELECT COALESCE(SUM(annual_premium * ?), 0)
            FROM clients
            WHERE username = ? AND LOWER(status) = "awaiting funds"
        ''', (commission_rate, username))
        total_commission_unpaid = cursor.fetchone()[0]

        # Lapsed Policies
        cursor.execute('''
            SELECT COUNT(*)
            FROM clients
            WHERE username = ? AND LOWER(status) = "lapsed"
        ''', (username,))
        lapsed_policies = cursor.fetchone()[0]

        # Missed Commissions (Lapsed Policies)
        cursor.execute('''
            SELECT COALESCE(SUM(annual_premium * ?), 0)
            FROM clients
            WHERE username = ? AND LOWER(status) = "lapsed"
        ''', (commission_rate, username))
        missed_commissions = cursor.fetchone()[0]

        # Average Premium
        cursor.execute('SELECT COALESCE(AVG(annual_premium), 0) FROM clients WHERE username = ?', (username,))
        avg_premium = cursor.fetchone()[0]

        # Placement Rate
        cursor.execute('SELECT COUNT(*) FROM clients WHERE username = ? AND LOWER(status) = "inforce"', (username,))
        paid_policies = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM clients WHERE username = ?', (username,))
        total_policies = cursor.fetchone()[0]

        placement_rate = (paid_policies / total_policies) * 100 if total_policies > 0 else 0

        # Policy Metrics
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM clients 
            WHERE username = ? 
            GROUP BY status
        ''', (username,))
        policy_statuses = {row['status']: row['count'] for row in cursor.fetchall()}

        # Commission Breakdown by Carrier
        cursor.execute('''
            SELECT carrier, COALESCE(SUM(annual_premium * ?), 0) AS total_commission
            FROM clients 
            WHERE username = ?
            GROUP BY carrier
        ''', (commission_rate, username))
        commission_data = [
            {'carrier': row['carrier'], 'total_commission': row['total_commission']}
            for row in cursor.fetchall()
        ]

        # Month-over-Month Commission Trends
        cursor.execute('''
            SELECT strftime('%Y-%m', policy_date) AS month, 
                   COALESCE(SUM(annual_premium * ?), 0) AS commission_paid
            FROM clients 
            WHERE username = ?
            GROUP BY strftime('%Y-%m', policy_date)
            ORDER BY month
        ''', (commission_rate, username))
        month_data = [
            {'month': row['month'] or "N/A", 'commission_paid': row['commission_paid'] or 0}
            for row in cursor.fetchall()
        ] or []

        # Format numeric values for display
        total_commission_paid = f"{total_commission_paid:,.2f}"
        total_commission_unpaid = f"{total_commission_unpaid:,.2f}"
        missed_commissions = f"{missed_commissions:,.2f}"
        avg_premium = f"{avg_premium:,.2f}"
        placement_rate = round(placement_rate, 2)  # Rounded to 2 decimal places

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return f"Database error: {e}", 500
    finally:
        conn.close()

    return render_template(
        'dashboard.html',
        agent=agent,
        missed_commissions=missed_commissions,
        policy_statuses=policy_statuses,
        total_commission_paid=total_commission_paid,
        total_commission_unpaid=total_commission_unpaid,
        lapsed_policies=lapsed_policies,
        avg_premium=avg_premium,
        placement_rate=placement_rate,
        commission_data=commission_data,
        month_data=month_data
    )






@app.route('/clients', methods=['GET'])
def clients():
    """Page to view and filter clients."""
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Fetch agent's commission tier
        cursor.execute("SELECT commission_level FROM agents WHERE username = ?", (username,))
        agent_data = cursor.fetchone()
        if not agent_data:
            return "Agent data not found.", 404
        commission_level = agent_data['commission_level'].upper()
        commission_rate = 0.05 if commission_level == 'LOA5' else 0.20

        # Get the range of years dynamically from policy_date
        cursor.execute("SELECT MIN(strftime('%Y', policy_date)) AS min_year, MAX(strftime('%Y', policy_date)) AS max_year FROM clients WHERE username = ?", (username,))
        year_data = cursor.fetchone()
        min_year = int(year_data['min_year']) if year_data['min_year'] else datetime.now().year
        max_year = int(year_data['max_year']) if year_data['max_year'] else datetime.now().year
        years = [str(year) for year in range(min_year, max_year + 1)]

        # Base query for fetching clients
        query = '''
        SELECT 
            c.id,
            c.client_name,
            c.carrier,
            c.product,
            c.annual_premium,
            c.policy_date,
            c.status
        FROM clients c
        WHERE c.username = ?
        '''
        params = [username]

        # Add filtering options
        month = request.args.get('month', '')
        year = request.args.get('year', '')
        status = request.args.get('status', '')

        if month:
            query += " AND strftime('%m', c.policy_date) = ?"
            params.append(f"{int(month):02d}")  # Convert month to two-digit format
        if year:
            query += " AND strftime('%Y', c.policy_date) = ?"
            params.append(year)
        if status and status != 'all':
            query += " AND c.status = ?"
            params.append(status)

        # Execute query
        cursor.execute(query, params)
        clients_data_raw = cursor.fetchall()
        clients_data = [dict(row) for row in clients_data_raw]

        # Calculate commission due and format fields
        for client in clients_data:
            try:
                annual_premium = float(client.get('annual_premium') or 0.0)
                commission_due = annual_premium * commission_rate
                client['annual_premium'] = f"{annual_premium:,.2f}"
                client['commission_due'] = f"{commission_due:,.2f}"
                client['policy_date'] = datetime.strptime(client['policy_date'], '%Y-%m-%d').strftime('%b %d, %Y')
            except (TypeError, ValueError):
                client['annual_premium'] = "$0.00"
                client['commission_due'] = "$0.00"
                client['policy_date'] = "N/A"

        # Fetch notes for each client
        for client in clients_data:
            cursor.execute("SELECT note_text, created_at FROM notes WHERE client_id = ? ORDER BY created_at DESC", (client['id'],))
            notes = cursor.fetchall()
            client['notes'] = [{'text': note['note_text'], 'created_at': note['created_at']} for note in notes]

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return "Database error occurred.", 500
    finally:
        conn.close()

    # Dropdown options
    statuses = ["all", "Inforce", "Pending Lapse", "Lapse", "Awaiting Funds"]
    

    # Render template
    return render_template(
        'clients.html',
        clients=clients_data,
        statuses=statuses,
        years=years,
        current_month=month,
        current_year=year,
        current_status=status,
    )



@app.route('/client/<int:client_id>')
def client_detail(client_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    client_data = cursor.fetchone()
    conn.close()

    # Debugging: Log retrieved notes
    print(f"Client Notes Retrieved: {client_data['notes']}" if client_data else "Client not found")

    # Render client_detail.html with client data
    return render_template('client_detail.html', client=client_data)



@app.route('/get_notes', methods=['GET'])
def get_notes():
    client_id = request.args.get('client_id')
    if not client_id:
        return jsonify({'notes': [], 'error': 'Client ID is required.'}), 400

    try:
        conn = sqlite3.connect('app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT note_text, created_at FROM notes WHERE client_id = ? ORDER BY created_at DESC", (client_id,))
        notes = cursor.fetchall()

        # Convert the notes to a list of dictionaries
        notes_list = [{'note_text': note['note_text'], 'created_at': note['created_at']} for note in notes]

        return jsonify({'notes': notes_list})
    except sqlite3.Error as e:
        print(f"Database error fetching notes: {e}")
        return jsonify({'notes': [], 'error': 'Database error.'}), 500
    finally:
        conn.close()



@app.route('/update_commission')
def update_commission():
    """Update commission level for LOA5 users who have been with the company for more than 180 days."""
    
    # Connect to the database
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Fetch agents who have LOA5 commission level
        cursor.execute('''
            SELECT username, commission_level, hire_date 
            FROM agents 
            WHERE commission_level = 'LOA5'
        ''')
        
        agents = cursor.fetchall()

        # Get today's date
        today = datetime.today()

        for agent in agents:
            hire_date = datetime.strptime(agent['hire_date'], '%Y-%m-%d')  # Assuming date format is YYYY-MM-DD
            days_since_hire = (today - hire_date).days

            # If the agent has been with the company for more than 180 days
            if days_since_hire > 180:
                # Update commission level to LOA20
                cursor.execute('''
                    UPDATE agents 
                    SET commission_level = 'LOA20' 
                    WHERE username = ?
                ''', (agent['username'],))

                print(f"Updated {agent['username']} to LOA20 (Hire Date: {hire_date}, Days: {days_since_hire})")

        # Commit changes to the database
        conn.commit()
        return "Commission levels updated successfully."

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return f"Database error: {e}", 500
    finally:
        conn.close()


@app.route('/update_payment_status', methods=['POST'])
def update_payment_status():
    client_id = request.form.get('client_id')
    new_status = request.form.get('first_payment_status')

    print(f"Updating status: client_id={client_id}, new_status={new_status}")  # Debug log

    if not client_id or not new_status:
        return "Client ID and Payment Status are required", 400

    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    try:
        # Update the first_payment_status in the database
        cursor.execute(
            'UPDATE clients SET first_payment_status = ? WHERE id = ?',
            (new_status, client_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")  # Log the exact error
        return "Database error", 500
    finally:
        conn.close()

    return redirect('/clients')


@app.route('/update_status', methods=['POST'])
def update_status():
    """Manually update the status of a client."""
    client_id = request.form.get('client_id')
    new_status = request.form.get('new_status')

    if not client_id or not new_status:
        flash("Invalid request. Please provide a client and status.", "danger")
        return redirect('/clients')

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE clients
            SET status = ?
            WHERE id = ?;
        ''', (new_status, client_id))
        conn.commit()

        if cursor.rowcount > 0:
            flash(f"Status for client {client_id} updated to {new_status}.", "success")
        else:
            flash("Failed to update client status. Please try again.", "danger")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        flash("Database error occurred while updating status.", "danger")
    finally:
        conn.close()

    return redirect('/clients')




@app.route('/add_note', methods=['POST'])
def add_note():
    client_id = request.form.get('client_id')
    note_text = request.form.get('note_text', '').strip()

    if not client_id or not note_text:
        flash("Client ID and note text are required.", "danger")
        return redirect('/clients')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert the note into the database
        cursor.execute(
            "INSERT INTO notes (client_id, note_text) VALUES (?, ?)",
            (client_id, note_text)
        )
        conn.commit()

        print(f"Note added for Client {client_id}: {note_text}")  # Debug log

        flash("Note added successfully.", "success")
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        flash("Database error occurred while adding the note.", "danger")
    finally:
        conn.close()

    return redirect('/clients')




@app.route('/update_notes', methods=['POST'])
def update_notes():
    client_id = request.form.get('client_id')
    notes = request.form.get('notes', '').strip()

    if not client_id:
        flash("Client ID is required.", "danger")
        return redirect('/clients')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Append new notes with timestamp
        cursor.execute('''
            UPDATE clients
            SET notes = COALESCE(notes, '') || '\n[' || DATETIME('now') || '] ' || ?
            WHERE id = ?
        ''', (notes, client_id))
        conn.commit()

        flash("Notes updated successfully.", "success")
    except sqlite3.Error as e:
        print(f"Database error during notes update: {e}")
        flash("Database error occurred while updating notes.", "danger")
    finally:
        conn.close()

    return redirect('/clients')




@app.route('/mark_paid', methods=['POST'])
def mark_paid():
    client_id = request.form.get('client_id')
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    try:
        # Update client status to "Inforce"
        cursor.execute('''
            UPDATE clients
            SET status = "Inforce",
                needs_attention = "No Issues",
                policy_effective_date = DATE('now'),
                notes = notes || '\nInitial payment received on ' || DATE('now')
            WHERE id = ?
        ''', (client_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return "Database error", 500
    finally:
        conn.close()
    return redirect('/clients')

@app.route('/mark_ip_missed', methods=['POST'])
def mark_ip_missed():
    client_id = request.form.get('client_id')
    if not client_id:
        return "Client ID is required", 400
    
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    try:
        # Update the client's status to 'Lapse'
        cursor.execute(
            'UPDATE clients SET first_payment_status = "Lapse", needs_attention = "Missed Payment" WHERE id = ?',
            (client_id,)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return "Database error", 500
    finally:
        conn.close()
    
    return redirect('/clients')


@app.route('/add_contact_attempt', methods=['POST'])
def add_contact_attempt():
    client_id = request.form.get('client_id')
    attempt_notes = request.form.get('attempt_notes', '').strip()
    if not client_id:
        return "Client ID is required", 400

    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    try:
        # Increment contact attempts if less than 8
        cursor.execute(
            '''
            UPDATE clients
            SET contact_attempts = CASE 
                WHEN contact_attempts < 8 THEN contact_attempts + 1 
                ELSE contact_attempts
            END,
            attempt_notes = COALESCE(attempt_notes || '\n', '') || ?
            WHERE id = ?
            ''',
            (attempt_notes, client_id)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return "Database error", 500
    finally:
        conn.close()

    return redirect('/clients')


#Delete client route
@app.route('/delete_client', methods=['POST'])
def delete_client():
    if 'username' not in session:
        return redirect('/login')

    client_id = request.form.get('client_id')

    try:
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()

        # Delete client by ID
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        conn.close()

        return redirect('/clients')
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return "Database error", 500



@app.route('/debug')
def debug():
    print(f"Database path: {os.path.abspath('app.db')}")
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables in database:", cursor.fetchall())
    conn.close()
    return "Debug info printed in the terminal."



@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']

    if request.method == 'POST':
        try:
            # Retrieve form data
            client_name = request.form.get('client_name', '').strip()
            date_of_birth = request.form.get('date_of_birth', '').strip()
            carrier = request.form.get('carrier', '').strip()
            product = request.form.get('product', '').strip()
            annual_premium = float(request.form.get('annual_premium', 0))  # Convert to float
            status = request.form.get('status', '').strip()
            policy_date = request.form.get('policy_date', '').strip()
            state = request.form.get('state', '').strip()
            lead_source = request.form.get('lead_source', '').strip()
            notes = request.form.get('notes', '').strip()
            print(f"Notes from form: {notes}")

            # Validate required fields
            if not client_name or not carrier or not product:
                flash("Client name, carrier, and product are required.", "danger")
                return redirect('/add_client')

            # Insert the client into the database
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO clients (client_name, date_of_birth, carrier, product, annual_premium, 
                                     status, policy_date, state, lead_source, notes, username)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (client_name, date_of_birth, carrier, product, annual_premium, 
                  status, policy_date, state, lead_source, notes, username))

            conn.commit()
            flash("Client added successfully!", "success")
            return redirect('/clients')
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            flash("An error occurred while adding the client. Please try again.", "danger")
            return redirect('/add_client')
        except Exception as e:
            print(f"Unexpected error: {e}")
            flash("An unexpected error occurred. Please try again.", "danger")
            return redirect('/add_client')
        finally:
            if 'conn' in locals():
                conn.close()

    try:
        # Fetch carriers and products dynamically
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT carrier FROM carrier_products")
        carriers = [dict(row)["carrier"] for row in cursor.fetchall()]  # Convert Row to Dict

        # Add client route logic for dynamic carrier and product data
        cursor.execute("SELECT carrier, product FROM carrier_products")
        product_data = [{"carrier": row["carrier"], "product": row["product"]} for row in cursor.fetchall()]

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        flash("An error occurred while fetching carriers and products. Please try again.", "danger")
        carriers, product_data = [], []
    finally:
        if 'conn' in locals():
            conn.close()

    # Predefined state and lead source options
    states = get_state_list()
    lead_sources = [
        "TV Inbound Call",
        "Referral",
        "Facebook Ad",
        "Google Ad",
        "Direct Mail",
        "Other"
    ]

    # Render the form
    return render_template('add_client.html', carriers=carriers, product_data=product_data, states=states, lead_sources=lead_sources)




def get_state_list():
    """Return a list of predefined states."""
    return [
        "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
        "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
        "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
        "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
        "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
        "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
        "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
        "Wisconsin", "Wyoming"
    ]


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

