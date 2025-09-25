from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv 
from datetime import datetime
import re
import certifi
import os

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')

app = Flask(__name__)
CORS(app)

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

# --- API endpoints ---
@app.route('/api/ping', methods = ['GET'])
def ping():
    return jsonify({'ok': True, 'message': 'ping'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user = data.get('username')
    pwd = data.get('password')
    if user in OPERATORS and OPERATORS[user] == pwd:
        return jsonify({'ok': True, 'username': user})
    return jsonify({'ok': False, 'error': 'Invalid credentials'}), 401

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)