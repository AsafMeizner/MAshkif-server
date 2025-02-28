# MAshkif server
## The server for the MAshkif scouting app made by Makers Assemble #5951 FRC team

### How to run the server

1. **Clone the repository.**

2. **Install dependencies:**

```
pip install -r requirements.txt
```


3. **Run the server:**

```
python app.py
```


4. **Configuration:**
- The server uses a `config.json` file for its configuration.
- On the first run, if no `config.json` exists, one will be automatically created using default values.
- To change settings such as passwords or the MongoDB URI, either update the `config.json` file manually or use the admin dashboard.

5. **Admin Dashboard:**
- Access the admin dashboard at: `http://127.0.0.1:5000/admin/login`
- Log in using the default admin password (default is `admin123` unless changed in `config.json`).
