# ✅ Step-by-Step AWS Deployment — Blissful Abodes Hotel System

## Overview
- **Platform**: Amazon EC2 (Ubuntu 22.04)
- **Web Server**: Nginx
- **App Server**: Gunicorn (already in requirements.txt)
- **Language**: Python 3.11+
- **Database**: SQLite (blissful_abodes.db — uploaded directly)
- **Time to complete**: ~45–60 minutes

---

## PHASE 1 — Create an AWS Account
1. Go to [https://aws.amazon.com/](https://aws.amazon.com/) and click **"Create an AWS Account"**
2. Enter your email, set a password, and fill in billing details
   - ⚠️ A debit/credit card is needed for verification, but `t2.micro` EC2 is **FREE** for 12 months
3. Choose the **"Basic Support – Free"** plan
4. Log in to the **AWS Management Console**

---

## PHASE 2 — Launch an EC2 Server
1. In the AWS Console, search for **EC2** and click on it
2. Click **"Launch Instance"** (orange button)
3. Fill in the settings:

   | Setting | Value |
   |---------|-------|
   | **Name** | `blissful-abodes-server` |
   | **AMI (OS)** | Ubuntu Server 22.04 LTS (Free tier eligible) |
   | **Instance Type** | `t2.micro` (Free tier) |
   | **Key Pair** | Click "Create new key pair" → name it `aws-key` → RSA → `.pem` format → Download it |
   | **Allow SSH** | ✅ Yes (from Anywhere) |
   | **Allow HTTP** | ✅ Yes (from Anywhere) |
   | **Allow HTTPS** | ✅ Yes (from Anywhere) |
   | **Storage** | 20 GB (default is fine) |

4. Click **"Launch Instance"**
5. Wait 1–2 minutes until the Instance State shows **"Running"**
6. Copy the **Public IPv4 Address** (example: `54.123.45.67`) — you will need this

---

## PHASE 3 — Connect to the Server from Your Windows Laptop
1. Place the downloaded `aws-key.pem` file on your Desktop (e.g., `C:\Users\ajith\Desktop\aws-key.pem`)
2. Open **Windows PowerShell** as Administrator
3. First, fix the key file permissions (one-time only):
   ```powershell
   icacls "C:\Users\ajith\Desktop\aws-key.pem" /inheritance:r /grant:r "$($env:USERNAME):(R)"
   ```
4. Connect to the server:
   ```powershell
   ssh -i "C:\Users\ajith\Desktop\aws-key.pem" ubuntu@44.208.253.176
   ```
   *(If your EC2 Public IP is different, replace `44.208.253.176` with yours.)*
5. Type `yes` when asked about host authenticity
6. You should now see the Ubuntu terminal prompt (`ubuntu@ip-xxx-xxx:~$`) ✅

---

## PHASE 4 — Set Up the Server
Run these commands one by one in the Ubuntu terminal:

### Step 4.1 — Update Ubuntu
```bash
sudo apt update && sudo apt upgrade -y
```

### Step 4.2 — Install Python, Pip, Nginx, Git
```bash
sudo apt install python3-pip python3-venv nginx git -y
```

### Step 4.3 — Verify Python is installed
```bash
python3 --version
```
*(Should show Python 3.10+ or 3.11+)*

---

## PHASE 5 — Upload Your Project to the Server

### Option A: From GitHub (if your code is on GitHub)
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### Option B: Upload from Windows using SCP (if NOT on GitHub)
Open a **new PowerShell window on your laptop** (not the SSH one) and run:
```powershell
scp -i "C:\Users\ajith\Desktop\aws-key.pem" -r "C:\Users\ajith\Downloads\final year project" ubuntu@44.208.253.176:/home/ubuntu/blissful-abodes
```
Then in the SSH terminal:
```bash
cd /home/ubuntu/blissful-abodes
```

---

## PHASE 6 — Install Project Dependencies
In the SSH terminal, inside your project folder:

### Step 6.1 — Create virtual environment
```bash
python3 -m venv venv
```

### Step 6.2 — Activate virtual environment
```bash
source venv/bin/activate
```
*(You should see `(venv)` in the prompt)*

### Step 6.3 — Install requirements
```bash
pip install --upgrade pip
pip install wheel
pip install -r requirements.txt
```
*(This will take 2–5 minutes)*

---

## PHASE 7 — Set Your Secret API Keys
Your project needs the Gemini AI and Razorpay keys. Set them as environment variables:

```bash
export GEMINI_API_KEY="your-actual-gemini-api-key-here"
export RAZORPAY_KEY_ID="your-actual-razorpay-key-id"
export RAZORPAY_KEY_SECRET="your-actual-razorpay-secret"
export SECRET_KEY="any-random-long-string-here"
export FLASK_ENV="production"
```

To make them **permanent** (survive server restarts):
```bash
echo 'export GEMINI_API_KEY="your-actual-gemini-api-key-here"' >> ~/.bashrc
echo 'export RAZORPAY_KEY_ID="your-razorpay-key-id"' >> ~/.bashrc
echo 'export RAZORPAY_KEY_SECRET="your-razorpay-secret"' >> ~/.bashrc
echo 'export SECRET_KEY="any-random-long-string"' >> ~/.bashrc
echo 'export FLASK_ENV="production"' >> ~/.bashrc
source ~/.bashrc
```

---

## PHASE 8 — Test Your Application
```bash
# Make sure you are in the project folder with venv activated
gunicorn --bind 0.0.0.0:5000 app:app
```
Open your browser and visit: `http://44.208.253.176:5000`
If the website loads → Press `Ctrl+C` to stop and move to Phase 9 ✅

---

## PHASE 9 — Keep the App Running 24/7 with Systemd

### Step 9.1 — Find the full path of your project
```bash
pwd
```
*(Copy this path — example: `/home/ubuntu/blissful-abodes`)*

### Step 9.2 — Create a systemd service file
```bash
sudo nano /etc/systemd/system/blissfulabodes.service
```

### Step 9.3 — Paste this content (replace paths with YOUR actual path from Step 9.1)
```ini
[Unit]
Description=Gunicorn for Blissful Abodes Flask App
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/blissful-abodes
Environment="PATH=/home/ubuntu/blissful-abodes/venv/bin"
Environment="GEMINI_API_KEY=your-actual-gemini-api-key-here"
Environment="RAZORPAY_KEY_ID=your-razorpay-key-id"
Environment="RAZORPAY_KEY_SECRET=your-razorpay-secret"
Environment="SECRET_KEY=any-random-long-string"
Environment="FLASK_ENV=production"
ExecStart=/home/ubuntu/blissful-abodes/venv/bin/gunicorn --workers 3 --bind unix:/home/ubuntu/blissful-abodes/blissfulabodes.sock -m 007 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Step 9.4 — Save and exit
Press `Ctrl+O` → `Enter` → `Ctrl+X`

### Step 9.5 — Start and enable the service
```bash
sudo systemctl daemon-reload
sudo systemctl start blissfulabodes
sudo systemctl enable blissfulabodes
```

### Step 9.6 — Check it is running
```bash
sudo systemctl status blissfulabodes
```
*(Should show "active (running)" in green)* ✅

---

## PHASE 10 — Configure Nginx as the Web Proxy

### Step 10.1 — Create Nginx config for your site
```bash
sudo nano /etc/nginx/sites-available/blissfulabodes
```

### Step 10.2 — Paste this (if your IP is different, replace 44.208.253.176)
```nginx
server {
    listen 80;
    server_name 44.208.253.176;

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/blissful-abodes/blissfulabodes.sock;
    }

    location /static/ {
        alias /home/ubuntu/blissful-abodes/static/;
    }

    location /uploads/ {
        alias /home/ubuntu/blissful-abodes/uploads/;
    }

    client_max_body_size 20M;
}
```

### Step 10.3 — Enable the config
```bash
sudo ln -s /etc/nginx/sites-available/blissfulabodes /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
```

### Step 10.4 — Test Nginx config (must say "syntax is ok")
```bash
sudo nginx -t
```

### Step 10.5 — Restart Nginx
```bash
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## ✅ FINAL STEP — Open Your Website
Open your browser and visit:
```
http://44.208.253.176
```
(No port number needed — Nginx handles Port 80)

Your **Blissful Abodes Hotel Management System** with all 6 AI features should now be **live on the internet!** 🎉

---

## 🔧 Useful Commands (for future management)

| Task | Command |
|------|---------|
| Check app status | `sudo systemctl status blissfulabodes` |
| Restart app | `sudo systemctl restart blissfulabodes` |
| View app logs | `sudo journalctl -u blissfulabodes -f` |
| Restart Nginx | `sudo systemctl restart nginx` |
| View Nginx error logs | `sudo tail -f /var/log/nginx/error.log` |
| Update code from GitHub | `git pull && sudo systemctl restart blissfulabodes` |

---

## ❌ Common Errors and Fixes

| Error | Fix |
|-------|-----|
| `502 Bad Gateway` in browser | Run `sudo systemctl status blissfulabodes` to see Python errors |
| `Permission denied` on .pem file | Run the `icacls` command in Phase 3 again |
| `ModuleNotFoundError` | Run `source venv/bin/activate` then `pip install -r requirements.txt` again |
| Gemini chatbot not working | Check `GEMINI_API_KEY` is set correctly in the service file |
| Static files (CSS/images) not loading | Verify the `/static/` path in Nginx config matches your actual folder |
