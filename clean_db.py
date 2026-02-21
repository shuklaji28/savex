import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

KEEP_NAMES = [
    'diet coke #2',
    'Magi pack',
    '6 eggs',
    '1 kg paneer',
    'half kilo chicken',
    'cabbage',
    'apple',
]

async def clean():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['test_database']

    # Delete ALL used/wasted history
    r1 = await db.food_items.delete_many({"status": {"$in": ["used", "wasted"]}})
    print(f"Deleted {r1.deleted_count} used/wasted items")

    # Get all active items
    all_active = await db.food_items.find({"status": "active"}, {"_id": 0, "id": 1, "item_name": 1}).to_list(200)

    # Keep best match for each name, delete rest
    keep_ids = set()
    for target in KEEP_NAMES:
        for item in all_active:
            if item["item_name"].lower() == target.lower():
                keep_ids.add(item["id"])
                break
        else:
            for item in all_active:
                if target.lower() in item["item_name"].lower() or item["item_name"].lower() in target.lower():
                    keep_ids.add(item["id"])
                    break

    print(f"Keeping {len(keep_ids)} items")
    delete_ids = [i["id"] for i in all_active if i["id"] not in keep_ids]
    r2 = await db.food_items.delete_many({"id": {"$in": delete_ids}})
    print(f"Deleted {r2.deleted_count} extra active items")

    # Show remaining
    remaining = await db.food_items.find({"status": "active"}, {"_id": 0, "item_name": 1, "expiry_date": 1, "estimated_cost_inr": 1, "storage_location": 1}).to_list(20)
    print("\n--- Remaining items ---")
    for i in remaining:
        print(f"  {i['item_name']} | expiry: {i.get('expiry_date','?')} | ₹{i.get('estimated_cost_inr',0)} | loc: {i.get('storage_location','?')}")

    pm = await db.price_memory.count_documents({})
    print(f"\nPrice memory entries: {pm}")

asyncio.run(clean())
