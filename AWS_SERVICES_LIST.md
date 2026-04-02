# AWS Services Used – Blissful Abodes Hotel Management System

This document describes all AWS Cloud services integrated into the **Blissful Abodes** final year project.

---

## 1. 🖥️ Amazon EC2 (Elastic Compute Cloud) — Application Hosting

| Detail | Value |
|--------|-------|
| **Instance Type** | `t2.micro` (Ubuntu 22.04 LTS) |
| **Region** | `ap-south-1` (Mumbai) |
| **Public IP** | `44.208.253.176` |
| **Service File** | `services/ec2_service.py` |

**How it is used:**
- The EC2 instance acts as the main **application server** for the Blissful Abodes hotel management system.
- The Flask application (`app.py`) runs on this instance, served by **Gunicorn** (a Python WSGI HTTP server).
- **Nginx** is configured as a reverse proxy on the EC2 instance, routing all incoming HTTP requests (port 80) to the Gunicorn socket.
- The systemd service (`blissfulabodes.service`) ensures the application automatically restarts on failure.
- All 5 AI/ML models (Fraud Detection, Dynamic Pricing, Sentiment Analysis, Room Recommender, Cancellation Predictor) run on this instance.

**`ec2_service.py` capabilities:**
- `get_instance_info()` — returns instance type, state, public/private IP, AZ, AMI
- `get_instance_status()` — checks system and instance reachability status
- `list_security_groups()` — lists open ports attached to the instance
- `get_infrastructure_summary()` — consolidated dashboard panel

**AWS Security Groups configured:**
- Port 22 (SSH) — for server management
- Port 80 (HTTP) — for public web access
- Port 443 (HTTPS) — for SSL traffic

---

## 2. 🗄️ Amazon S3 (Simple Storage Service) — File Storage

| Detail | Value |
|--------|-------|
| **Bucket** | `blissful-abodes-media` |
| **Purpose** | Persistent storage for user uploads and generated reports |
| **File Types** | Room images, GST invoices (PDF), Booking QR codes (PNG) |
| **Service File** | `services/s3_service.py` |

**How it is used:**
- Guest-uploaded files (room photos) are stored in S3 to ensure they persist if the EC2 instance is stopped or replaced.
- AI-generated GST Invoice PDFs and Booking QR codes are uploaded to S3 for permanent storage.
- S3 provides **high durability (99.999999999%)** and decouples file storage from the compute server.

---

## 3. 📣 Amazon SNS (Simple Notification Service) — Push Notifications

| Detail | Value |
|--------|-------|
| **Admin Topic** | `blissful-admin-alerts` |
| **Guest Topic** | `blissful-guest-notifications` |
| **Purpose** | Real-time booking confirmations, fraud alerts, cancellation notices |
| **Service File** | `services/sns_service.py` |

**How it is used:**
- `send_booking_confirmation()` — publishes a booking confirmation to the guest SNS topic after a successful payment, delivering it via email/SMS.
- `send_fraud_alert()` — immediately notifies the admin team when the AI Fraud Detection system flags a high-risk booking (fraud score ≥ 0.35).
- `send_cancellation_alert()` — sends a cancellation and refund notice to the guest.

**Why SNS over direct email:**
> SNS decouples notification delivery from the application. If the email service is down, SNS retains and retries the message automatically, ensuring no booking confirmation is lost.

---

## 4. 🗃️ Amazon DynamoDB — NoSQL Session & Chat Storage

| Detail | Value |
|--------|-------|
| **Tables** | `blissful-sessions`, `blissful-chatbot-history`, `blissful-audit-logs` |
| **Purpose** | Fast NoSQL storage for sessions, AI chatbot history, and audit logs |
| **Service File** | `services/dynamodb_service.py` |

**How it is used:**
- **Sessions** (`blissful-sessions`): Persists Flask/agent session data across multiple EC2 instances if the app is horizontally scaled. Each session has a 24-hour TTL for automatic cleanup.
- **Chatbot History** (`blissful-chatbot-history`): Stores all AI concierge (Aria) conversation messages per user with a 30-day TTL. This allows users to resume conversations and gives the AI context of past interactions.
- **Audit Logs** (`blissful-audit-logs`): Records tamper-proof audit trail entries (`booking_created`, `fraud_flagged`, `login`, `price_updated`) for compliance and debugging.

**Why DynamoDB over SQLite for this data:**
> DynamoDB provides single-digit millisecond latency at any scale. Chat history and session data are write-heavy and have no relational structure, making DynamoDB the ideal fit over the relational SQLite database.

---

## 5. 🔐 AWS IAM (Identity and Access Management) — Security & Permissions

