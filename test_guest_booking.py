import requests
import time
from datetime import datetime, timedelta

def wait_for_server():
    print("Waiting for server to start...")
    for _ in range(60):
        try:
            r = requests.get('http://127.0.0.1:5000/')
            if r.status_code == 200:
                print("Server is up!")
                return True
        except:
            pass
        time.sleep(5)
    print("Server did not start in time.")
    return False

def test_checkout(email, expected_flash):
    print(f"\n--- Testing with email: {email} ---")
    session = requests.Session()
    # First get the page to get any session cookies if needed
    r = session.get('http://127.0.0.1:5000/guest-checkout/room_S_107')
    
    ci = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    co = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    
    data = {
        'guest_name': 'Test User',
        'guest_email': email,
        'guest_phone': '9876543210',
        'check_in': ci,
        'check_out': co,
        'num_guests': '1'
    }
    
    r = session.post('http://127.0.0.1:5000/guest-checkout/room_S_107', data=data)
    print(f"Status Code: {r.status_code}")
    print(f"URL after POST: {r.url}")
    
    if expected_flash in r.text:
        print("SUCCESS! Found expected text/flash message.")
    else:
        print("FAILED! Did not find expected text.")
        if "Booking failed" in r.text:
            print("Found 'Booking failed' error. Checking snippet:")
            idx = r.text.find("Booking failed")
            print(r.text[idx:idx+100])
        elif "⚠️ Booking blocked" in r.text:
             print("Found 'Booking blocked' message.")

if __name__ == '__main__':
    if wait_for_server():
        # Test 1: Disposable email (should be caught by AI Fraud)
        test_checkout('tester@mailinator.com', 'Booking blocked: High fraud risk')
        
        # Test 2: Normal email (should succeed)
        test_checkout('tester@gmail.com', 'Booking Confirmed')
