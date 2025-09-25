from pymongo import MongoClient
from datetime import datetime

client = MongoClient('mongodb://localhost:27017')
db = client['payment_fixer_db']
exceptions = db['exceptions']

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
    }
]
exceptions.insert_many(sample)
print('seeded')