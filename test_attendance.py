import requests
import json

# Change to your server IP
BASE_URL = "http://192.168.1.100:8000/api/attendance"

def test_sign_in():
    """Test sign-in endpoint"""
    print("\n=== Testing Sign In ===")
    url = f"{BASE_URL}/create-vedant-attendance/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Cannot connect to server")
        print("Make sure Django server is running with: python manage.py runserver 0.0.0.0:8000")
    except requests.exceptions.Timeout:
        print("❌ Timeout Error: Server took too long to respond")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def test_sign_out():
    """Test sign-out endpoint"""
    print("\n=== Testing Sign Out ===")
    url = f"{BASE_URL}/signout-vedant-attendance/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Cannot connect to server")
    except requests.exceptions.Timeout:
        print("❌ Timeout Error: Server took too long to respond")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def test_today_attendance():
    """Test today's attendance endpoint"""
    print("\n=== Testing Today's Attendance ===")
    url = f"{BASE_URL}/attendance/today/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print(f"Total Records: {len(data)}")
        if len(data) > 0:
            print(f"Sample Record: {json.dumps(data[0], indent=2)}")
        return data
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def test_attendance_report():
    """Test attendance report endpoint"""
    print("\n=== Testing Attendance Report ===")
    url = f"{BASE_URL}/attendance/report/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def test_all():
    """Run all tests"""
    print("=" * 50)
    print("Django API Test Suite")
    print("=" * 50)
    
    # Test 1: Sign In
    result1 = test_sign_in()
    
    # Wait a bit
    import time
    time.sleep(2)
    
    # Test 2: Sign Out
    result2 = test_sign_out()
    
    # Test 3: Today's Attendance
    test_today_attendance()
    
    # Test 4: Attendance Report
    test_attendance_report()
    
    print("\n" + "=" * 50)
    print("Tests Complete!")
    print("=" * 50)

if __name__ == "__main__":
    # Install requests if needed: pip install requests
    test_all()
