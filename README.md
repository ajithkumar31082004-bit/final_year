# Blissful Abodes Hotel Management System

Full-stack hotel management and booking platform built with Flask. Includes multi-role dashboards, booking flows, payments (Razorpay), AI-assisted features, and reporting.

## Features

- Public website with room listings, offers, and contact pages
- Guest, staff, manager, admin, and superadmin dashboards
- Booking, cancellation, invoicing, and QR check-in
- Razorpay payment integration (demo mode supported)
- AI/ML modules for recommendations, pricing, fraud detection, and demand forecasting
- Notifications, reviews, loyalty points, and audits

## Tech Stack

- Python, Flask, Jinja2
- SQLite
- Razorpay SDK
- Flask-WTF (CSRF protection)
- scikit-learn, NumPy, pandas
- TextBlob, VADER

## Project Structure

- `app.py` - Flask app entry point and routes
- `config.py` - configuration
- `routes/` - blueprints for auth, guest, staff, admin, etc.
- `services/` - payment, email, PDF, security, AI chat
- `models/` - DB access and schema
- `ml_models/` - AI/ML components
- `templates/` and `static/` - UI

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python app.py
```

The app will seed the database on first run.

## Default Demo Credentials

From `app.py`:

- Super Admin: `vikram@blissfulabodes.com` / `Admin@123`
- Admin: `anil@blissfulabodes.com` / `Admin@123`
- Manager: `suresh@blissfulabodes.com` / `Staff@123`
- Staff: `priya@blissfulabodes.com` / `Staff@123`
- Guest: `rajesh@example.com` / `Guest@123`

## Configuration

Environment variables (optional):

- `FLASK_SECRET_KEY`
- `DATABASE_PATH`
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `GOOGLE_MAPS_API_KEY`

If Razorpay keys are not set, the app runs in demo mode for payments.

## Security Notes

- CSRF protection is enabled globally.
- Superadmin impersonation supports safe return to admin mode.

## Tests

There is a minimal `test_app.py`. Extend as needed.

