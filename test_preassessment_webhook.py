"""
Test script for pre-assessment webhook endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_webhook():
    """Test the pre-assessment webhook endpoint"""
    
    print("\n" + "=" * 80)
    print("TESTING PRE-ASSESSMENT WEBHOOK")
    print("=" * 80)
    
    # Test payload
    payload = {
        "organization_id": "682ae94fa2e778c597d09b57",
        "preassessment_id": "507f1f77bcf86cd799439011",
        "regulation_id": "6981ea4cb358c36d4be852be"
    }
    
    print("\n1. Sending webhook...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhook/preassessment",
            json=payload,
            timeout=10
        )
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Webhook sent successfully!")
        else:
            print(f"\n❌ Webhook failed with status {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return
    
    # Check received webhooks
    print("\n" + "=" * 80)
    print("2. Checking received webhooks...")
    
    try:
        response = requests.get(f"{BASE_URL}/webhook/received")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Clear webhooks
    print("\n" + "=" * 80)
    print("3. Clearing received webhooks...")
    
    try:
        response = requests.delete(f"{BASE_URL}/webhook/received")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\nMake sure the API is running on http://localhost:8000")
    print("Start it with: python -m uvicorn app.main:app --reload\n")
    
    input("Press Enter to start test...")
    test_webhook()
