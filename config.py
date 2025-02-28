import os
import json

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    "MONGO_URI": "<mongo-uri-here>",
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
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = DEFAULT_CONFIG.copy()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    return config

config = load_config()

def save_config(new_config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(new_config, f, indent=4)
