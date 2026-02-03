# fix_production_password.py
import os
import sys
from pymongo import MongoClient
from passlib.context import CryptContext

def main():
    # === CONFIGURATION ===
    # PASTE YOUR MONGODB_URL HERE (from Render Environment tab)
    MONGODB_URL = "mongodb+srv://..."  # ⚠️ REPLACE THIS WITH YOUR ACTUAL URL
    
    USERNAME = "admin"
    NEW_PASSWORD = "AdminSecure123!"  # You can change this
    
    if "mongodb+srv://" not in MONGODB_URL:
        print("❌ ERROR: Please paste your real MONGODB_URL from Render")
        print("   Go to: Render Dashboard → esgbackend → Environment → MONGODB_URL")
        return
    
    # === FIX SCRIPT ===
    try:
        print("🔗 Connecting to production database...")
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB")
        
        # Get database
        db_name = MONGODB_URL.split("/")[-1].split("?")[0]
        if not db_name:
            db_name = "esg_dashboard"
        db = client[db_name]
        print(f"📊 Using database: {db_name}")
        
        # Check current admin user
        admin_user = db.users.find_one({"username": USERNAME})
        if not admin_user:
            print(f"❌ User '{USERNAME}' not found!")
            print("\nAvailable users:")
            for user in db.users.find({}, {"username": 1, "email": 1, "role": 1}):
                print(f"  - {user.get('username')} ({user.get('role')})")
            return
        
        print(f"\n🔍 Found user: {USERNAME}")
        print(f"   Email: {admin_user.get('email')}")
        print(f"   Role: {admin_user.get('role')}")
        print(f"   Current password hash: {admin_user.get('hashed_password', 'EMPTY')[:50]}...")
        
        # Initialize password hasher (MUST match your app)
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Generate new hash
        new_hash = pwd_context.hash(NEW_PASSWORD)
        
        # Confirm before updating
        print(f"\n⚠️  About to update password for '{USERNAME}'")
        response = input("Type 'YES' to continue: ")
        
        if response.strip().upper() == "YES":
            # Update the user
            result = db.users.update_one(
                {"username": USERNAME},
                {"$set": {"hashed_password": new_hash}}
            )
            
            if result.modified_count == 1:
                print(f"\n✅ SUCCESS: Password updated!")
                print(f"   New password: {NEW_PASSWORD}")
                print(f"   New hash: {new_hash[:50]}...")
                
                # Verify
                updated = db.users.find_one({"username": USERNAME})
                if pwd_context.verify(NEW_PASSWORD, updated.get("hashed_password", "")):
                    print("✅ Hash verification passed!")
                else:
                    print("❌ Hash verification failed (unexpected)")
            else:
                print("⚠️  No changes made")
        else:
            print("❌ Update cancelled")
        
        client.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nCommon issues:")
        print("1. Wrong MONGODB_URL - copy from Render Environment tab")
        print("2. Network blocked - ensure you can connect to MongoDB Atlas")
        print("3. IP not whitelisted - check MongoDB Atlas Network Access")

if __name__ == "__main__":
    main()