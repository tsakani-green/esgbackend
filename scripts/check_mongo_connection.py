"""Check MongoDB connectivity using the project's settings.

Usage:
  python scripts/check_mongo_connection.py

This will print the effective MONGO URI (with password redacted), try to connect, and list databases or show a clear error.
"""
from app.core.config import settings
from pymongo import MongoClient
import urllib.parse

uri = settings.get_mongo_uri()
print("Effective MONGO URI:", uri.replace(settings.MONGODB_URL or '', '***') if uri else uri)

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    info = client.server_info()
    print("MongoDB server info:", {k: info.get(k) for k in ("version", "gitVersion") if k in info})
    print("Databases:", client.list_database_names())
    client.close()
except Exception as e:
    print("Failed to connect to MongoDB:\n", e)
    print("Suggested checks:\n - Is MONGODB_URL in .env correct?\n - Is your network/VPN blocking outbound connections to MongoDB Atlas?\n - Does MongoDB Atlas allow your IP in Project Network Access (IP whitelist)?")
