from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import yaml
import os
import time
from agora_token_builder import RtcTokenBuilder

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
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- AGORA CONFIG ---
app.config['AGORA_APP_ID'] = 'eb6bdbc56a9a45d589680734a4e94940'
app.config['AGORA_APP_CERTIFICATE'] = '610a04b272f24461aed01c6a7a719a62'


# Initialize MySQL
mysql = MySQL(app)

# --- Token Generation ---
def generate_agora_token(channel_name, user_id):
    """Generates an Agora token for a user to join a channel."""
    app_id = app.config['AGORA_APP_ID']
    app_certificate = app.config['AGORA_APP_CERTIFICATE']
    # Tokens expire. Set an expiration time in seconds.
    expire_time_in_seconds = 3600
    current_timestamp = int(time.time())
    privilege_expired_ts = current_timestamp + expire_time_in_seconds
    # A role of publisher allows the user to both send and receive video/audio.
    role = 1 # Publisher

    token = RtcTokenBuilder.buildTokenWithUid(app_id, app_certificate, channel_name, user_id, role, privilege_expired_ts)
    return token

# --- User Management Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
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
    session.clear()
    return redirect(url_for('login'))

# --- Notes System Routes ---
@app.route('/dashboard')
def dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    search_query = request.args.get('search', '') # Get search query from URL

    if search_query:
        like_query = f"%{search_query}%"
        cur.execute("SELECT * FROM folders WHERE user_id = %s AND name LIKE %s", (session['id'], like_query))
    else:
        cur.execute("SELECT * FROM folders WHERE user_id = %s", [session['id']])
    
    folders = cur.fetchall()
    cur.close()
    return render_template('dashboard.html', folders=folders, search_query=search_query)

# ... (All your other routes for folders and files remain the same) ...

# --- AGORA VIDEO CALL ROUTES ---
@app.route('/video_call')
def video_call_page():
    """Renders the video call page."""
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    return render_template('video_call.html')

@app.route('/get_token')
def get_token():
    """API endpoint to provide token to the frontend."""
    if 'loggedin' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    # For simplicity, we'll use a fixed channel name.
    # In a real app, you might let users create or join named rooms.
    channel_name = "test_channel"
    user_id = session['id']
    token = generate_agora_token(channel_name, user_id)
    
    return jsonify({
        'token': token, 
        'appId': app.config['AGORA_APP_ID'],
        'channel': channel_name,
        'uid': user_id
    })


# --- ALL OTHER ROUTES (add_folder, view_folder, etc.) ---
# (Keep all your existing routes for file and folder management here)
# I've omitted them for brevity, but you should keep them in your file.

@app.route('/add_folder', methods=['POST'])
def add_folder():
    if 'loggedin' not in session: return redirect(url_for('login'))
    
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
    if 'loggedin' not in session: return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM folders WHERE id = %s AND user_id = %s", (folder_id, session['id']))
    folder = cur.fetchone()
    if not folder:
        flash('Folder not found.', 'danger')
        return redirect(url_for('dashboard'))

    search_query = request.args.get('search', '') # Get search query from URL

    if search_query:
        like_query = f"%{search_query}%"
        cur.execute("SELECT * FROM files WHERE folder_id = %s AND user_id = %s AND name LIKE %s", (folder_id, session['id'], like_query))
    else:
        cur.execute("SELECT * FROM files WHERE folder_id = %s AND user_id = %s", (folder_id, session['id']))
    
    files = cur.fetchall()
    cur.close()
    return render_template('folder.html', folder=folder, files=files, search_query=search_query)

@app.route('/add_file/<int:folder_id>', methods=['POST'])
def add_file(folder_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    cur = mysql.connection.cursor()

    if 'text_file_name' in request.form:
        file_name = request.form['text_file_name']
        if file_name:
            cur.execute("INSERT INTO files (name, content, folder_id, user_id, file_type) VALUES (%s, %s, %s, %s, %s)", 
                        (file_name, '', folder_id, session['id'], 'text'))
            mysql.connection.commit()
            flash('Text file created!', 'success')

    if 'uploaded_file' in request.files:
        file = request.files['uploaded_file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(session['id']))
            os.makedirs(user_upload_dir, exist_ok=True)
            file_path = os.path.join(user_upload_dir, filename)
            file.save(file_path)
            
            db_filepath = os.path.join(str(session['id']), filename)
            cur.execute("INSERT INTO files (name, folder_id, user_id, file_type, filepath) VALUES (%s, %s, %s, %s, %s)",
                        (filename, folder_id, session['id'], 'upload', db_filepath))
            mysql.connection.commit()
            flash('File uploaded successfully!', 'success')

    cur.close()
    return redirect(url_for('view_folder', folder_id=folder_id))

@app.route('/file/<int:file_id>', methods=['GET', 'POST'])
def view_file(file_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
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

@app.route('/download/<int:file_id>')
def download_file(file_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, session['id']))
    file_info = cur.fetchone()
    cur.close()

    if file_info and file_info['file_type'] == 'upload' and file_info['filepath']:
        try:
            return send_from_directory(app.config['UPLOAD_FOLDER'], file_info['filepath'], as_attachment=True)
        except FileNotFoundError:
            flash('File not found on server.', 'danger')
            return redirect(url_for('view_folder', folder_id=file_info['folder_id']))
    else:
        flash('File not found or is not downloadable.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/delete_folder/<int:folder_id>', methods=['POST'])
def delete_folder(folder_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM folders WHERE id = %s AND user_id = %s", (folder_id, session['id']))
    mysql.connection.commit()
    cur.close()
    flash('Folder deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/rename_folder/<int:folder_id>', methods=['POST'])
def rename_folder(folder_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    new_name = request.form['new_name']
    if new_name:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE folders SET name = %s WHERE id = %s AND user_id = %s", (new_name, folder_id, session['id']))
        mysql.connection.commit()
        cur.close()
        flash('Folder renamed successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s AND user_id = %s", (file_id, session['id']))
    file_info = cur.fetchone()
    if file_info:
        if file_info['file_type'] == 'upload' and file_info['filepath']:
            physical_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filepath'])
            if os.path.exists(physical_path):
                os.remove(physical_path)
        
        cur.execute("DELETE FROM files WHERE id = %s", [file_id])
        mysql.connection.commit()
        flash('File deleted successfully.', 'success')
    cur.close()
    return redirect(url_for('view_folder', folder_id=file_info['folder_id']))

@app.route('/rename_file/<int:file_id>', methods=['POST'])
def rename_file(file_id):
    if 'loggedin' not in session: return redirect(url_for('login'))
    new_name = request.form['new_name']
    cur = mysql.connection.cursor()
    cur.execute("SELECT folder_id FROM files WHERE id = %s AND user_id = %s", (file_id, session['id']))
    file_info = cur.fetchone()
    if file_info and new_name:
        cur.execute("UPDATE files SET name = %s WHERE id = %s", (new_name, file_id))
        mysql.connection.commit()
        flash('File renamed successfully.', 'success')
    cur.close()
    return redirect(url_for('view_folder', folder_id=file_info['folder_id']))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
