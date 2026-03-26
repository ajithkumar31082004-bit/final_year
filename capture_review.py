import time
import requests
from playwright.sync_api import sync_playwright

print("Waiting for server to start on port 5001 or 5000...")
server_url = "http://127.0.0.1:5001"
started = False

for _ in range(10):
    try:
        r = requests.get(f"{server_url}/login", timeout=2)
        if r.status_code == 200:
            started = True
            break
    except Exception:
        pass
    
    try:
        r2 = requests.get("http://127.0.0.1:5000/login", timeout=2)
        if r2.status_code == 200:
            server_url = "http://127.0.0.1:5000"
            started = True
            break
    except Exception:
        pass
        
    time.sleep(2)

if not started:
    print("Server did not respond properly, trying to run anyway...")

print(f"Connected to server at {server_url}. Launching playwright...")

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1080})
    page = context.new_page()
    
    page.goto(f"{server_url}/login")
        
    # Login as Admin
    page.fill("input[name='email']", "anil@blissfulabodes.com")
    page.fill("input[name='password']", "Admin@123")
    page.click("button[type='submit']")

    # Navigate to Admin Reviews Management page
    page.goto(f"{server_url}/admin/reviews")
    page.wait_for_timeout(3000)
    
    # Locate the AI Review Insights or the main content
    # Let's take a screenshot of the whole page since it shows the full Review & Rating System Output
    page.screenshot(path="Fig_5.14_Output_of_Review_and_Rating_System.png", full_page=True)
    print("Image saved successfully as Fig_5.14_Output_of_Review_and_Rating_System.png!")

    browser.close()

with sync_playwright() as p:
    try:
        run(p)
    except Exception as e:
        print(f"Error encountered: {e}")
