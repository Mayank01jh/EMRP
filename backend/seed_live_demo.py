"""
Seed rich demo incidents and ambulances directly into MongoDB Atlas.
"""
import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb+srv://Mayank1234:mayank1234@mydata.ezd5wcv.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "emrp"

def utcnow():
    return datetime.now(timezone.utc)

def new_id():
    import uuid
    return uuid.uuid4().hex[:24]

async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    now = utcnow()

    # 1. Seed demo ambulances
    ambulances = [
        {
            "_id": "amb-delhi-1081",
            "created_at": now,
            "updated_at": now,
            "registration": "DL-01-AMB-1081",
            "operator_id": "Delhi-EMS-Central",
            "status": "AVAILABLE",
            "capabilities": ["ALS", "VENTILATOR"],
            "crew": [
                {"name": "Dr. Rajesh Sharma", "role": "Paramedic Specialist", "license_number": "MED-9941"},
                {"name": "Vikas Singh", "role": "Emergency Driver", "license_number": "DRV-1102"},
            ],
            "current_location": {"type": "Point", "coordinates": [77.2150, 28.6180]},
            "location": {"type": "Point", "coordinates": [77.2150, 28.6180]},
            "heading_deg": 45.0,
            "speed_kmh": 0.0,
            "last_seen_at": now.isoformat(),
            "active_incident_id": None,
        },
        {
            "_id": "amb-delhi-1082",
            "created_at": now,
            "updated_at": now,
            "registration": "DL-02-AMB-1082",
            "operator_id": "Delhi-EMS-South",
            "status": "AVAILABLE",
            "capabilities": ["BLS"],
            "crew": [
                {"name": "Sunita Verma", "role": "EMT Lead", "license_number": "EMT-4412"},
                {"name": "Amit Kumar", "role": "Emergency Driver", "license_number": "DRV-8821"},
            ],
            "current_location": {"type": "Point", "coordinates": [77.2020, 28.6100]},
            "location": {"type": "Point", "coordinates": [77.2020, 28.6100]},
            "heading_deg": 180.0,
            "speed_kmh": 0.0,
            "last_seen_at": now.isoformat(),
            "active_incident_id": None,
        },
        {
            "_id": "amb-delhi-1083",
            "created_at": now,
            "updated_at": now,
            "registration": "DL-03-AMB-1083",
            "operator_id": "Delhi-EMS-North",
            "status": "AVAILABLE",
            "capabilities": ["ALS", "NEONATAL"],
            "crew": [
                {"name": "Priya Nair", "role": "Critical Care Paramedic", "license_number": "MED-7719"},
            ],
            "current_location": {"type": "Point", "coordinates": [77.2280, 28.6250]},
            "location": {"type": "Point", "coordinates": [77.2280, 28.6250]},
            "heading_deg": 270.0,
            "speed_kmh": 0.0,
            "last_seen_at": now.isoformat(),
            "active_incident_id": None,
        },
        {
            "_id": "amb-delhi-1084",
            "created_at": now,
            "updated_at": now,
            "registration": "DL-04-AMB-1084",
            "operator_id": "Delhi-EMS-West",
            "status": "AVAILABLE",
            "capabilities": ["ALS", "TRAUMA"],
            "crew": [
                {"name": "Rohan Mehra", "role": "Senior Paramedic", "license_number": "MED-3341"},
            ],
            "current_location": {"type": "Point", "coordinates": [77.1900, 28.6400]},
            "location": {"type": "Point", "coordinates": [77.1900, 28.6400]},
            "heading_deg": 90.0,
            "speed_kmh": 0.0,
            "last_seen_at": now.isoformat(),
            "active_incident_id": None,
        },
    ]

    for amb in ambulances:
        await db.ambulances.update_one({"_id": amb["_id"]}, {"$set": amb}, upsert=True)
    print(f"Seeded/Updated {len(ambulances)} ambulances")

    # 2. Seed demo incidents
    demo_incidents = [
        {
            "_id": "inc-demo-cardiac-01",
            "caller_id": "caller-9876543210",
            "idempotency_key": "demo-cardiac-01",
            "request_hash": "hash-cardiac-01",
            "location": {"type": "Point", "coordinates": [77.2195, 28.6315]},
            "accuracy_m": 8.0,
            "address": "Inner Circle, Connaught Place, Block B, New Delhi",
            "severity": "CRITICAL",
            "status": "QUEUED",
            "caller_info": {
                "name": "Ramesh Gupta",
                "phone": "+91 98765 43210",
                "notes": "🔴 CRITICAL: Acute crushing chest pain, radiating to left arm. Profuse diaphoresis, shortness of breath. Bystander assistance requested.",
            },
            "assigned_unit_id": None,
            "destination_hospital_id": "hosp-aiims-01",
            "parent_incident_id": None,
            "child_incident_ids": [],
            "received_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "eta_seconds": 240,
        },
        {
            "_id": "inc-demo-trauma-02",
            "caller_id": "caller-9811223344",
            "idempotency_key": "demo-trauma-02",
            "request_hash": "hash-trauma-02",
            "location": {"type": "Point", "coordinates": [77.2075, 28.5714]},
            "accuracy_m": 12.0,
            "address": "Safdarjung Flyover, Ring Road Northbound",
            "severity": "HIGH",
            "status": "QUEUED",
            "caller_info": {
                "name": "Pooja Sharma",
                "phone": "+91 98112 23344",
                "notes": "🟠 HIGH: High-speed motorcycle collision. Compound lower limb injury with active hemorrhage. Conscious, severe distress.",
            },
            "assigned_unit_id": None,
            "destination_hospital_id": "hosp-aiims-01",
            "parent_incident_id": None,
            "child_incident_ids": [],
            "received_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "eta_seconds": 380,
        },
        {
            "_id": "inc-demo-asthma-03",
            "caller_id": "caller-9899112233",
            "idempotency_key": "demo-asthma-03",
            "request_hash": "hash-asthma-03",
            "location": {"type": "Point", "coordinates": [77.2433, 28.5677]},
            "accuracy_m": 15.0,
            "address": "Central Market, Lajpat Nagar II, New Delhi",
            "severity": "MEDIUM",
            "status": "VALIDATING",
            "caller_info": {
                "name": "Ananya Roy",
                "phone": "+91 98991 12233",
                "notes": "🟡 MEDIUM: Acute asthmatic attack. Inhaler refractory. Audible wheezing and tachypnea.",
            },
            "assigned_unit_id": None,
            "destination_hospital_id": None,
            "parent_incident_id": None,
            "child_incident_ids": [],
            "received_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "eta_seconds": None,
        },
        {
            "_id": "inc-demo-fall-04",
            "caller_id": "caller-9711002233",
            "idempotency_key": "demo-fall-04",
            "request_hash": "hash-fall-04",
            "location": {"type": "Point", "coordinates": [77.1906, 28.6517]},
            "accuracy_m": 20.0,
            "address": "Near Karol Bagh Metro Station Gate 2",
            "severity": "LOW",
            "status": "RECEIVED",
            "caller_info": {
                "name": "Sanjay Verma",
                "phone": "+91 97110 02233",
                "notes": "🟢 LOW: Slip and fall. Right wrist swelling and forehead abrasion. Ambulatory, vitals stable.",
            },
            "assigned_unit_id": None,
            "destination_hospital_id": None,
            "parent_incident_id": None,
            "child_incident_ids": [],
            "received_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "eta_seconds": None,
        },
    ]

    for inc in demo_incidents:
        await db.incidents.update_one({"_id": inc["_id"]}, {"$set": inc}, upsert=True)
    print(f"Seeded/Updated {len(demo_incidents)} demo incidents")

    # 3. Seed hospitals
    hospitals = [
        {
            "_id": "hosp-aiims-01",
            "created_at": now,
            "updated_at": now,
            "name": "AIIMS Apex Trauma Center — Level 1",
            "location": {"type": "Point", "coordinates": [77.2088, 28.5672]},
            "address": "Ring Rd, Safdarjung Enclave, New Delhi 110029",
            "phone": "+91-11-26588500",
            "capabilities": ["TRAUMA", "CARDIAC", "STROKE", "BURNS"],
            "capacity": {
                "resus_beds_available": 4,
                "icu_beds_available": 2,
                "ed_wait_minutes": 5,
                "last_updated_at": now.isoformat(),
            },
            "helipad": True,
        },
        {
            "_id": "hosp-safdarjung-02",
            "created_at": now,
            "updated_at": now,
            "name": "Safdarjung Hospital Emergency Care",
            "location": {"type": "Point", "coordinates": [77.2075, 28.5714]},
            "address": "Ansari Nagar West, New Delhi 110029",
            "phone": "+91-11-26165060",
            "capabilities": ["TRAUMA", "CARDIAC", "PAEDIATRIC"],
            "capacity": {
                "resus_beds_available": 6,
                "icu_beds_available": 5,
                "ed_wait_minutes": 8,
                "last_updated_at": now.isoformat(),
            },
            "helipad": False,
        },
    ]

    for hosp in hospitals:
        await db.hospitals.update_one({"_id": hosp["_id"]}, {"$set": hosp}, upsert=True)
    print(f"Seeded/Updated {len(hospitals)} hospitals")

    client.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
