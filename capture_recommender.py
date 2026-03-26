import time
import requests
from playwright.sync_api import sync_playwright

print("Waiting for server to start on port 5001 or 5000...")
server_url = "http://127.0.0.1:5001"
started = False

for _ in range(30):
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
    print("Server did not start within 60 seconds.")
    exit(1)

print(f"Connected to server at {server_url}. Launching playwright...")

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    # Give it a larger viewport so the recommended rooms grid fits well in one line/scroll
    context = browser.new_context(viewport={"width": 1440, "height": 1080})
    page = context.new_page()
    
    page.goto(f"{server_url}/login")
        
    page.fill("input[name='email']", "rajesh@example.com")
    page.fill("input[name='password']", "Guest@123")
    page.click("button[type='submit']")

    # Navigate to dashboard
    page.goto(f"{server_url}/dashboard")
    page.wait_for_timeout(3000)
    
    # Locate the AI recommendation section and screenshot it
    element = page.locator("h3:has-text('AI Recommended')").locator("xpath=..")
    if element.count() > 0:
        # Save straight to root directory
        element.screenshot(path="Fig_5.12_Output_of_AI_Recommendation_System.png")
        print("Image saved successfully as Fig_5.12_Output_of_AI_Recommendation_System.png!")
    else:
        page.screenshot(path="Fig_5.12_Output_of_AI_Recommendation_System.png", full_page=True)
        print("Recommendation element not found, saved full page screenshot instead.")

    browser.close()

with sync_playwright() as p:
    try:
        run(p)
    except Exception as e:
        print(f"Error encountered: {e}")
