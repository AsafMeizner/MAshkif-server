from flask import Flask, request, jsonify
from flask_cors import CORS
from db_handler import fetch_entries, insert_entries
import os

app = Flask(__name__)
CORS(app)

# Define the two passwords.
NORMAL_PASSWORD = os.environ.get('password')
ADMIN_PASSWORD = os.environ.get('admin_password')

# New dynamic routes – the competition_id is extracted from the URL.
@app.route('/<competition_id>/entries', methods=['GET', 'POST'])
def entries(competition_id):
    return handle_entries(competition_id, 'entries')

@app.route('/<competition_id>/princess', methods=['GET', 'POST'])
def princess_entries(competition_id):
    return handle_entries(competition_id, 'princess')

def handle_entries(competition_id, collection_name):
    # Check for the password in either headers or JSON payload.
    password = request.headers.get('x-password') or (request.json or {}).get('password')
    if password not in [NORMAL_PASSWORD, ADMIN_PASSWORD]:
        return jsonify({'message': 'Forbidden: Invalid password'}), 403

    # Determine if the user is admin.
    is_admin = (password == ADMIN_PASSWORD)
    
    if request.method == 'GET':
        # For GET, we simply fetch entries.
        entries_data, status_code = fetch_entries(competition_id, collection_name)
        return jsonify(entries_data), status_code

    elif request.method == 'POST':
        data = request.json
        entries_list = data.get('entries', [])
        if not isinstance(entries_list, list):
            return jsonify({'message': 'Invalid request: entries should be an array'}), 400

        # For POST, we allow automatic creation of the competition DB if the admin password is used.
        insert_result, status_code = insert_entries(
            competition_id, entries_list, collection_name, create_if_not_exists=is_admin
        )
        return jsonify(insert_result), status_code

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,x-password')
    return response

if __name__ == "__main__":
    app.run()
