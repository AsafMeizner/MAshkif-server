from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS
from db_handler import fetch_entries, insert_entries, create_database, create_collection, get_all_competitions
from config import config, save_config, reload_config
import os
import requests
import logging
from datetime import datetime
import json
from ip2geotools.databases.noncommercial import DbIpCity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
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
    # Get client IP and country
    client_ip = request.remote_addr
    country = get_client_country(client_ip)
    
    # Get password from headers or JSON
    password = request.headers.get('x-password') or (request.json or {}).get('password')
    
    # Log the request
    logger.info(f"Request received - Method: {request.method}, Path: {request.path}, IP: {client_ip}, Country: {country}, Time: {datetime.now()}, Competition ID: {competition_id}, Collection: {collection_name}")
    
    role, details = check_password(password)
    if role is None:
        logger.warning(f"Invalid password attempt from IP: {client_ip}, Country: {country}")
        return jsonify({'message': 'Forbidden: Invalid password'}), 403

    allowed_comps = details.get('competitions')
    if allowed_comps != "all" and competition_id not in allowed_comps:
        logger.warning(f"Unauthorized competition access attempt - IP: {client_ip}, Country: {country}, Competition ID: {competition_id}, Role: {role}")
        return jsonify({'message': 'Forbidden: Access to this competition is not allowed'}), 403

    if request.method == 'GET':
        if details.get('permissions') not in ['read-only', 'read-write']:
            logger.warning(f"Unauthorized read attempt - IP: {client_ip}, Country: {country}, Role: {role}")
            return jsonify({'message': 'Forbidden: Read permission required'}), 403
        entries_data, status_code = fetch_entries(competition_id, collection_name)
        logger.info(f"Entries fetched successfully - IP: {client_ip}, Country: {country}, Competition ID: {competition_id}, Role: {role}")
        return jsonify(entries_data), status_code

    elif request.method == 'POST':
        if details.get('permissions') not in ['write-only', 'read-write']:
            logger.warning(f"Unauthorized write attempt - IP: {client_ip}, Country: {country}, Role: {role}")
            return jsonify({'message': 'Forbidden: Write permission required'}), 403
        data = request.json
        entries_list = data.get('entries', [])
        if not isinstance(entries_list, list):
            logger.warning(f"Invalid entries format - IP: {client_ip}, Country: {country}")
            return jsonify({'message': 'Invalid request: entries should be an array'}), 400
        insert_result, status_code = insert_entries(
            competition_id, entries_list, collection_name,
            create_if_not_exists=(details.get('permissions') == 'read-write')
        )
        logger.info(f"Entries inserted successfully - IP: {client_ip}, Country: {country}, Competition ID: {competition_id}, Role: {role}, Entries Count: {len(entries_list)}")
        return jsonify(insert_result), status_code

# --- API Route for Teams ---

