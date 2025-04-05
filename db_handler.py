from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import pymongo
from config import config
import socket

def get_client():
    try:
        # Set a longer timeout for DNS resolution and connection
        client = MongoClient(
            config.get("MONGO_URI"),
            server_api=ServerApi('1'),
            connectTimeoutMS=30000,  # 30 seconds
            socketTimeoutMS=30000,   # 30 seconds
            serverSelectionTimeoutMS=30000,  # 30 seconds
            retryWrites=True,
            retryReads=True
        )
        # Test the connection
        client.admin.command('ping')
        return client
    except pymongo.errors.ServerSelectionTimeoutError as e:
        print(f"ServerSelectionTimeoutError: {e}")
        return None
    except pymongo.errors.ConnectionError as e:
        print(f"ConnectionError: {e}")
        return None
    except socket.gaierror as e:
        print(f"DNS resolution error: {e}")
        return None
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def get_db(db_name, create_if_not_exists=False):
    try:
        client = get_client()
        client.admin.command('ping')
        print("Connected to MongoDB!")
        # Check if the database exists by listing current databases.
        if db_name not in client.list_database_names():
            if create_if_not_exists:
                db = client[db_name]
                return db
            else:
                return None
        else:
            return client[db_name]
    except pymongo.errors.ServerSelectionTimeoutError as e:
        print(f"ServerSelectionTimeoutError: {e}")
        return None
    except pymongo.errors.ConnectionError as e:
        print(f"ConnectionError: {e}")
        return None
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def fetch_entries(db_name, collection_name):
    db = get_db(db_name, create_if_not_exists=False)
    if db is None:
        return {'message': 'Competition not found'}, 404
    try:
        entries = list(db[collection_name].find())
        for entry in entries:
            entry['_id'] = str(entry['_id'])
        return entries, 200
    except pymongo.errors.AutoReconnect as e:
        print(f"AutoReconnect error: {e}")
        return {'message': 'Database connection error'}, 500
    except Exception as e:
        print(f"Error fetching entries: {e}")
        return {'message': 'Error fetching entries'}, 500

def insert_entries(db_name, entries, collection_name, create_if_not_exists=False):
    db = get_db(db_name, create_if_not_exists=create_if_not_exists)
    if db is None:
        return {'message': 'Competition not found'}, 404

    inserted_ids = []
    try:
        for entry in entries:
            existing_entry = db[collection_name].find_one({
                'matchNumber': entry['matchNumber'],
                'teamNumber': entry['teamNumber']
            })
            if existing_entry:
                if existing_entry['submissionTime'] < entry['submissionTime']:
                    db[collection_name].update_one({'_id': existing_entry['_id']}, {'$set': entry})
                    inserted_ids.append(str(existing_entry['_id']))
            else:
                result = db[collection_name].insert_one(entry)
                inserted_ids.append(str(result.inserted_id))

        if inserted_ids:
            return {'message': 'Entries processed successfully', 'entryIds': inserted_ids}, 201
        else:
            return {'message': 'No new entries to process'}, 400
    except pymongo.errors.AutoReconnect as e:
        print(f"AutoReconnect error: {e}")
        return {'message': 'Database connection error'}, 500
    except Exception as e:
        print(f"Error inserting entries: {e}")
        return {'message': 'Error inserting entries'}, 500

# Admin helper functions

def create_database(db_name):
    db = get_db(db_name, create_if_not_exists=True)
    if db is not None:
        return db
    return None

def create_collection(db_name, collection_name):
    db = get_db(db_name, create_if_not_exists=True)
    if db is not None:
        try:
            db.create_collection(collection_name)
            return True
        except pymongo.errors.CollectionInvalid:
            # Collection already exists: treat as success.
            return True
        except Exception as e:
            print(f"Error creating collection: {e}")
            return False
    return False
