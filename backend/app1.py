from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from datetime import datetime, timedelta
import bcrypt
import certifi
import os


from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)

# MongoDB connection (local)
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where()
)
try:
    # This will attempt to get the list of databases from MongoDB
    dbs = client.list_database_names()
    print("✅ Connected to MongoDB Atlas! Databases:", dbs)
except Exception as e:
    print("❌ Could not connect to MongoDB Atlas:", e)

db = client['payment_fixer_db']
exceptions = db['exceptions']
processed = db['processed']
audit = db['audit_logs']
users = db['users'] 

# --- Simple operator "auth" (demo only) ---
OPERATORS = {
    "operator1": "password1",
    "operator2": "password2"
}

# --- Helpers ---
def validate_transaction(tx):
    """Basic validations used by demo: name length and IBAN-ish check"""
    errs = []
    # Beneficiary name should be <= 70 chars (example rule)
    name = tx.get('beneficiary_name', '')
    if len(name.strip()) == 0:
        errs.append('Beneficiary name empty')
    if len(name) > 70:
        errs.append('Beneficiary name too long (max 70)')
    # Amount
    try:
        amt = float(tx.get('amount', 0))
        if amt <= 0:
            errs.append('Amount must be positive')
    except Exception:
        errs.append('Amount invalid')
    # Very simple IBAN-like pattern (not full validation)
    iban = tx.get('iban', '')
    if iban and not re.match(r'^[A-Z0-9]{8,34}$', iban.replace(' ', '').upper()):
        errs.append('IBAN format invalid')
    return errs

