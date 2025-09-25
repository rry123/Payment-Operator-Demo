from flask import Flask, jsonify
from pymongo import MongoClient
import ssl

import certifi
app = Flask(__name__)


print(ssl.OPENSSL_VERSION)
MONGO_URI = "mongodb+srv://rajy25122:ritik9640@cluster0.pqtebj6.mongodb.net/"

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

db = client['mydatabase']
collection = db['mycollection']

print("Connected!")

@app.route('/')
def home():
    # Example: count documents in the collection
    count = collection.count_documents({})
    return jsonify({"message": f"Connected to MongoDB! Document count: {count}"})

if __name__ == '__main__':
    app.run(debug=True)