| Detail | Value |
|--------|-------|
| **Instance Role** | `blissful-abodes-ec2-role` |
| **Purpose** | Manages permissions for all AWS service access |
| **Service File** | `services/iam_service.py` |

**How it is used:**
- The EC2 instance is attached to the `blissful-abodes-ec2-role` IAM role, which grants it permissions to access S3, DynamoDB, SNS, and CloudWatch **without hardcoding credentials**.
- `get_caller_identity()` — verifies which IAM user/role the application is running as using AWS STS.
- `list_attached_policies()` — checks that the EC2 role has all required service permissions (S3, DynamoDB, SNS, CloudWatch).
- `assume_role()` — generates temporary STS credentials for cross-account or cross-service access (e.g., accessing a backup S3 bucket in another account).
- `check_service_permissions()` — admin health check that validates all required IAM permissions are in place.

**IAM Policies attached to `blissful-abodes-ec2-role`:**

| Policy | Services Granted |
|--------|-----------------|
| `AmazonS3FullAccess` | Upload/read room images, invoices, QR codes |
| `AmazonDynamoDBFullAccess` | Read/write sessions, chatbot history, audit logs |
| `AmazonSNSFullAccess` | Publish booking and fraud alert notifications |
| `CloudWatchAgentServerPolicy` | Push metrics and logs to CloudWatch |

---

## 6. 🗃️ Amazon RDS (Relational Database Service) — Database Management

| Detail | Value |
|--------|-------|
| **Database Engine** | SQLite (local dev) → PostgreSQL `db.t3.micro` (production) |
| **Free Tier** | 750 hours/month |

**How it is used:**
- The core application database stores all hotel data: users, bookings, rooms, reviews, notifications, audit logs, and payment records.
- In production, **Amazon RDS** provides a managed database separate from the EC2 application server, ensuring data survives if the server is re-created.
- All 5 AI models read and write to this database (fraud scores, cancellation probabilities, sentiment scores, pricing logs).

---

## 7. 📊 Amazon CloudWatch — Monitoring & Observability

| Detail | Value |
|--------|-------|
| **Purpose** | Real-time performance monitoring and alerting |
| **Key Metrics** | CPU utilization, Memory, Disk I/O, Network In/Out |

**How it is used:**
- **CloudWatch Metrics** monitor the EC2 instance's CPU, RAM and network usage in real time during ML model inference.
- **CloudWatch Alarms** alert when CPU exceeds 80%, preventing crashes during peak booking periods.
- **CloudWatch Logs** capture Nginx access logs and Gunicorn error logs from the EC2 instance.

---

## Architecture Overview

```
Internet (HTTPS)
       │
       ▼
 [AWS Security Group — Port 443/80/22]
       │
       ▼
 Amazon EC2 (t2.micro, Ubuntu 22.04)
 ├── Nginx (Reverse Proxy → Port 80/443)
 ├── Gunicorn (Flask App Server)
 └── Flask App (app.py)
     ├── 5 AI/ML Models (Fraud, Pricing, Recommender, Sentiment, Cancellation)
     ├── Google Gemini Chatbot (Aria AI Concierge)
     ├── Razorpay Payment Integration
     │
     ├── Amazon S3  ──────────── (Room images, Invoices PDF, QR Codes)
     ├── Amazon SNS ──────────── (Booking confirmations, Fraud alerts)
     ├── Amazon DynamoDB ──────── (Sessions, Chatbot history, Audit logs)
     ├── Amazon RDS ──────────── (Users, Bookings, Rooms — relational data)
     ├── AWS IAM ─────────────── (EC2 role permissions for all services above)
     └── Amazon CloudWatch ───── (CPU/Memory monitoring, Log aggregation)
```

---

## Service Files Summary

| AWS Service | Service File | Key Functions |
|-------------|-------------|---------------|
| EC2 | `services/ec2_service.py` | `get_instance_info()`, `get_instance_status()`, `get_infrastructure_summary()` |
| S3 | `services/s3_service.py` | `upload_file()`, `upload_invoice()`, `upload_qr()`, `get_presigned_url()` |
| SNS | `services/sns_service.py` | `send_booking_confirmation()`, `send_fraud_alert()`, `send_cancellation_alert()` |
| DynamoDB | `services/dynamodb_service.py` | `save_session()`, `save_chat_message()`, `get_chat_history()`, `log_audit_event()` |
| IAM / STS | `services/iam_service.py` | `get_caller_identity()`, `list_attached_policies()`, `assume_role()`, `check_service_permissions()` |

---

*This deployment follows the AWS Well-Architected Framework principles: Reliability, Security, Performance Efficiency, and Cost Optimization.*
