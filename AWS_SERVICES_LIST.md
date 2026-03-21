# AWS Services Used – Blissful Abodes Hotel Management System

This document describes the four AWS Cloud services integrated into the **Blissful Abodes** final year project.

---

## 1. 🖥️ Amazon EC2 (Elastic Compute Cloud) — Application Hosting

| Detail | Value |
|--------|-------|
| **Instance Type** | `t2.micro` (Ubuntu 22.04 LTS) |
| **Region** | us-east-1 (N. Virginia) |
| **Public IP** | `44.208.253.176` |

**How it is used:**
- The EC2 instance acts as the main **application server** for the Blissful Abodes hotel management system.
- The Flask application (`app.py`) runs on this instance, served by **Gunicorn** (a Python WSGI HTTP server).
- **Nginx** is configured as a reverse proxy on the EC2 instance, routing all incoming HTTP requests (port 80) to the Gunicorn socket.
- The systemd service (`blissfulabodes.service`) ensures the application automatically restarts on failure.
- All AI/ML models (Fraud Detection, Dynamic Pricing, Sentiment Analysis, Room Recommender, Cancellation Predictor) also run on this instance.

**AWS Security Groups configured:**
- Port 22 (SSH) — for server management
- Port 80 (HTTP) — for public web access

---

## 2. 🗄️ Amazon S3 (Simple Storage Service) — File Storage

| Detail | Value |
|--------|-------|
| **Purpose** | Persistent storage for user uploads and generated reports |
| **File Types** | Room images, GST invoices (PDF), Booking QR codes (PNG) |

**How it is used:**
- Guest-uploaded files (such as room photos) are stored in an S3 bucket to ensure they are not lost if the EC2 instance is stopped or replaced.
- AI-generated GST Invoice PDFs (`reports/`) and Booking QR code images (`static/qr/`) are uploaded to S3 for permanent storage.
- S3 provides **high durability (99.999999999%)** and decouples file storage from the compute server, which is the industry-standard practice.

**Why this matters:**
> If only EC2 is used without S3, all uploaded files are deleted when the EC2 instance is terminated. S3 ensures data persists independently.

---

## 3. 🗃️ Amazon RDS (Relational Database Service) — Database Management

| Detail | Value |
|--------|-------|
| **Database Engine** | SQLite (local, mirrored to RDS for production) |
| **Recommended RDS Engine** | PostgreSQL (`db.t3.micro`) |
| **Free Tier** | 750 hours/month free |

**How it is used:**
- The core application database (`blissful_abodes.db`) stores all hotel data: users, bookings, rooms, reviews, notifications, audit logs, and payment records.
- In the production deployment, **Amazon RDS** provides a managed database that is separate from the EC2 application server, ensuring data survives even if the server is re-created.
- RDS provides **automated daily backups**, **multi-AZ replication** options, and **automated patching**, which are critical for a hotel management system where booking data must never be lost.
- All 6 AI models read and write to this database: fraud scores, cancellation probabilities, review sentiments, and dynamic pricing logs are all stored here.

**Database Tables used:**
`users` · `bookings` · `rooms` · `reviews` · `notifications` · `audit_logs` · `housekeeping_tasks` · `maintenance_issues` · `service_requests` · `chatbot_messages` · `coupons`

---

## 4. 📊 Amazon CloudWatch (Monitoring & Observability)

| Detail | Value |
|--------|-------|
| **Purpose** | Real-time performance monitoring and alerting |
| **Key Metrics Tracked** | CPU utilization, Memory, Disk I/O, Network In/Out |

**How it is used:**
- **CloudWatch Metrics** monitor the EC2 instance's CPU, RAM and network usage in real time. This is critical when running 6 AI/ML models simultaneously, as they are computationally intensive (especially during peak booking times).
- **CloudWatch Alarms** are configured to send alerts when CPU usage exceeds 80%, preventing application crashes during high traffic.
- **CloudWatch Logs** capture all application logs (Nginx access logs, Gunicorn error logs) from the EC2 instance, making it easy to diagnose errors without needing to SSH into the server.
- The "ML Analytics" dashboard section of the Blissful Abodes admin panel was built with the same observability principles as CloudWatch — showing real-time model performance, fraud detection rates, and demand forecasts.

---

## Architecture Overview

```
Internet (HTTP)
       │
       ▼
  [AWS Security Group]
       │
       ▼
  Amazon EC2 (t2.micro)
  ├── Nginx (Reverse Proxy → Port 80)
  ├── Gunicorn (Flask App Server)
  ├── Flask App (app.py)
  │   ├── 6 AI/ML Models
  │   ├── Razorpay Payment Integration
  │   └── Google Gemini Chatbot API
  │
  ├── Amazon RDS ──────────── (Database: Users, Bookings, Rooms)
  ├── Amazon S3  ──────────── (Storage: Uploads, PDFs, QR Codes)
  └── Amazon CloudWatch ───── (Monitoring: CPU, Logs, Alerts)
```

---

*This deployment follows the AWS Well-Architected Framework principles: Reliability, Security, Performance Efficiency, and Cost Optimization.*
