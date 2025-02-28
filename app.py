from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
from db_handler import (fetch_entries, insert_entries, create_database, create_collection,
                        list_competitions, list_collections)
from config import config, save_config
import os

app = Flask(__name__)
app.secret_key = config.get("SECRET_KEY", "dev")
CORS(app)

def check_password(provided):
    for key, details in config.get("passwords", {}).items():
        if provided == details.get("password"):
            return key, details
    return None, None

# --- API Routes for Competition Entries ---

@app.route('/<competition_id>/entries', methods=['GET', 'POST'])
def entries(competition_id):
    return handle_entries(competition_id, 'entries')

@app.route('/<competition_id>/princess', methods=['GET', 'POST'])
def princess_entries(competition_id):
    return handle_entries(competition_id, 'princess')

def handle_entries(competition_id, collection_name):
    password = request.headers.get('x-password') or (request.json or {}).get('password')
    role, details = check_password(password)
    if role is None:
        return jsonify({'message': 'Forbidden: Invalid password'}), 403

    allowed_comps = details.get('competitions')
    if allowed_comps != "all" and competition_id not in allowed_comps:
        return jsonify({'message': 'Forbidden: Access to this competition is not allowed'}), 403

    if request.method == 'GET':
        if details.get('permissions') not in ['read-only', 'read-write']:
            return jsonify({'message': 'Forbidden: Read permission required'}), 403
        entries_data, status_code = fetch_entries(competition_id, collection_name)
        return jsonify(entries_data), status_code

    elif request.method == 'POST':
        if details.get('permissions') not in ['write-only', 'read-write']:
            return jsonify({'message': 'Forbidden: Write permission required'}), 403
        data = request.json
        entries_list = data.get('entries', [])
        if not isinstance(entries_list, list):
            return jsonify({'message': 'Invalid request: entries should be an array'}), 400
        insert_result, status_code = insert_entries(
            competition_id, entries_list, collection_name,
            create_if_not_exists=(details.get('permissions') == 'read-write')
        )
        return jsonify(insert_result), status_code

# --- Admin GUI Routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        admin_details = config.get('passwords', {}).get('admin')
        if admin_details and password == admin_details.get('password'):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin password')
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return func(*args, **kwargs)
    return wrapper

@app.route('/admin')
@admin_required
def admin_dashboard():
    competitions = list_competitions()
    return render_template('admin_dashboard.html', config=config, competitions=competitions)

@app.route('/admin/update_config', methods=['POST'])
@admin_required
def update_config():
    new_mongo_uri = request.form.get('mongo_uri')
    if new_mongo_uri:
        config['MONGO_URI'] = new_mongo_uri
    for key in config.get('passwords', {}):
        new_pass = request.form.get(f'passwords-{key}-password')
        new_perm = request.form.get(f'passwords-{key}-permissions')
        new_comps = request.form.get(f'passwords-{key}-competitions')
        if new_pass:
            config['passwords'][key]['password'] = new_pass
        if new_perm:
            config['passwords'][key]['permissions'] = new_perm
        if new_comps:
            if new_comps.strip().lower() != 'all':
                comps = [c.strip() for c in new_comps.split(',') if c.strip()]
                config['passwords'][key]['competitions'] = comps
            else:
                config['passwords'][key]['competitions'] = "all"
    new_secret = request.form.get('secret_key')
    if new_secret:
        config['SECRET_KEY'] = new_secret
        app.secret_key = new_secret
    save_config(config)
    flash('Configuration updated successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_password', methods=['POST'])
@admin_required
def add_password():
    new_key = request.form.get('new_key')
    new_pass = request.form.get('new_password')
    new_perm = request.form.get('new_permissions')
    new_comps = request.form.get('new_competitions')
    if not (new_key and new_pass and new_perm):
        flash('Missing required fields for new password.')
        return redirect(url_for('admin_dashboard'))
    if new_comps and new_comps.strip().lower() != 'all':
        comps = [c.strip() for c in new_comps.split(',') if c.strip()]
    else:
        comps = "all"
    config['passwords'][new_key] = {
        "password": new_pass,
        "permissions": new_perm,
        "competitions": comps
    }
    save_config(config)
    flash(f'Password entry for "{new_key}" added successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create_database', methods=['POST'])
@admin_required
def admin_create_database():
    competition_id = request.form.get('competition_id')
    if not competition_id:
        flash('Competition ID is required.')
        return redirect(url_for('admin_dashboard'))
    db = create_database(competition_id)
    if db:
        flash(f'Competition database "{competition_id}" created successfully.')
    else:
        flash(f'Failed to create competition database "{competition_id}".')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create_collection', methods=['POST'])
@admin_required
def admin_create_collection():
    competition_id = request.form.get('competition_id')
    collection_name = request.form.get('collection_name')
    if not (competition_id and collection_name):
        flash('Competition ID and collection name are required.')
        return redirect(url_for('admin_dashboard'))
    result = create_collection(competition_id, collection_name)
    if result:
        flash(f'Collection "{collection_name}" created successfully in competition "{competition_id}".')
    else:
        flash(f'Failed to create collection "{collection_name}" in competition "{competition_id}".')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/collections/<competition_id>')
@admin_required
def get_collections(competition_id):
    collections = list_collections(competition_id)
    return jsonify(collections)

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,x-password')
    return response

if __name__ == "__main__":
    app.run(debug=True)