def get_dashboard_stats(days=5):
    """
    Returns a dict of dashboard metrics for the last `days` days.
    """
    now = datetime.utcnow()
    since = now - timedelta(days=days)

    # Counts
    total_exceptions = exceptions.count_documents({})
    total_processed = processed.count_documents({})
    processed_recent = processed.count_documents({'processed_at': {'$gte': since}})
    # processed today (UTC day)
    start_of_today = datetime(now.year, now.month, now.day)
    processed_today = processed.count_documents({'processed_at': {'$gte': start_of_today}})

    # Exceptions by message type
    ex_by_mt_cursor = exceptions.aggregate([
        {'$group': {'_id': '$message_type', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ])
    exceptions_by_message_type = [{'message_type': doc['_id'] or '(none)', 'count': doc['count']} for doc in ex_by_mt_cursor]

    # Processed count by operator
    proc_by_op_cursor = processed.aggregate([
        {'$group': {'_id': '$processed_by', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ])
    processed_by_operator = [{'operator': doc['_id'] or '(unknown)', 'count': doc['count']} for doc in proc_by_op_cursor]

    # Top errors (from exceptions.error string)
    top_errors_cursor = exceptions.aggregate([
        {'$match': {'error': {'$exists': True}}},
        {'$group': {'_id': '$error', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 10}
    ])
    top_errors = [{'error': doc['_id'] or '(none)', 'count': doc['count']} for doc in top_errors_cursor]

    # Average resolution time (processed.processed_at - processed.created_at) in seconds
    # Only consider processed docs that have created_at and processed_at
    avg_pipeline = [
        {'$match': {'created_at': {'$exists': True}, 'processed_at': {'$exists': True}, 'processed_at': {'$gte': since}}},
        {'$project': {'diffMs': {'$subtract': ['$processed_at', '$created_at']}}},
        {'$group': {'_id': None, 'avgMs': {'$avg': '$diffMs'}}}
    ]
    avg_res = list(processed.aggregate(avg_pipeline))
    avg_resolution_seconds = None
    if avg_res and avg_res[0].get('avgMs') is not None:
        avg_resolution_seconds = avg_res[0]['avgMs'] / 1000.0  # ms -> seconds

    # Exceptions trend per day for last `days`
    trend_pipeline = [
        {'$match': {'created_at': {'$gte': since}}},
        {'$group': {
            '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
            'count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}}
    ]
    trend_cursor = list(exceptions.aggregate(trend_pipeline))
    # build date keys and fill zeros for missing days
    trend = {}
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date().isoformat()
        trend[d] = 0
    for entry in trend_cursor:
        trend[entry['_id']] = entry['count']

    return {
        'ok': True,
        'generated_at': now.isoformat() + 'Z',
        'total_exceptions': total_exceptions,
        'total_processed': total_processed,
        'processed_recent_days': processed_recent,
        'processed_today': processed_today,
        'avg_resolution_seconds': avg_resolution_seconds,
        'exceptions_by_message_type': exceptions_by_message_type,
        'processed_by_operator': processed_by_operator,
        'top_errors': top_errors,
        'exceptions_trend': trend
    }

# --- API endpoints ---
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    username = data.get('username')
    password = data.get('password')

    # If you forget to return here, Flask returns None by default
    if not all([name, username, password]):
        return jsonify({"ok": False, "error": "Missing fields"}), 400

    # You may have logic here but forgot to return anything at the end
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    users.insert_one({
        "name": name,
        "username": username,
        "password": hashed_pw,
        "created_at": datetime.utcnow()
    })

    # ⚠️ Must return something!
    return jsonify({"ok": True, "message": "User registered successfully"})

@app.route('/api/ping', methods = ['GET'])
def ping():
    return jsonify({'ok': True, 'message': 'ping'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    # Check if fields are provided
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400

    # Find user in DB
    user = users.find_one({"username": username})
    if not user:
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401

    # Check password
    if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401

    # Create JWT token
    access_token = create_access_token(identity=str(user["_id"]))

    return jsonify({
        "ok": True,
        "token": access_token,
        "username": username
    })

@app.route('/api/exceptions', methods=['GET'])
def get_exceptions():
    docs = list(exceptions.find().sort('created_at', -1))
    for d in docs:
        d['_id'] = str(d['_id'])
    return jsonify({'ok': True, 'exceptions': docs})

@app.route('/api/processed', methods=['GET'])
def get_processed():
    docs = list(processed.find().sort('processed_at', -1))
    for d in docs:
        d['_id'] = str(d['_id'])
    return jsonify({'ok': True, 'processed': docs})

@app.route('/api/fix', methods=['POST'])
def fix_transaction():
    data = request.json or {}
    tx_id = data.get('tx_id')
    operator = data.get('operator')
    new_values = data.get('tx')
    if not tx_id or not operator or not new_values:
        return jsonify({'ok': False, 'error': 'Missing fields'}), 400

    orig = exceptions.find_one({'_id': ObjectId(tx_id)})
    if not orig:
        return jsonify({'ok': False, 'error': 'Transaction not found in exceptions'}), 404

    # Merge and validate
    merged = orig.copy()
    merged.update(new_values)
    # remove _id to avoid problems
    merged.pop('_id', None)

    errors = validate_transaction(merged)
    if errors:
        # update the exception record with last_error and keep in queue
        exceptions.update_one({'_id': ObjectId(tx_id)}, {'$set': {'last_error': errors, 'last_modified_by': operator, 'last_modified_at': datetime.utcnow()}})
        return jsonify({'ok': False, 'errors': errors}), 400

    # Move to processed
    merged['processed_at'] = datetime.utcnow()
    merged['processed_by'] = operator
    res = processed.insert_one(merged)

    # Insert audit log
    audit.insert_one({
        'tx_id': tx_id,
        'operator': operator,
        'before': {k: v for k, v in orig.items() if k != '_id'},
        'after': merged,
        'timestamp': datetime.utcnow()
    })

    # Remove from exceptions
    exceptions.delete_one({'_id': ObjectId(tx_id)})

    return jsonify({'ok': True, 'processed_id': str(res.inserted_id)})

@app.route('/api/seed', methods=['POST'])
def seed_data():
    # seeds some example exception transactions
    sample = [
        {
            'message_type': 'MT103',
            'sender': 'ABC BANK',
            'receiver': 'XYZ BANK',
            'beneficiary_name': 'Johnathan Will...',
            'iban': 'GB29NWBK60161331926819',
            'amount': '5000',
            'currency': 'USD',
            'error': 'Field 59 truncated when converting to MX',
            'created_at': datetime.utcnow()
        },
        {
            'message_type': 'MT103',
            'sender': 'SOME BANK',
            'receiver': 'OTHER BANK',
            'beneficiary_name': '',
            'iban': 'INVALIDIBAN',
            'amount': '-100',
            'currency': 'EUR',
            'error': 'Multiple errors detected from MT->MX conversion',
            'created_at': datetime.utcnow()
        }
    ]
    res = exceptions.insert_many(sample)
    return jsonify({'ok': True, 'inserted_count': len(res.inserted_ids)})

@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    # optional ?days=30 parameter (int), bounded between 1 and 365
    try:
        days = int(request.args.get('days', 30))
    except ValueError:
        days = 30
    days = max(1, min(days, 365))  # sane bounds

    try:
        stats = get_dashboard_stats(days=days)
        return jsonify(stats)
    except Exception as e:
        # don't expose stack trace in prod; helpful during dev
        return jsonify({'ok': False, 'error': str(e)}), 500
    
    


# report_generator = pipeline("text2text-generation", model="facebook/bart-large-cnn")



# @app.route('/api/generate_report', methods=['POST'])
# def generate_report():
#     data = request.json
#     if not data:
#         return jsonify({"ok": False, "error": "No data provided"}), 400

#     # Convert structured data into a readable prompt
#     prompt = f"""
# Dashboard data:
# Total exceptions: {data['total_exceptions']}
# Total processed: {data['total_processed']}
# Processed in last {data.get('processed_recent_days',7)} days: {data['processed_recent_days']}
# Processed today: {data['processed_today']}
# Average resolution time (seconds): {data['avg_resolution_seconds']}
# Exceptions by message type: {', '.join([f"{e['message_type']} ({e['count']})" for e in data['exceptions_by_message_type']])}
# Processed by operator: {', '.join([f"{p['operator']} ({p['count']})" for p in data['processed_by_operator']])}
# Top errors: {', '.join([f"{t['error']} ({t['count']})" for t in data['top_errors']])}
# Exceptions trend last 7 days: {', '.join([f"{k}: {v}" for k,v in data['exceptions_trend'].items()])}

# Generate a concise, readable report from the above data in under 100 words. Do not repeat instructions.
# """


#     try:
#         report = report_generator(prompt, max_length=1000, min_length=50, do_sample=False)
#         return jsonify({"ok": True, "report": report[0]['generated_text']})
#     except Exception as e:
#         return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/operator_stats', methods=['GET'])
def operator_stats():
    pipeline = [
        {"$group": {
            "_id": "$processed_by",
            "count": {"$sum": 1},
            "avg_resolution": {"$avg": {"$subtract": ["$processed_at", "$created_at"]}}
        }},
        {"$sort": {"count": -1}}
    ]
    results = []
    for doc in processed.aggregate(pipeline):
        results.append({
            "operator": doc["_id"],
            "count": doc["count"],
            "avg_resolution_seconds": doc["avg_resolution"] / 1000.0 if doc.get("avg_resolution") else None
        })
    return jsonify({"ok": True, "stats": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)