@app.route('/<competition_id>/teams', methods=['GET'])
def get_teams(competition_id):
    password = request.headers.get('x-password')
    role, details = check_password(password)
    if role is None:
        return jsonify({'message': 'Forbidden: Invalid password'}), 403

    allowed_comps = details.get('competitions')
    if allowed_comps != "all" and competition_id not in allowed_comps:
        return jsonify({'message': 'Forbidden: Access to this competition is not allowed'}), 403

    if details.get('permissions') not in ['read-only', 'read-write']:
        return jsonify({'message': 'Forbidden: Read permission required'}), 403

    # Get TBA API key from config
    tba_key = config.get('tba_key')
    if not tba_key:
        return jsonify({'message': 'TBA API key not configured'}), 500

    # Get event key from query parameters or use competition_id as event key
    event_key = request.args.get('event_key', competition_id)
    
    # Check if we have cached teams in the database
    try:
        # Try to fetch teams from the database first
        teams_data, status_code = fetch_entries(competition_id, 'teams')
        if status_code == 200 and teams_data:
            # Format teams as strings in the format "number - nickname"
            formatted_teams = []
            for team in teams_data:
                if isinstance(team, dict) and 'team_number' in team and 'nickname' in team:
                    formatted_teams.append(f"{team['team_number']} - {team['nickname']}")
                elif isinstance(team, str):
                    formatted_teams.append(team)
            
            if formatted_teams:
                return jsonify(formatted_teams), 200
    except Exception as e:
        print(f"Error fetching teams from database: {str(e)}")
    
    # If we don't have cached teams, try to fetch from TBA API
    try:
        headers = {'X-TBA-Auth-Key': tba_key}
        url = f'https://www.thebluealliance.com/api/v3/event/{event_key}/teams/simple'
        
        # Log the request details (without the API key)
        print(f"Making TBA API request to: {url}")
        
        response = requests.get(url, headers=headers)
        
        # Log the response status and headers
        print(f"TBA API response status: {response.status_code}")
        print(f"TBA API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            teams = response.json()
            # Format teams as strings in the format "number - nickname"
            formatted_teams = [f"{team['team_number']} - {team['nickname']}" for team in teams]
            
            # Store teams in the database for future use
            try:
                insert_entries(competition_id, teams, 'teams', create_if_not_exists=True)
            except Exception as e:
                print(f"Error storing teams in database: {str(e)}")
            
            return jsonify(formatted_teams), 200
        elif response.status_code == 304:
            # Not modified, use cached data if available
            return jsonify({'message': 'Not modified, use cached data'}), 304
        elif response.status_code == 401:
            # Log the error response
            print(f"TBA API error response: {response.text}")
            return jsonify({'message': 'TBA API authentication failed. Please check your API key.'}), 401
        elif response.status_code == 403:
            # Log the error response
            print(f"TBA API error response: {response.text}")
            return jsonify({'message': 'TBA API access forbidden. Please check your API key permissions.'}), 403
        elif response.status_code == 404:
            return jsonify({'message': 'Event not found in TBA'}), 404
        else:
            # Log the error response
            print(f"TBA API error response: {response.text}")
            return jsonify({'message': f'TBA API error: {response.status_code}'}), response.status_code
    except Exception as e:
        print(f"Exception in get_teams: {str(e)}")
        return jsonify({'message': f'Error fetching teams: {str(e)}'}), 500
    
    # If all else fails, return a default list of teams
    default_teams = [
        "1234 - Example Team 1",
        "5678 - Example Team 2",
        "9012 - Example Team 3"
    ]
    return jsonify(default_teams), 200

@app.route('/<competition_id>/teams', methods=['POST'])
def add_teams(competition_id):
    password = request.headers.get('x-password')
    role, details = check_password(password)
    if role is None:
        return jsonify({'message': 'Forbidden: Invalid password'}), 403

    allowed_comps = details.get('competitions')
    if allowed_comps != "all" and competition_id not in allowed_comps:
        return jsonify({'message': 'Forbidden: Access to this competition is not allowed'}), 403

    if details.get('permissions') not in ['write-only', 'read-write']:
        return jsonify({'message': 'Forbidden: Write permission required'}), 403

    data = request.json
    teams_list = data.get('teams', [])
    
    if not isinstance(teams_list, list):
        return jsonify({'message': 'Invalid request: teams should be an array'}), 400
    
    # Format teams if they're not already in the correct format
    formatted_teams = []
    for team in teams_list:
        if isinstance(team, str):
            formatted_teams.append(team)
        elif isinstance(team, dict):
            if 'team_number' in team and 'nickname' in team:
                formatted_teams.append(f"{team['team_number']} - {team['nickname']}")
            else:
                return jsonify({'message': 'Invalid team format. Each team must have team_number and nickname'}), 400
        else:
            return jsonify({'message': 'Invalid team format'}), 400
    
    # Store teams in the database
    insert_result, status_code = insert_entries(
        competition_id, formatted_teams, 'teams',
        create_if_not_exists=(details.get('permissions') == 'read-write')
    )
    
    return jsonify(insert_result), status_code

# --- Admin GUI Routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        admin_details = config.get('passwords', {}).get('admin')
        if admin_details and password == admin_details.get("password"):
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
    competitions, _ = get_all_competitions()
    return render_template('admin_dashboard.html', config=config, competitions=competitions)

@app.route('/admin/update_config', methods=['POST'])
@admin_required
def update_config():
    new_mongo_uri = request.form.get('mongo_uri')
    if new_mongo_uri:
        config['MONGO_URI'] = new_mongo_uri
    
    new_tba_key = request.form.get('tba_key')
    if new_tba_key:
        config['tba_key'] = new_tba_key
        
    for key in config.get('passwords', {}):
        new_pass = request.form.get(f'passwords-{key}-password')
        new_perm = request.form.get(f'passwords-{key}-permissions')
        new_comps = request.form.getlist(f'passwords-{key}-competitions')  # Changed to getlist for multiple values
        if new_pass:
            config['passwords'][key]['password'] = new_pass
        if new_perm:
            config['passwords'][key]['permissions'] = new_perm
        if new_comps:
            if 'all' in new_comps:
                config['passwords'][key]['competitions'] = "all"
            else:
                config['passwords'][key]['competitions'] = new_comps
    
    save_config(config)
    reload_config()
    flash('Configuration updated successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_password', methods=['POST'])
@admin_required
def delete_password():
    delete_key = request.form.get('delete_key')
    if delete_key in config.get('passwords', {}):
        del config['passwords'][delete_key]
        save_config(config)
        reload_config()
        flash(f'Password entry for "{delete_key}" deleted successfully.')
    else:
        flash(f'No password entry found for key "{delete_key}".')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_password', methods=['POST'])
@admin_required
def add_password():
    new_key = request.form.get('new_key')
    new_pass = request.form.get('new_password')
    new_perm = request.form.get('new_permissions')
    new_comps = request.form.getlist('new_competitions')  # Changed to getlist for multiple values
    if not (new_key and new_pass and new_perm):
        flash('Missing required fields for new password.')
        return redirect(url_for('admin_dashboard'))
    
    if 'all' in new_comps:
        comps = "all"
    else:
        comps = new_comps
        
    config['passwords'][new_key] = {
        "password": new_pass,
        "permissions": new_perm,
        "competitions": comps
    }
    save_config(config)
    reload_config()
    flash(f'Password entry for "{new_key}" added successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create_competition', methods=['POST'])
@admin_required
def admin_create_competition():
    competition_id = request.form.get('competition_id')
    collections_input = request.form.get('collections')  # Optional comma-separated list
    if not competition_id:
        flash('Competition ID is required.')
        return redirect(url_for('admin_dashboard'))
    db = create_database(competition_id)
    if db is not None:
        flash(f'Competition "{competition_id}" created successfully.')
        if collections_input:
            collections = [c.strip() for c in collections_input.split(',') if c.strip()]
            for coll in collections:
                result = create_collection(competition_id, coll)
                if result:
                    flash(f'Collection "{coll}" created in competition "{competition_id}".')
                else:
                    flash(f'Failed to create collection "{coll}" in competition "{competition_id}".')
    else:
        flash(f'Failed to create competition "{competition_id}".')
    return redirect(url_for('admin_dashboard'))

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,x-password')
    return response

def get_client_country(ip):
    try:
        response = DbIpCity.get(ip, api_key='free')
        return response.country
    except Exception as e:
        logger.warning(f"Could not determine country for IP {ip}: {str(e)}")
        return "Unknown"

if __name__ == "__main__":
    app.run(debug=True) 