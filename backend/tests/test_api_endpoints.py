import pytest
import requests
import os
from datetime import date

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL').rstrip('/')

class TestHealthCheck:
    """Health check endpoint test"""

    def test_root_endpoint(self, api_client):
        """Test GET /api/ returns 200 with correct structure"""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert data["message"] == "Sustain API"
        assert "date" in data
        assert data["date"] == date.today().isoformat()
        print(f"✓ Health check passed: {data}")


class TestInventory:
    """Inventory endpoint tests"""

    def test_get_inventory(self, api_client):
        """Test GET /api/inventory returns items grouped and sorted by urgency"""
        response = api_client.get(f"{BASE_URL}/api/inventory")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        print(f"✓ Inventory returned {len(data['items'])} active items")
        
        # Verify items are sorted by days_remaining (ascending)
        if len(data["items"]) > 1:
            days_list = [item["days_remaining"] for item in data["items"]]
            assert days_list == sorted(days_list), "Items should be sorted by days_remaining"
            print(f"✓ Items correctly sorted by urgency: {days_list[:5]}")
        
        # Verify each item has required fields
        if data["items"]:
            item = data["items"][0]
            required_fields = ["id", "item_name", "normalized_name", "quantity", "unit", 
                             "storage_location", "category", "added_date", "expiry_date", 
                             "status", "days_remaining", "urgency_level"]
            for field in required_fields:
                assert field in item, f"Missing field: {field}"
            print(f"✓ Item structure valid: {item['normalized_name']} ({item['urgency_level']})")

    def test_get_history(self, api_client):
        """Test GET /api/inventory/history returns past items"""
        response = api_client.get(f"{BASE_URL}/api/inventory/history")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        print(f"✓ History returned {len(data['items'])} past items")
        
        # Verify history items have correct status
        for item in data["items"]:
            assert item["status"] in ["used", "wasted"], "History items should be used or wasted"
            assert "action_date" in item
        
        if data["items"]:
            print(f"✓ Sample history item: {data['items'][0]['normalized_name']} - {data['items'][0]['status']}")

    def test_get_single_item(self, api_client):
        """Test GET /api/inventory/{item_id} returns single item detail"""
        # First get inventory to get an item ID
        inv_response = api_client.get(f"{BASE_URL}/api/inventory")
        items = inv_response.json()["items"]
        
        if not items:
            pytest.skip("No active items to test")
        
        item_id = items[0]["id"]
        response = api_client.get(f"{BASE_URL}/api/inventory/{item_id}")
        assert response.status_code == 200
        
        item = response.json()
        assert item["id"] == item_id
        assert "days_remaining" in item
        assert "urgency_level" in item
        print(f"✓ Single item fetch: {item['normalized_name']} (ID: {item_id})")


class TestInventoryActions:
    """Test marking items as used or wasted"""

    def test_mark_item_as_used(self, api_client):
        """Test PUT /api/inventory/{item_id}/status marks item as used"""
        # Get an active item
        inv_response = api_client.get(f"{BASE_URL}/api/inventory")
        items = inv_response.json()["items"]
        
        if not items:
            pytest.skip("No active items to test")
        
        # Use the last item (least urgent) for testing
        test_item = items[-1]
        item_id = test_item["id"]
        item_name = test_item["normalized_name"]
        
        # Mark as used
        response = api_client.put(
            f"{BASE_URL}/api/inventory/{item_id}/status",
            json={"status": "used"}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] == True
        assert result["item_id"] == item_id
        assert result["status"] == "used"
        print(f"✓ Marked '{item_name}' as used (ID: {item_id})")
        
        # Verify item is no longer in active inventory
        verify_response = api_client.get(f"{BASE_URL}/api/inventory")
        active_ids = [item["id"] for item in verify_response.json()["items"]]
        assert item_id not in active_ids, "Used item should not be in active inventory"
        print(f"✓ Verified '{item_name}' removed from active inventory")
        
        # Verify item appears in history
        history_response = api_client.get(f"{BASE_URL}/api/inventory/history")
        history_items = history_response.json()["items"]
        history_item = next((item for item in history_items if item["id"] == item_id), None)
        assert history_item is not None, "Used item should appear in history"
        assert history_item["status"] == "used"
        print(f"✓ Verified '{item_name}' appears in history as 'used'")


class TestReports:
    """Reports endpoint tests"""

    def test_get_reports(self, api_client):
        """Test GET /api/reports returns correct structure with overall, streaks, weekly, monthly data"""
        response = api_client.get(f"{BASE_URL}/api/reports")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify main structure
        assert "overall" in data
        assert "streaks" in data
        assert "weekly" in data
        assert "monthly" in data
        print("✓ Reports structure valid")
        
        # Verify overall fields
        overall = data["overall"]
        required_overall = ["saved_weight_kg", "wasted_weight_kg", "money_saved_inr", 
                           "co2_saved_kg", "waste_ratio", "most_wasted_category", "total_items_tracked"]
        for field in required_overall:
            assert field in overall, f"Missing overall field: {field}"
        print(f"✓ Overall metrics: {overall['total_items_tracked']} items tracked")
        
        # Verify streaks fields
        streaks = data["streaks"]
        assert "current_streak_days" in streaks
        assert "longest_streak_days" in streaks
        print(f"✓ Streaks: current={streaks['current_streak_days']}, longest={streaks['longest_streak_days']}")
        
        # Verify weekly fields
        weekly = data["weekly"]
        required_period = ["items_saved", "items_wasted", "saved_weight_kg", "money_saved_inr", "co2_saved_kg"]
        for field in required_period:
            assert field in weekly, f"Missing weekly field: {field}"
        print(f"✓ Weekly: {weekly['items_saved']} saved, {weekly['items_wasted']} wasted")
        
        # Verify monthly fields
        monthly = data["monthly"]
        for field in required_period:
            assert field in monthly, f"Missing monthly field: {field}"
        print(f"✓ Monthly: {monthly['items_saved']} saved, {monthly['items_wasted']} wasted")


class TestNotifications:
    """Notifications endpoint tests"""

    def test_get_notifications(self, api_client):
        """Test GET /api/notifications returns items needing attention"""
        response = api_client.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200
        
        data = response.json()
        assert "notify_today" in data
        assert "expired_items" in data
        assert "cook_today" in data
        print(f"✓ Notifications: {len(data['notify_today'])} items need attention")
        print(f"✓ Expired: {len(data['expired_items'])}, Cook today: {len(data['cook_today'])}")
