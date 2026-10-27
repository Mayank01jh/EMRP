import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb+srv://Mayank1234:mayank1234@mydata.ezd5wcv.mongodb.net/?retryWrites=true&w=majority")
    db = client.emrp
    now = datetime.now(timezone.utc)
    coords = [
        ("DL-01-AMB-1081", [77.2195, 28.6315], "AVAILABLE"),
        ("DL-02-AMB-1082", [77.2220, 28.5720], "AVAILABLE"),
        ("DL-03-AMB-1083", [77.2430, 28.5680], "AVAILABLE"),
    ]
    for reg, pos, st in coords:
        res = await db.ambulances.update_one(
            {"registration": reg},
            {"$set": {
                "location": {"type": "Point", "coordinates": pos},
                "last_seen_at": now,
                "status": st,
                "updated_at": now
            }}
        )
        print(f"Updated {reg}: {res.modified_count} modified")
    print("All ambulances seeded with Delhi coordinates & active last_seen_at!")

if __name__ == "__main__":
    asyncio.run(main())
