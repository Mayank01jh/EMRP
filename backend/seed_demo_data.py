"""Seed sample ambulances and hospitals in MongoDB Atlas for live testing."""
import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.base import new_id, utcnow

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "emrp")

async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    amb_count = await db.ambulances.count_documents({})
    print(f"Current ambulances count: {amb_count}")
    if amb_count == 0:
        sample_ambulances = [
            {
                "_id": new_id(),
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "registration": "DL-01-AMB-1081",
                "operator_id": "Delhi-EMS-Central",
                "status": "AVAILABLE",
                "capabilities": ["ALS", "VENTILATOR"],
                "crew": [
                    {"name": "Dr. Rajesh Sharma", "role": "Paramedic Specialist", "license_number": "MED-9941"},
                    {"name": "Vikas Singh", "role": "Emergency Driver", "license_number": "DRV-1102"},
                ],
                "current_location": {
                    "type": "Point",
                    "coordinates": [77.2150, 28.6180],
                },
                "heading_deg": 45.0,
                "speed_kmh": 0.0,
            },
            {
                "_id": new_id(),
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "registration": "DL-02-AMB-1082",
                "operator_id": "Delhi-EMS-South",
                "status": "AVAILABLE",
                "capabilities": ["BLS"],
                "crew": [
                    {"name": "Sunita Verma", "role": "EMT Lead", "license_number": "EMT-4412"},
                    {"name": "Amit Kumar", "role": "Emergency Driver", "license_number": "DRV-8821"},
                ],
                "current_location": {
                    "type": "Point",
                    "coordinates": [77.2020, 28.6100],
                },
                "heading_deg": 180.0,
                "speed_kmh": 0.0,
            },
            {
                "_id": new_id(),
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "registration": "DL-03-AMB-1083",
                "operator_id": "Delhi-EMS-North",
                "status": "DISPATCHED",
                "capabilities": ["ALS", "NEONATAL"],
                "crew": [
                    {"name": "Priya Nair", "role": "Critical Care Paramedic", "license_number": "MED-7719"},
                ],
                "current_location": {
                    "type": "Point",
                    "coordinates": [77.2280, 28.6250],
                },
                "heading_deg": 270.0,
                "speed_kmh": 38.0,
            },
        ]
        await db.ambulances.insert_many(sample_ambulances)
        print("Seeded 3 sample ambulances successfully!")

    hosp_count = await db.hospitals.count_documents({})
    print(f"Current hospitals count: {hosp_count}")
    if hosp_count == 0:
        sample_hospitals = [
            {
                "_id": new_id(),
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "name": "AIIMS Apex Trauma Center",
                "location": {
                    "type": "Point",
                    "coordinates": [77.2088, 28.5672],
                },
                "address": "Ring Rd, Safdarjung Enclave, New Delhi, Delhi 110029",
                "phone": "+91-11-26588500",
                "capabilities": ["TRAUMA", "CARDIAC", "STROKE", "BURNS"],
                "capacity": {
                    "resus_beds_available": 4,
                    "icu_beds_available": 2,
                    "ed_wait_minutes": 5,
                    "last_updated_at": utcnow(),
                },
                "helipad": True,
            },
            {
                "_id": new_id(),
                "created_at": utcnow(),
                "updated_at": utcnow(),
                "name": "Safdarjung Hospital Emergency Care",
                "location": {
                    "type": "Point",
                    "coordinates": [77.2075, 28.5714],
                },
                "address": "Ansari Nagar West, New Delhi, Delhi 110029",
                "phone": "+91-11-26165060",
                "capabilities": ["TRAUMA", "CARDIAC", "PAEDIATRIC"],
                "capacity": {
                    "resus_beds_available": 6,
                    "icu_beds_available": 5,
                    "ed_wait_minutes": 8,
                    "last_updated_at": utcnow(),
                },
                "helipad": False,
            },
        ]
        await db.hospitals.insert_many(sample_hospitals)
        print("Seeded 2 sample hospitals successfully!")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed())
