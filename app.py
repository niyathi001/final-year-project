from flask import Flask, render_template, request, redirect, url_for, session,flash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# MySQL connection
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="123456",
    database="customer_table"
)
cursor = conn.cursor()

# Ensure users table exists
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100) UNIQUE,
        password VARCHAR(255)
    )
""")
conn.commit()

# ---------------- Routes ---------------- #

@app.route('/')
def home_page():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Optional: Hash password (only if you want to secure it)
        # from werkzeug.security import generate_password_hash
        # password = generate_password_hash(password)

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, password)
            )
            conn.commit()
            flash("✅ Registration successful! Please log in.", "success")
            return redirect(url_for('login_page'))
        except mysql.connector.IntegrityError:
            flash("❌ Error: Email already registered!", "danger")
            return render_template('register.html')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    next_page = request.args.get('next')  # Get 'next' from URL

    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        cursor.execute(
            "SELECT * FROM users WHERE LOWER(email) = %s AND password = %s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            if next_page == 'blog':
                return redirect(url_for('blog_page'))  # Redirect to blog if asked
            return redirect(url_for('view_plants'))  # Default after normal login
        else:
            return "❌ Invalid Email or Password!"
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home_page'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/plantabout')
def plantsabout():
    return render_template('plantsabout.html')

@app.route('/plants')
def view_plants():
    cursor.execute("SELECT * FROM plants")
    plants = cursor.fetchall()
    return render_template('plants.html', plants=plants)

@app.route('/payment', methods=['POST'])
def payment():
    plant_id = request.form['plant_id']
    cursor.execute("SELECT * FROM plants WHERE id = %s", (plant_id,))
    plant = cursor.fetchone()
    return render_template('payment.html', plant=plant)

@app.route('/confirm', methods=['POST'])
def confirm():
    plant_id = request.form['plant_id']
    price = request.form['price']
    user_id = session.get('user_id')

    if user_id is None:
        return "❌ Error: User session expired. Please log in again."

    cursor.execute("UPDATE plants SET stock = stock - 1 WHERE id = %s", (plant_id,))
    cursor.execute(
        "INSERT INTO purchases (user_id, plant_id) VALUES (%s, %s)",
        (user_id, plant_id)
    )
    conn.commit()

    return render_template('confirm.html', plant_id=plant_id, price=price)

@app.route('/history')
def order_history():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login_page'))

    cursor.execute("""
        SELECT p.name, p.category, p.price, p.description, pur.purchase_date, p.id
        FROM purchases pur
        JOIN plants p ON pur.plant_id = p.id
        WHERE pur.user_id = %s
        ORDER BY pur.purchase_date DESC
    """, (user_id,))
    orders = cursor.fetchall()
    return render_template('history.html', orders=orders)

@app.route('/add-task/<plant_name>', methods=['GET', 'POST'])
def add_task_reminder(plant_name):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    success = False

    if request.method == 'POST':
        task_type = request.form['task_type']
        task_date = request.form['task_date']
        notes = request.form['notes']
        user_id = session['user_id']

        cursor.execute("""
            INSERT INTO task_reminders (user_id, plant_name, task_type, task_date, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, plant_name, task_type, task_date, notes))
        conn.commit()
        success = True

    return render_template('add_task.html', plant_name=plant_name, success=success)

@app.route('/tasks')
def view_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user_id = session['user_id']
    cursor.execute("""
        SELECT id, plant_name, task_type, task_date, notes
        FROM task_reminders
        WHERE user_id = %s AND task_date >= CURDATE()
        ORDER BY task_date ASC
    """, (user_id,))
    tasks = cursor.fetchall()
    return render_template('tasks.html', tasks=tasks)

@app.route('/request-service/<plant_name>', methods=['GET', 'POST'])
def request_service(plant_name):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        service_type = request.form['service_type']
        preferred_date = request.form['preferred_date']
        notes = request.form['notes']
        user_id = session['user_id']

        cursor.execute("""
            SELECT id, name FROM employees
            WHERE specialization LIKE %s
            ORDER BY RAND() LIMIT 1
        """, ('%' + service_type + '%',))
        employee = cursor.fetchone()

        if not employee:
            return "<h3 style='color:red;'>❌ No employee available for this service right now.</h3>"

        employee_id, employee_name = employee

        cursor.execute("""
            INSERT INTO plant_services (user_id, plant_name, service_type, preferred_date, notes, employee_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, plant_name, service_type, preferred_date, notes, employee_id))
        conn.commit()

        return f"<h3 style='color:green;'>✅ Your service request has been submitted!<br>👨‍🌾 Employee <strong>{employee_name}</strong> has been assigned and will contact you soon.</h3>"

    return render_template('request_service.html', plant_name=plant_name)


@app.route('/my-services')
def my_services():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login_page'))

    cursor.execute("""
        SELECT plant_name, service_type, preferred_date, e.name
        FROM plant_services ps
        JOIN employees e ON ps.employee_id = e.id
        WHERE ps.user_id = %s
        ORDER BY preferred_date ASC
    """, (user_id,))
    services = cursor.fetchall()

    return render_template('services.html', services=services)


@app.route('/blog', methods=['GET', 'POST'])
def blog_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    user_id = session['user_id']
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        cursor.execute(
            "INSERT INTO posts (user_id, title, content) VALUES (%s, %s, %s)",
            (user_id, title, content)
        )
        conn.commit()
        return redirect(url_for('blog_page'))

    cursor.execute("""
        SELECT p.title, p.content, p.created_at, u.name
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
    """)
    posts = cursor.fetchall()

    return render_template('blog.html', posts=posts)

@app.route('/contact', methods=['GET', 'POST'])
def contact_page():
    if request.method == 'POST':
        user_email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        # Simulate email handling (you can add actual email sending later)
        print(f"New contact message from {user_email}")
        print(f"Subject: {subject}")
        print(f"Message: {message}")

        flash("✅ Your message has been sent! We’ll get back to you soon.", "success")
        return redirect(url_for('contact_page'))

    return render_template('contact.html')

@app.route('/caretips')
def care_tips():
    return render_template('caretips.html')


# ---------------- Start Server ---------------- #
if __name__ == '__main__':
    app.run(debug=True)
