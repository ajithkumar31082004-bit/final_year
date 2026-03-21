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

## AI Models

- Fraud Detection: hybrid rules + ML (RandomForest) trained on booking history; combines rule score with model probability.
  If a booking is classified as high risk, it is automatically blocked and flagged for administrative review.
  Medium-risk bookings are sent for manual verification, while low-risk bookings proceed normally.

```text
Booking Request
    ↓
Fraud Detection Engine
    ↓
 SAFE      REVIEW      FRAUD
   ↓          ↓           ↓
Confirm   Verify     Block + Alert
```
- Demand Forecasting: 30-day forecast using linear regression on calendar features with real booking history when available.
- Dynamic Pricing: rule-based optimization using occupancy, season, timing, and room type.
- Cancellation Prediction: logistic regression-style scoring using user history and booking signals.
- Recommendation System: hybrid collaborative + content-based + contextual scoring with ML ranking (logistic regression).

## Viva Quick Answer

My project implements five AI systems: Fraud Detection, Demand Forecasting, Dynamic Pricing, Cancellation Prediction, and a Hybrid Recommendation System to improve security, revenue optimization, and personalization.
One-line: 5 AI = Security + Prediction + Pricing + Risk + Personalization.

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
