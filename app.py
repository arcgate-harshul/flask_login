from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import yaml

# Initialize the Flask App
app = Flask(__name__)

# Configure DB from a YAML file
db_config = yaml.safe_load(open('db.yaml'))
app.config['MYSQL_HOST'] = db_config['mysql_host']
app.config['MYSQL_USER'] = db_config['mysql_user']
app.config['MYSQL_PASSWORD'] = db_config['mysql_password']
app.config['MYSQL_DB'] = db_config['mysql_db']

# A secret key is needed for flashing messages
app.config['SECRET_KEY'] = 'your_secret_key_here' 

# Initialize MySQL
mysql = MySQL(app)

@app.route('/')
def index():
    """Displays the welcome page."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles the login logic."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()
        if user:
            flash('Login Successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# --- NEW SIGNUP ROUTE ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handles the user signup logic."""
    if request.method == 'POST':
        # Get form details
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        
        # Check if user already exists
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        existing_user = cur.fetchone()
        
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('signup'))
        
        # If username is new, insert into database
        cur.execute("INSERT INTO users(username, password) VALUES (%s, %s)", (username, password))
        mysql.connection.commit()
        cur.close()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
        
    # If request is GET, just show the signup page
    return render_template('signup.html')


@app.route('/dashboard')
def dashboard():
    """A simple dashboard page to show after successful login."""
    return "<h1>Welcome to your Dashboard!</h1><p><a href='/login'>Logout</a></p>"

if __name__ == '__main__':
    # Run the app on all available IPs (for Azure VM)
    app.run(host='0.0.0.0', port=5000, debug=True)
