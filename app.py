from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import yaml

# Initialize the Flask App
app = Flask(__name__)

# Configure DB from a YAML file
# It's better to keep credentials out of the code.
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
    """
    Handles the login logic.
    GET: Displays the login form.
    POST: Processes the submitted credentials.
    """
    if request.method == 'POST':
        # Get form details
        username = request.form['username']
        password = request.form['password']

        # Create a cursor to execute SQL queries
        cur = mysql.connection.cursor()

        # Fetch the user from the database
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()

        if user:
            # If user is found, redirect to a success page
            flash('Login Successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            # If user is not found, show an error
            flash('Invalid credentials. Please try again.', 'danger')
            return redirect(url_for('login'))

    # If the request is GET, just show the login page
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """A simple dashboard page to show after successful login."""
    return "<h1>Welcome to your Dashboard!</h1><p><a href='/login'>Logout</a></p>"

if __name__ == '__main__':
    # Run the app on all available IPs (for Azure VM)
    app.run(host='0.0.0.0', port=5000, debug=True)
