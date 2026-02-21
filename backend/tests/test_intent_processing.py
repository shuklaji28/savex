"""
Tests for POST /api/process-text intent classification feature.
Tests cover: add intent, mark_used intent, mark_wasted intent, mixed intents, not_found case.
Each test relies on LLM (Gemini) so responses may take a few seconds.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session for this module"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def cleanup_test_items(api_client):
    """Track items created during tests so we can clean them up"""
    created_ids = []
    yield created_ids
    # Cleanup: mark all test items as used/wasted
    for item_id in created_ids:
        try:
            api_client.put(
                f"{BASE_URL}/api/inventory/{item_id}/status",
                json={"status": "wasted"}
            )
        except Exception:
            pass


# ─── Helper to POST process-text ───
def process_text(api_client, text, timeout=30):
    """Call /api/process-text and return parsed JSON"""
    resp = api_client.post(
        f"{BASE_URL}/api/process-text",
        json={"text": text},
        timeout=timeout
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


class TestAddIntent:
    """Test pure 'add' intent: buying new items"""

    def test_add_two_items(self, api_client, cleanup_test_items):
        """POST 'I bought milk and bananas' → items=2, updated_items=[], not_found=[]"""
        data = process_text(api_client, "I bought milk and bananas")
        print(f"Response: {data}")

        # Should have no error
        assert "error" not in data or data.get("error") is None, f"Unexpected error: {data.get('error')}"

        added = data.get("items", [])
        updated = data.get("updated_items", [])
        not_found = data.get("not_found", [])

        assert len(added) == 2, f"Expected 2 added items, got {len(added)}: {[i.get('normalized_name') for i in added]}"
        assert len(updated) == 0, f"Expected 0 updated items, got {len(updated)}"
        assert len(not_found) == 0, f"Expected 0 not_found, got {len(not_found)}"

        names = [item["normalized_name"] for item in added]
        print(f"✓ Added items: {names}")
        assert any("milk" in n for n in names), f"milk not found in {names}"
        assert any("banana" in n for n in names), f"banana not found in {names}"

        # Track created IDs for cleanup
        for item in added:
            cleanup_test_items.append(item["id"])

        # Verify count field
        assert data.get("count", 0) == 2, f"Expected count=2, got {data.get('count')}"
        print("✓ test_add_two_items PASSED")


class TestMarkWastedIntent:
    """Test 'mark_wasted' intent: item expired/went bad"""

    def test_milk_expired(self, api_client, cleanup_test_items):
        """
        Flow: 
          1. Add milk to inventory
          2. POST 'the milk expired, I couldn't use it' → updated_items=[milk:wasted], items=[], not_found=[]
          3. Verify milk no longer in active inventory
        """
        # Step 1: Add milk to inventory
        setup = process_text(api_client, "I bought fresh milk")
        added_setup = setup.get("items", [])
        assert len(added_setup) >= 1, "Pre-condition: milk should be added"
        milk_item = next((i for i in added_setup if "milk" in i.get("normalized_name", "")), None)
        assert milk_item is not None, f"milk not in added items: {added_setup}"
        milk_id = milk_item["id"]
        cleanup_test_items.append(milk_id)
        print(f"✓ Pre-condition: milk added with id={milk_id}")

        time.sleep(1)  # brief pause before next LLM call

        # Step 2: Mark milk as wasted via text
        data = process_text(api_client, "the milk expired, I couldn't use it")
        print(f"Response: {data}")

        added = data.get("items", [])
        updated = data.get("updated_items", [])
        not_found = data.get("not_found", [])

        assert len(added) == 0, f"Expected 0 added items, got {len(added)}"
        assert len(updated) >= 1, f"Expected >=1 updated items, got {len(updated)}: {not_found}"
        
        updated_milk = next((i for i in updated if "milk" in i.get("normalized_name", "")), None)
        assert updated_milk is not None, f"milk not in updated_items: {updated}"
        assert updated_milk["status"] == "wasted", f"Expected status=wasted, got {updated_milk['status']}"
        print(f"✓ Milk marked as wasted: {updated_milk}")

        # Step 3: Verify the specific updated milk item is no longer active
        time.sleep(0.5)
        updated_milk_id = updated_milk["id"]
        inv_resp = api_client.get(f"{BASE_URL}/api/inventory")
        active_ids = [i["id"] for i in inv_resp.json().get("items", [])]
        assert updated_milk_id not in active_ids, f"Updated milk (id={updated_milk_id}) still in active inventory"
        # Verify in history
        hist_resp = api_client.get(f"{BASE_URL}/api/inventory/history")
        hist_ids = [i["id"] for i in hist_resp.json().get("items", [])]
        assert updated_milk_id in hist_ids, f"Updated milk (id={updated_milk_id}) not found in history"
        print(f"✓ Milk (id={updated_milk_id}) confirmed removed from inventory and added to history")
        print("✓ test_milk_expired PASSED")


class TestMarkUsedIntent:
    """Test 'mark_used' intent: item was consumed"""

    def test_bananas_used(self, api_client, cleanup_test_items):
        """
        Flow:
          1. Add bananas to inventory
          2. POST 'I used the bananas' → updated_items=[banana:used], items=[]
        """
        # Step 1: Add bananas
        setup = process_text(api_client, "I bought bananas")
        added_setup = setup.get("items", [])
        assert len(added_setup) >= 1, "Pre-condition: bananas should be added"
        banana_item = next((i for i in added_setup if "banana" in i.get("normalized_name", "")), None)
        assert banana_item is not None, f"banana not in added items: {added_setup}"
        banana_id = banana_item["id"]
        cleanup_test_items.append(banana_id)
        print(f"✓ Pre-condition: banana added with id={banana_id}")

        time.sleep(1)

        # Step 2: Mark bananas as used
        data = process_text(api_client, "I used the bananas")
        print(f"Response: {data}")

        added = data.get("items", [])
        updated = data.get("updated_items", [])
        not_found = data.get("not_found", [])

        assert len(added) == 0, f"Expected 0 added items, got {len(added)}"
        assert len(updated) >= 1, f"Expected >=1 updated items, got {len(updated)}"

        updated_banana = next((i for i in updated if "banana" in i.get("normalized_name", "")), None)
        assert updated_banana is not None, f"banana not in updated_items: {updated}"
        assert updated_banana["status"] == "used", f"Expected status=used, got {updated_banana['status']}"
        print(f"✓ Banana marked as used: {updated_banana}")
        print("✓ test_bananas_used PASSED")


class TestMixedIntent:
    """Test mixed intents in single message: add + mark_wasted"""

    def test_add_eggs_and_waste_milk(self, api_client, cleanup_test_items):
        """
        Flow:
          1. Add milk to inventory (pre-condition)
          2. POST 'I bought eggs and threw away the milk'
             → items=[egg], updated_items=[milk:wasted]
        """
        # Step 1: Add milk
        setup = process_text(api_client, "I got some milk from the store")
        added_setup = setup.get("items", [])
        assert len(added_setup) >= 1, "Pre-condition: milk should be added"
        milk_item = next((i for i in added_setup if "milk" in i.get("normalized_name", "")), None)
        assert milk_item is not None, f"milk not found in {added_setup}"
        cleanup_test_items.append(milk_item["id"])
        print(f"✓ Pre-condition: milk added (id={milk_item['id']})")

        time.sleep(1)

        # Step 2: Mixed message
        data = process_text(api_client, "I bought eggs and threw away the milk")
        print(f"Response: {data}")

        added = data.get("items", [])
        updated = data.get("updated_items", [])
        not_found = data.get("not_found", [])

        # Egg should be added
        assert len(added) >= 1, f"Expected >=1 added items (egg), got {len(added)}"
        added_names = [i.get("normalized_name", "") for i in added]
        assert any("egg" in n for n in added_names), f"egg not in added items: {added_names}"
        print(f"✓ Added items: {added_names}")

        # Milk should be marked wasted
        assert len(updated) >= 1, f"Expected >=1 updated items (milk), got {len(updated)}"
        updated_milk = next((i for i in updated if "milk" in i.get("normalized_name", "")), None)
        assert updated_milk is not None, f"milk not in updated_items: {updated}"
        assert updated_milk["status"] == "wasted", f"Expected milk status=wasted, got {updated_milk['status']}"
        print(f"✓ Milk marked as wasted in mixed intent")

        # Track eggs for cleanup
        for item in added:
            cleanup_test_items.append(item["id"])
        print("✓ test_add_eggs_and_waste_milk PASSED")


class TestNotFoundIntent:
    """Test not_found when item is not in inventory"""

    def test_unknown_item_not_found(self, api_client):
        """
        POST 'the broccoli went bad' when broccoli is NOT in inventory
        → not_found=[broccoli], items=[], updated_items=[]
        """
        # First ensure broccoli is NOT in inventory by marking any broccoli as wasted
        inv_resp = api_client.get(f"{BASE_URL}/api/inventory")
        active_items = inv_resp.json().get("items", [])
        for item in active_items:
            if "broccoli" in item.get("normalized_name", ""):
                api_client.put(
                    f"{BASE_URL}/api/inventory/{item['id']}/status",
                    json={"status": "wasted"}
                )
                print(f"Cleaned up existing broccoli from inventory")

        # Now test not_found
        data = process_text(api_client, "the broccoli went bad")
        print(f"Response: {data}")

        added = data.get("items", [])
        updated = data.get("updated_items", [])
        not_found = data.get("not_found", [])

        assert len(added) == 0, f"Expected 0 added items, got {len(added)}"
        assert len(updated) == 0, f"Expected 0 updated items, got {len(updated)}"
        assert len(not_found) >= 1, f"Expected >=1 not_found items, got {not_found}"

        not_found_names = [nf.get("name", "") for nf in not_found]
        assert any("broccoli" in n for n in not_found_names), f"broccoli not in not_found: {not_found}"
        print(f"✓ not_found contains broccoli: {not_found}")
        print("✓ test_unknown_item_not_found PASSED")

    def test_response_structure(self, api_client):
        """Verify /api/process-text response always has required fields"""
        data = process_text(api_client, "I bought some rice")
        print(f"Response: {data}")

        required_fields = ["transcript", "items", "updated_items", "not_found", "count"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Items should be list
        assert isinstance(data["items"], list), "items should be a list"
        assert isinstance(data["updated_items"], list), "updated_items should be a list"
        assert isinstance(data["not_found"], list), "not_found should be a list"

        print(f"✓ Response structure valid: {list(data.keys())}")
        print("✓ test_response_structure PASSED")

        # Cleanup rice
        for item in data.get("items", []):
            api_client.put(
                f"{BASE_URL}/api/inventory/{item['id']}/status",
                json={"status": "wasted"}
            )
