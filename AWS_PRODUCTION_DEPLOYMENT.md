# AWS Cloud Deployment Guide: Blissful Abodes

This guide provides the exact terminal commands and steps needed to deploy your AI-powered Hotel Management System to your production AWS EC2 instance (`13.206.110.152`).

## 🏗️ Architecture Overview
* **Compute:** AWS EC2 (Ubuntu 22.04 LTS)
* **Web Server:** Nginx (Reverse Proxy)
* **App Server:** Gunicorn (WSGI)
* **Database:** SQLite (Currently) / Amazon RDS (Optional)
* **Cloud Services Integrated:** Amazon DynamoDB (Logs), Amazon SNS (Alerts), IAM (Security), S3 (Media), Cognito (Auth).

---

## Step 1: Connect to your EC2 Instance
Open your local terminal and connect to your AWS EC2 instance using your `.pem` key:

```bash
# Set secure permissions for your key
chmod 400 your-aws-key.pem

# SSH into the server
ssh -i "your-aws-key.pem" ubuntu@13.206.110.152
```

## Step 2: System Setup & Dependencies
Once inside the EC2 instance, run the following commands to update the server and install necessary packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev nginx git libtiff5-dev libjpeg8-dev libopenjp2-7-dev zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk libharfbuzz-dev libfribidi-dev libxcb1-dev
```

## Step 3: Clone Project & Setup Python Environment
```bash
# Clone the repository (replace with your actual git URL)
git clone https://github.com/your-username/blissful-abodes.git
cd blissful-abodes

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python requirements
pip install -r requirements.txt
pip install gunicorn
```

## Step 4: Configure Environment Variables
You need to create your `.env` file on the server. We will copy the variables you are already using locally:

```bash
nano .env
```
*Paste your local `.env` content into this file, especially the AWS keys, DynamoDB table names, AWS Region (`ap-south-1`), and the `FLASK_SECRET_KEY`.*
Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

## Step 5: Configure Gunicorn as a Systemd Service
To ensure your Flask app runs 24/7 and restarts if the server reboots, we configure it as a system service.

```bash
sudo nano /etc/systemd/system/blissful.service
```

**Paste the following configuration:**
```ini
[Unit]
Description=Gunicorn instance to serve Blissful Abodes AI
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/blissful-abodes
Environment="PATH=/home/ubuntu/blissful-abodes/.venv/bin"
EnvironmentFile=/home/ubuntu/blissful-abodes/.env
ExecStart=/home/ubuntu/blissful-abodes/.venv/bin/gunicorn --workers 4 --threads 2 --bind unix:blissful.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
```

**Start and enable the service:**
```bash
sudo systemctl start blissful
sudo systemctl enable blissful
sudo systemctl status blissful  # Confirm it says 'active (running)'
```

## Step 6: Configure Nginx Server
Now we route internet traffic (Port 80) to our Gunicorn socket.

```bash
sudo nano /etc/nginx/sites-available/blissful
```

**Paste the following configuration:**
```nginx
server {
    listen 80;
    server_name 13.206.110.152; # Or your domain name (e.g., www.blissfulabodes.com)

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/blissful-abodes/blissful.sock;
    }

    location /static {
        alias /home/ubuntu/blissful-abodes/static;
        expires 30d;
    }
}
```

**Enable the site and restart Nginx:**
```bash
sudo ln -s /etc/nginx/sites-available/blissful /etc/nginx/sites-enabled
sudo nginx -t   # Checks for syntax errors
sudo systemctl restart nginx
```

## Step 7: Final Firewall Setup (UFW)
Open necessary ports mapping to the outside world:

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw enable
```

---

🎉 **Congratulations!** Your project is now securely deployed on the AWS Cloud.
You can access your live application by visiting: **http://13.206.110.152**

### Troubleshooting / Logs
If anything goes wrong, you can check your live logs using these commands:
* **Gunicorn App Logs:** `sudo journalctl -u blissful -f`
* **Nginx Error Logs:** `sudo tail -f /var/log/nginx/error.log`
