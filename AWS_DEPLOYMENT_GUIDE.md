# AWS Deployment Guide for Your Flask Project

This guide covers how to deploy your Flask application to AWS. Since your project uses Flask, Gunicorn (already in your `requirements.txt`), and SQLite, there are two main ways to deploy on AWS: **Amazon EC2** (Virtual Server - Recommended for learning and control) and **AWS Elastic Beanstalk** (Platform as a Service - Easier setup).

> [!WARNING]
> **Important Database Note**: You are currently using `blissful_abodes.db` (SQLite). On AWS, if your server is terminated or you use autoscaling, your SQLite database file might be lost or overwritten. For a true production environment, it is highly recommended to migrate your database to **Amazon RDS (Relational Database Service)** using PostgreSQL or MySQL. However, for a final year project, hosting the SQLite file directly on a single EC2 instance is usually acceptable.

---

## Option 1: Deploying to Amazon EC2 (Recommended)

This approach gives you a full virtual machine (Ubuntu). We will use **Gunicorn** to run the Python code and **Nginx** as a reverse proxy to handle incoming web traffic.

### Step 1: Launch an EC2 Instance
1. Go to the [AWS Management Console](https://console.aws.amazon.com/) and log in.
2. Search for **EC2** and click **Instances** -> **Launch instances**.
3. **Name**: Enter a name for your project (e.g., `blissful-abodes-server`).
4. **AMI**: Select **Ubuntu Server** (usually Ubuntu Server 22.04 LTS or 24.04 LTS).
5. **Instance Type**: `t2.micro` (This is Free Tier eligible).
6. **Key Pair**: Click **Create a new key pair**. 
   - Name it `aws-key`.
   - Choose **RSA** and **.pem** (or **.ppk** if you use PuTTY on Windows).
   - *Download and save this file securely! You will need it to log into the server.*
7. **Network Settings**:
   - Check **Allow SSH traffic from Anywhere**
   - Check **Allow HTTP traffic from the internet**
   - Check **Allow HTTPS traffic from the internet**
8. Click **Launch instance**.

### Step 2: Connect to your EC2 Instance
1. Once the instance state is "Running", select your instance and copy its **Public IPv4 address**.
2. Open Windows PowerShell or Command Prompt. Navigate to the folder where you downloaded your `.pem` key.
3. Run the following command to securely log in:
   ```bash
   ssh -i "aws-key.pem" ubuntu@<YOUR_EC2_PUBLIC_IP>
   ```
   *(Type `yes` if prompted about the host authenticity).*

### Step 3: Set Up the Server Environment
Once connected to the Ubuntu terminal, run these commands to update the server and install Python, pip, and Nginx:
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx git -y
```

### Step 4: Upload Your Project Code
You can either use `git clone` if your project is on GitHub, or copy files via SCP.
**If using GitHub:**
```bash
git clone <YOUR_GITHUB_REPO_URL>
cd <YOUR_PROJECT_FOLDER>
```
*(If you haven't pushed to GitHub, you will need to push your local code to a GitHub repository first, or use a tool like WinSCP/FileZilla to transfer your files from Windows to the EC2 instance).*

### Step 5: Create a Virtual Environment and Install Dependencies
Inside your project folder on the EC2 server:
```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install your project dependencies
pip install wheel
pip install -r requirements.txt
```

### Step 6: Test Gunicorn
Your `requirements.txt` already includes Gunicorn. Test if it runs your app:
```bash
gunicorn --bind 0.0.0.0:8000 app:app
```
*(If you see errors here, you will need to fix them. If it works, press `Ctrl+C` to stop it).*

### Step 7: Create a Systemd Service for Gunicorn
We want Gunicorn to run automatically in the background, even if the server restarts.
```bash
sudo nano /etc/systemd/system/flaskapp.service
```
Paste the following configuration (replace `<YOUR_PROJECT_FOLDER>` with your actual folder name):
```ini
[Unit]
Description=Gunicorn instance to serve Flask App
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/<YOUR_PROJECT_FOLDER>
Environment="PATH=/home/ubuntu/<YOUR_PROJECT_FOLDER>/venv/bin"
ExecStart=/home/ubuntu/<YOUR_PROJECT_FOLDER>/venv/bin/gunicorn --workers 3 --bind unix:flaskapp.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
```
Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`). Then start and enable the service:
```bash
sudo systemctl start flaskapp
sudo systemctl enable flaskapp
```

### Step 8: Configure Nginx to Route Traffic
Now we tell Nginx to take public web traffic (Port 80) and send it to Gunicorn.
```bash
sudo nano /etc/nginx/sites-available/flaskapp
```
Paste this configuration (replace the IP):
```nginx
server {
    listen 80;
    server_name <YOUR_EC2_PUBLIC_IP>;

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/<YOUR_PROJECT_FOLDER>/flaskapp.sock;
    }
}
```
Save and exit. Now enable the Nginx configuration:
```bash
sudo ln -s /etc/nginx/sites-available/flaskapp /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

**Congratulations!** You can now visit your EC2 Public IP address in your browser, and your application should be live!

---

## Option 2: Deploying to AWS Elastic Beanstalk (Easier but less flexible)

Elastic Beanstalk handles the server configuration (Nginx, Gunicorn) for you.

1. Create a `.ebextensions` folder in your project root.
2. In the AWS Console, go to **Elastic Beanstalk** -> **Create application**.
3. Choose **Python** as the platform.
4. Compress your entire project (excluding the `venv` folder and `__pycache__`) into a `.zip` file.
5. Upload the `.zip` file in the "Application code" section.
6. AWS will automatically install dependencies from `requirements.txt` and look for the `app.py` file to start the server.

> [!NOTE]
> If using Elastic Beanstalk, you must explicitly point it to your app instance. You may need to rename `app.py` to `application.py`, or configure the WSGI path in the Elastic Beanstalk settings.
