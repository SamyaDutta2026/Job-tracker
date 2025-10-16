# app.py (Corrected Version)
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from math import ceil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_for_your_app_super_secure'

# --- DATABASE AND AUTHENTICATION ---
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(id=user_data['id'], username=user_data['username'], password=user_data['password'])
    return None

def get_db_connection():
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- CHART GENERATION ---
def get_plot_base64(df, plot_type='status', theme='light'):
    bg_color = '#ffffff' if theme == 'light' else '#2b2b4d'
    text_color = '#333333' if theme == 'light' else '#e0e0e0'
    plt.style.use('default' if theme == 'light' else 'dark_background')
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    colors = ['#0d6efd', '#6f42c1', '#d63384', '#fd7e14', '#198754'] if theme == 'light' else ['#e94560', '#1abc9c', '#f1c40f', '#3498db', '#e74c3c']
    if plot_type == 'status':
        status_counts = df['status'].value_counts()
        ax.bar(status_counts.index, status_counts.values, color=colors)
        ax.set_title('Applications by Status', color=text_color)
        ax.set_ylabel('Count', color=text_color)
    elif plot_type == 'company':
        top_companies = df['company_name'].value_counts().head(5)
        ax.barh(top_companies.index, top_companies.values, color=colors[0])
        ax.set_title('Top 5 Companies', color=text_color)
        ax.set_xlabel('Count', color=text_color)
        ax.invert_yaxis()
    ax.tick_params(axis='x', colors=text_color)
    ax.tick_params(axis='y', colors=text_color)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

# --- AUTH ROUTES ---
@app.route('/')
def index():
    return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        conn = get_db_connection()
        user_data = conn.execute("SELECT * FROM user WHERE username = ?", (request.form['username'],)).fetchone()
        conn.close()
        if user_data and bcrypt.check_password_hash(user_data['password'], request.form['password']):
            user = User(id=user_data['id'], username=user_data['username'], password=user_data['password'])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    hashed_password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO user (username, password) VALUES (?, ?)", (request.form['username'], hashed_password))
        conn.commit()
        conn.close()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    except sqlite3.IntegrityError:
        flash('Username already exists.', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- DASHBOARD ROUTE ---
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page
    total_apps_count = conn.execute('SELECT COUNT(id) FROM application WHERE user_id = ?', (current_user.id,)).fetchone()[0]
    total_pages = ceil(total_apps_count / per_page)
    recent_applications = conn.execute('SELECT * FROM application WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?', (current_user.id, per_page, offset)).fetchall()
    all_apps = conn.execute('SELECT * FROM application WHERE user_id = ?', (current_user.id,)).fetchall()
    conn.close()

    df = pd.DataFrame(all_apps, columns=['id', 'user_id', 'company_name', 'job_title', 'status', 'date_applied'])
    total_applications = len(df)
    interviews_scheduled = len(df[df['status'] == 'Interviewing'])
    in_progress = len(df[df['status'].isin(['Applied', 'Interviewing'])])
    
    theme = request.cookies.get('theme', 'light')
    status_chart_base64, company_chart_base64 = (None, None)
    if not df.empty:
        status_chart_base64 = get_plot_base64(df, 'status', theme)
        company_chart_base64 = get_plot_base64(df, 'company', theme)

    return render_template('dashboard.html',
                           total_applications=total_applications, interviews_scheduled=interviews_scheduled, in_progress=in_progress,
                           applications=recent_applications,
                           status_chart=status_chart_base64, company_chart=company_chart_base64,
                           current_page=page, total_pages=total_pages)

# --- APPLICATION BOARD & ACTIONS ---
@app.route('/applications')
@login_required
def applications():
    conn = get_db_connection()
    apps = conn.execute('SELECT * FROM application WHERE user_id = ? ORDER BY id DESC', (current_user.id,)).fetchall()
    conn.close()
    jobs_by_status = {"Wishlist": [], "Applied": [], "Interviewing": [], "Offer": [], "Rejected": []}
    for app in apps:
        if app['status'] in jobs_by_status:
            jobs_by_status[app['status']].append(app)
    return render_template('applications.html', jobs_by_status=jobs_by_status)

@app.route('/add_job', methods=['POST'])
@login_required
def add_job():
    form = request.form
    conn = get_db_connection()
    conn.execute('INSERT INTO application (user_id, company_name, job_title, status, date_applied) VALUES (?, ?, ?, ?, ?)',
                 (current_user.id, form['company_name'], form['job_title'], form['status'], form['date_applied']))
    conn.commit()
    conn.close()
    flash('Job application added!', 'success')
    return redirect(url_for('applications'))

@app.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    conn = get_db_connection()
    if conn.execute('SELECT * FROM application WHERE id=? AND user_id=?', (job_id, current_user.id)).fetchone() is None:
        abort(403)
    conn.execute('DELETE FROM application WHERE id = ?', (job_id,))
    conn.commit()
    conn.close()
    flash('Job application removed.', 'info')
    return redirect(url_for('applications'))

@app.route('/edit_job/<int:job_id>', methods=['POST'])
@login_required
def edit_job(job_id):
    conn = get_db_connection()
    if conn.execute('SELECT * FROM application WHERE id=? AND user_id=?', (job_id, current_user.id)).fetchone() is None:
        abort(403)
    form = request.form
    conn.execute('UPDATE application SET company_name=?, job_title=?, date_applied=?, status=? WHERE id=?',
                 (form['company_name'], form['job_title'], form['date_applied'], form['status'], job_id))
    conn.commit()
    conn.close()
    flash('Job application updated successfully!', 'success')
    return redirect(url_for('applications'))

@app.route('/update_status/<int:job_id>', methods=['POST'])
@login_required
def update_status(job_id):
    new_status = request.json.get('status')
    conn = get_db_connection()
    if conn.execute('SELECT * FROM application WHERE id = ? AND user_id = ?', (job_id, current_user.id)).fetchone() is None:
        conn.close()
        return jsonify({'success': False, 'message': 'Forbidden'}), 403
    conn.execute('UPDATE application SET status = ? WHERE id = ?', (new_status, job_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Status updated'})

if __name__ == '__main__':
    app.run(debug=True)