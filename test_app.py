import sys
import traceback
from app import create_app

print("Creating app...")
app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
print("App created.")

with app.test_client() as client:
    try:
        print("Testing unauthenticated...")
        response = client.get("/")
        print(f"Status: {response.status_code}")

        print("Testing authenticated (Guest)...")
        # Login as guest
        response = client.post("/login", data={
            "email": "rajesh@example.com",
            "password": "Guest@123"
        }, follow_redirects=True)
        print(f"Login Status: {response.status_code}")

        response = client.get("/")
        print(f"Auth Status: {response.status_code}")
        if response.status_code != 200:
            print(response.data.decode("utf-8"))
            
        print("Testing authenticated (Admin)...")
        client.post("/login", data={"email": "anil@blissfulabodes.com", "password": "Admin@123"}, follow_redirects=True)
        response = client.get("/")
        print(f"Admin Status: {response.status_code}")
        if response.status_code != 200:
            print(response.data.decode("utf-8"))

    except Exception as e:
        print("Error during request:")
        traceback.print_exc()
