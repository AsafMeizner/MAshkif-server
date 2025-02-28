import os
import json

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        # Use environment variables (or .env via os.environ) to generate default config.
        config = {
            "MONGO_URI": os.environ.get("MONGODB_URI"),
            "passwords": {
                "admin": {
                    "password": os.environ.get("admin_password"),
                    "permissions": "read-write",  # full permissions for admin GUI
                    "competitions": "all"
                },
                "normal": {
                    "password": os.environ.get("password"),
                    "permissions": "read-write",  # adjust as needed; could be read-only
                    "competitions": "all"
                }
            },
            "SECRET_KEY": os.environ.get("SECRET_KEY", "dev")
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    return config

config = load_config()

def save_config(new_config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(new_config, f, indent=4)
