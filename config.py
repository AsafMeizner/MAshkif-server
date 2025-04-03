import os
import json

# Use the directory of this file to create an absolute path to the config file.
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

DEFAULT_CONFIG = {
    "MONGO_URI": "<mongo-uri-here>",
    "tba_key": "<tba-key-here>",
    "passwords": {
        "admin": {
            "password": "admin123",  # default admin password
            "permissions": "read-write",  # full permissions for admin GUI
            "competitions": "all"
        },
        "normal": {
            "password": "user123",  # default normal password
            "permissions": "read-write",  # adjust as needed; could be read-only
            "competitions": "all"
        }
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print("Error reading config file:", e)
            config = DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except OSError as e:
            print("Error writing config file:", e)
            raise
    return config

config = load_config()

def save_config(new_config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4)
    except OSError as e:
        print("Error writing to config file:", e)
        raise