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
    # Give it a larger viewport so graphs render well
    context = browser.new_context(viewport={"width": 1440, "height": 1080})
    page = context.new_page()
    
    page.goto(f"{server_url}/login")
        
    # Login as Super Admin
    page.fill("input[name='email']", "anil@blissfulabodes.com")
    page.fill("input[name='password']", "Admin@123")
    page.click("button[type='submit']")

    # Navigate to Super Admin Dashboard
    page.goto(f"{server_url}/superadmin/dashboard")
    page.wait_for_timeout(3000)
    
    # Check if we can locate the Multi-Year Revenue Trend card
    element = page.locator("h3:has-text('Multi-Year Revenue Trend'), span:has-text('Multi-Year Revenue Trend')").locator("xpath=../..")
    # Also attempt to grab the System Status if it's nearby, but a full page screenshot or top-half is fine
    
    # We will just take a full page screenshot and also attempt a targeted one if the element exists
    if element.count() > 0:
        # Get its bounding box and the one next to it to screenshot the row
        row = element.locator("xpath=..")
        row.screenshot(path="Fig_5.7_System_Performance_Graph.png")
        print("Image saved successfully as Fig_5.7_System_Performance_Graph.png (Row capture)!")
    else:
        page.screenshot(path="Fig_5.7_System_Performance_Graph.png", full_page=True)
        print("Image saved successfully as Fig_5.7_System_Performance_Graph.png (Full page)!")

    browser.close()

with sync_playwright() as p:
    try:
        run(p)
    except Exception as e:
        print(f"Error encountered: {e}")
