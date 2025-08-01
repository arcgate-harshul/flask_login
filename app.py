from flask import Flask, render_template, request, redirect, url_for, flash, session
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
# Cursors by default return tuples. This will return dictionaries, which are easier to work with.
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' 

# A secret key is needed for sessions and flashing messages
app.config['SECRET_KEY'] = 'your_super_secret_key' 

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
            # Store user info in the session
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handles the user signup logic."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        if cur.fetchone():
            flash('Username already exists. Please choose a different one.', 'danger')
        else:
            cur.execute("INSERT INTO users(username, password) VALUES (%s, %s)", (username, password))
            mysql.connection.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        cur.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

# --- NEW DASHBOARD AND NOTES ROUTES ---

@app.route('/dashboard')
def dashboard():
    """Displays user's folders."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM folders WHERE user_id = %s", [session['id']])
    folders = cur.fetchall()
    cur.close()
    return render_template('dashboard.html', folders=folders)

@app.route('/add_folder', methods=['POST'])
def add_folder():
    """Adds a new folder for the user."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    folder_name = request.form['folder_name']
    if folder_name:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO folders (name, user_id) VALUES (%s, %s)", (folder_name, session['id']))
        mysql.connection.commit()
        cur.close()
        flash('Folder created successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/folder/<int:folder_id>')
def view_folder(folder_id):
    """Displays files within a specific folder."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    # Ensure the user owns the folder they are trying to view
    cur.execute("SELECT * FROM folders WHERE id = %s AND user_id = %s", (folder_id, session['id']))
    folder = cur.fetchone()
    if not folder:
        flash('Folder not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('dashboard'))

    cur.execute("SELECT * FROM files WHERE folder_id = %s AND user_id = %s", (folder_id, session['id']))
    files = cur.fetchall()
    cur.close()
    return render_template('folder.html', folder=folder, files=files)

@app.route('/add_file/<int:folder_id>', methods=['POST'])
def add_file(folder_id):
    """Adds a new file to a folder."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    file_name = request.form['file_name']
    if file_name:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO files (name, content, folder_id, user_id) VALUES (%s, %s, %s, %s)", 
                    (file_name, '', folder_id, session['id']))
        mysql.connection.commit()
        cur.close()
        flash('File created successfully!', 'success')
    return redirect(url_for('view_folder', folder_id=folder_id))

@app.route('/file/<int:file_id>', methods=['GET', 'POST'])
def view_file(file_id):
    """Displays and updates a file's content."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    # Ensure the user owns the file they are trying to access
    cur.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, session['id']))
    file = cur.fetchone()
    if not file:
        flash('File not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        content = request.form['content']
        cur.execute("UPDATE files SET content = %s WHERE id = %s", (content, file_id))
        mysql.connection.commit()
        flash('File saved successfully!', 'success')
        # Refetch the file to show updated content
        cur.execute("SELECT * FROM files WHERE id = %s", [file_id])
        file = cur.fetchone()
    
    cur.close()
    return render_template('file.html', file=file)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
