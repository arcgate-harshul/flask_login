from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import yaml
import os

# Initialize the Flask App
app = Flask(__name__)

# --- Configuration ---
# DB Config
db_config = yaml.safe_load(open('db.yaml'))
app.config['MYSQL_HOST'] = db_config['mysql_host']
app.config['MYSQL_USER'] = db_config['mysql_user']
app.config['MYSQL_PASSWORD'] = db_config['mysql_password']
app.config['MYSQL_DB'] = db_config['mysql_db']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Other Config
app.config['SECRET_KEY'] = 'your_super_secret_key'
# Define the path for the upload folder
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Initialize MySQL
mysql = MySQL(app)

# --- User Management Routes ---
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
            flash('Username already exists!', 'danger')
        else:
            cur.execute("INSERT INTO users(username, password) VALUES (%s, %s)", (username, password))
            mysql.connection.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        cur.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.clear()
    return redirect(url_for('login'))

# --- Notes System Routes ---
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
        flash('Folder created!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/folder/<int:folder_id>')
def view_folder(folder_id):
    """Displays files within a specific folder."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM folders WHERE id = %s AND user_id = %s", (folder_id, session['id']))
    folder = cur.fetchone()
    if not folder:
        flash('Folder not found.', 'danger')
        return redirect(url_for('dashboard'))

    cur.execute("SELECT * FROM files WHERE folder_id = %s AND user_id = %s", (folder_id, session['id']))
    files = cur.fetchall()
    cur.close()
    return render_template('folder.html', folder=folder, files=files)

@app.route('/add_file/<int:folder_id>', methods=['POST'])
def add_file(folder_id):
    """Handles creating text files AND uploading files."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # --- Handle Text File Creation ---
    if 'text_file_name' in request.form:
        file_name = request.form['text_file_name']
        if file_name:
            cur.execute("INSERT INTO files (name, content, folder_id, user_id, file_type) VALUES (%s, %s, %s, %s, %s)", 
                        (file_name, '', folder_id, session['id'], 'text'))
            mysql.connection.commit()
            flash('Text file created!', 'success')

    # --- Handle File Upload ---
    if 'uploaded_file' in request.files:
        file = request.files['uploaded_file']
        if file.filename != '':
            # Secure the filename to prevent malicious paths
            filename = secure_filename(file.filename)
            # Create a user-specific directory if it doesn't exist
            user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(session['id']))
            os.makedirs(user_upload_dir, exist_ok=True)
            # Save the file
            file_path = os.path.join(user_upload_dir, filename)
            file.save(file_path)
            
            # Store file info in the database
            db_filepath = os.path.join(str(session['id']), filename) # Store relative path
            cur.execute("INSERT INTO files (name, folder_id, user_id, file_type, filepath) VALUES (%s, %s, %s, %s, %s)",
                        (filename, folder_id, session['id'], 'upload', db_filepath))
            mysql.connection.commit()
            flash('File uploaded successfully!', 'success')

    cur.close()
    return redirect(url_for('view_folder', folder_id=folder_id))


@app.route('/file/<int:file_id>', methods=['GET', 'POST'])
def view_file(file_id):
    """Displays and updates a text file's content."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, session['id']))
    file = cur.fetchone()
    
    if not file or file['file_type'] != 'text':
        flash('File not found or is not a text file.', 'danger')
        cur.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        content = request.form['content']
        cur.execute("UPDATE files SET content = %s WHERE id = %s", (content, file_id))
        mysql.connection.commit()
        flash('File saved!', 'success')
        cur.execute("SELECT * FROM files WHERE id = %s", [file_id])
        file = cur.fetchone()
    
    cur.close()
    return render_template('file.html', file=file)

# --- NEW DOWNLOAD ROUTE ---
@app.route('/download/<int:file_id>')
def download_file(file_id):
    """Handles downloading an uploaded file."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, session['id']))
    file_info = cur.fetchone()
    cur.close()

    if file_info and file_info['file_type'] == 'upload' and file_info['filepath']:
        try:
            # send_from_directory is a secure way to send files
            return send_from_directory(app.config['UPLOAD_FOLDER'], file_info['filepath'], as_attachment=True)
        except FileNotFoundError:
            flash('File not found on server.', 'danger')
            return redirect(url_for('view_folder', folder_id=file_info['folder_id']))
    else:
        flash('File not found or is not downloadable.', 'danger')
        return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
