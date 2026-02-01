"""Seed minimal realistic data into a local MongoDB for UI development.

Usage (recommended):
  # start a local mongo with docker (one-liner)
  docker run --name esg-mongo -p 27017:27017 -d mongo:6.0 --bind_ip_all

  # set env for local dev (or edit .env)
  export MONGODB_URL="mongodb://localhost:27017"
  python scripts/seed_local_data.py

The script is idempotent (uses upsert by unique keys).
"""
from __future__ import annotations
import hashlib
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "esg_dashboard"

async def ensure_indexes(db):
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)

async def seed_users(db):
    # Passwords use the same simple sha256 hashing as the app's dev mode
    def sha(p):
        return hashlib.sha256(p.encode()).hexdigest()

    users = [
        {
            "username": "admin",
            "email": "admin@local.test",
            "full_name": "Administrator",
            "role": "admin",
            "hashed_password": sha("admin123"),
            "company": "GreenBDG",
            "portfolio_access": ["dube-trade-port","bertha-house"],
            "status": "active",
            "created_at": datetime.utcnow(),
        },
        {
            "username": "bertha-user",
            "email": "bertha@local.test",
            "full_name": "Bertha House Manager",
            "role": "client",
            "hashed_password": sha("bertha123"),
            "company": "Bertha House",
            "portfolio_access": ["bertha-house"],
            "status": "active",
            "created_at": datetime.utcnow(),
        },
    ]

    for u in users:
        await db.users.update_one({"username": u["username"]}, {"$set": u}, upsert=True)

async def seed_portfolios(db):
    portfolios = [
        {"_id": "bertha-house", "name": "Bertha House", "description": "Demo building"},
        {"_id": "dube-trade-port", "name": "Dube Trade Port", "description": "Demo port"},
    ]
    for p in portfolios:
        await db.portfolios.update_one({"_id": p["_id"]}, {"$set": p}, upsert=True)

async def seed_assets(db):
    assets = [
        {
            "_id": "bertha-house-meter-1",
            "portfolio_id": "bertha-house",
            "name": "Local Mains",
            "type": "meter",
            "created_at": datetime.utcnow(),
        }
    ]
    for a in assets:
        await db.assets.update_one({"_id": a["_id"]}, {"$set": a}, upsert=True)

async def seed_sample_invoices(db):
    inv = {
        "invoice_number": "INV-2025-0001",
        "portfolio_id": "bertha-house",
        "amount": 1234.56,
        "currency": "ZAR",
        "issued_at": datetime.utcnow(),
    }
    await db.invoices.update_one({"invoice_number": inv["invoice_number"]}, {"$set": inv}, upsert=True)

async def seed_ai_templates(db):
    # idempotent per-portfolio templates useful for local dev and QA
    templates = [
        {
            "portfolio_id": "bertha-house",
            "key": "exec_summary",
            "name": "Executive summary (short)",
            "prompt": "In two concise bullet points, summarize the current carbon intensity for {{portfolio_name}} and provide one high-impact, low-cost action the facilities team can implement this week.",
            "is_public": True,
        },
        {
            "portfolio_id": "bertha-house",
            "key": "board_brief",
            "name": "Board brief (one-paragraph)",
            "prompt": "Write a single-paragraph board-level briefing for {{portfolio_name}} (tone: executive, <120 words) that highlights trend, top risk, and recommended CFO action with estimated annual savings.",
            "is_public": True,
        },
        {
            "portfolio_id": "bertha-house",
            "key": "technical_deepdive",
            "name": "Technical deep-dive",
            "prompt": "Provide a technical 3-part checklist for engineering: 1) immediate meter and sensor checks, 2) 30-day operational tuning, 3) 12-month capital improvements — include expected % energy savings for each item.",
            "is_public": False,
        },
    ]

    for t in templates:
        await db.ai_templates.update_one({"portfolio_id": t["portfolio_id"], "key": t["key"]}, {"$set": t}, upsert=True)


async def main():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    await ensure_indexes(db)
    await seed_users(db)
    await seed_portfolios(db)
    await seed_assets(db)
    await seed_sample_invoices(db)
    await seed_ai_templates(db)
    # quick verification
    users = await db.users.find().to_list(length=10)
    print(f"Seeded users: {[u['username'] for u in users]}")
    print("Done.")
    client.close()

if __name__ == '__main__':
    asyncio.run(main())
