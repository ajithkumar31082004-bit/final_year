"""
Blissful Abodes - Email Service
Sends HTML emails via SMTP for all hotel notification types
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

HOTEL_NAME = "Blissful Abodes Chennai"
HOTEL_EMAIL = os.environ.get("MAIL_USERNAME", "noreply@blissfulabodes.com")
HOTEL_PHONE = "+91 44 2345 6789"
DEMO_MODE = os.environ.get("DEMO_MODE", "0").strip().lower() in {"1", "true", "yes"}
MAIL_SUPPRESS = os.environ.get("MAIL_SUPPRESS", "0").strip().lower() in {
    "1",
    "true",
    "yes",
}


def get_email_header():
    return f"""
    <div style="background: linear-gradient(135deg, #FF6B35, #E55A2B); padding: 30px; text-align: center;">
        <h1 style="color: white; font-family: 'Georgia', serif; margin: 0; font-size: 28px;">🏨 {HOTEL_NAME}</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 5px 0 0;">123 Marina Beach Road, Chennai - 600001</p>
    </div>
    """


def get_email_footer():
    return f"""
    <div style="background: #2D2D2D; padding: 20px; text-align: center;">
        <p style="color: #aaa; font-size: 13px; margin: 0;">
            {HOTEL_NAME} | {HOTEL_PHONE} | 
            <a href="mailto:{HOTEL_EMAIL}" style="color: #FF6B35;">{HOTEL_EMAIL}</a>
        </p>
        <p style="color: #666; font-size: 11px; margin: 10px 0 0;">
            © 2025-2026 {HOTEL_NAME}. All rights reserved.
        </p>
    </div>
    """


def send_email(to_email, subject, html_body, attachment_path=None):
    """Core email sending function"""
    try:
        if DEMO_MODE or MAIL_SUPPRESS:
            print(f"[EMAIL] (demo) Would send to {to_email}: {subject}")
            return True

        smtp_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("MAIL_PORT", 587))
        username = os.environ.get("MAIL_USERNAME", "")
        password = os.environ.get("MAIL_PASSWORD", "")

        if not username or not password:
            print(f"[EMAIL] Would send to {to_email}: {subject}")
            return True  # Return success in dev mode

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{HOTEL_NAME} <{username}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 0; font-family: 'Arial', sans-serif; background: #f5f5f5;">
            <div style="max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                {get_email_header()}
                <div style="padding: 30px;">
                    {html_body}
                </div>
                {get_email_footer()}
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(full_html, "html"))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(attachment_path)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(username, to_email, msg.as_string())

        print(f"[EMAIL] ✅ Sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Error: {e}")
        return False


def send_welcome_email(user_email, user_name):
    html = f"""
    <h2 style="color: #FF6B35;">🙏 Namaste, {user_name}!</h2>
    <p>Welcome to <strong>{HOTEL_NAME}</strong>! We are thrilled to have you as part of our family.</p>
    <p>Your account has been created successfully. You can now:</p>
    <ul>
        <li>🛏️ Browse and book from our 100 premium rooms</li>
        <li>🎁 Earn Blissful Rewards points on every stay</li>
        <li>🌟 Access exclusive member-only offers</li>
        <li>📱 Manage your bookings anytime, anywhere</li>
    </ul>
    <div style="text-align: center; margin: 30px 0;">
        <a href="http://localhost:5000/rooms" style="background: linear-gradient(135deg, #FF6B35, #E55A2B); color: white; padding: 14px 28px; text-decoration: none; border-radius: 25px; font-weight: bold;">
            ✨ Explore Rooms
        </a>
    </div>
    <p style="color: #888; font-size: 13px;">Use code <strong>WELCOME10</strong> for 10% off your first booking!</p>
    """
    return send_email(user_email, f"🎉 Welcome to {HOTEL_NAME}!", html)


def send_booking_confirmation(user_email, user_name, booking_data, invoice_path=None):
    html = f"""
    <h2 style="color: #28A745;">✅ Booking Confirmed!</h2>
    <p>Dear {user_name}, your booking has been confirmed. Here are your details:</p>
    <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px; color: #666;">Booking ID</td>
                <td style="padding: 8px; font-weight: bold;">#{booking_data.get('booking_id', 'N/A')}</td></tr>
            <tr><td style="padding: 8px; color: #666;">Room</td>
                <td style="padding: 8px; font-weight: bold;">{booking_data.get('room_number', 'N/A')} - {booking_data.get('room_type', 'N/A')}</td></tr>
            <tr><td style="padding: 8px; color: #666;">Check-in</td>
                <td style="padding: 8px; font-weight: bold;">{booking_data.get('check_in', 'N/A')} at 2:00 PM</td></tr>
            <tr><td style="padding: 8px; color: #666;">Check-out</td>
                <td style="padding: 8px; font-weight: bold;">{booking_data.get('check_out', 'N/A')} at 12:00 PM</td></tr>
            <tr><td style="padding: 8px; color: #666;">Guests</td>
                <td style="padding: 8px; font-weight: bold;">{booking_data.get('num_guests', 1)}</td></tr>
            <tr style="background: #FF6B35; color: white;">
                <td style="padding: 10px; border-radius: 4px;">Total Amount</td>
                <td style="padding: 10px; font-weight: bold; font-size: 18px;">₹{booking_data.get('total_amount', 0):,.0f}</td></tr>
        </table>
    </div>
    <p>📋 Your GST invoice is attached. Check-in at 2:00 PM with a valid government ID.</p>
    <p style="color: #888; font-size: 13px;">Need help? Call us at {HOTEL_PHONE}</p>
    """
    return send_email(
        user_email,
        f"🏨 Booking Confirmed - #{booking_data.get('booking_id', '')}",
        html,
        invoice_path,
    )


def send_checkin_reminder(user_email, user_name, booking_data):
    html = f"""
    <h2 style="color: #FF6B35;">🏨 Your Stay Starts Tomorrow!</h2>
    <p>Dear {user_name}, we can't wait to welcome you!</p>
    <div style="background: #fff3e0; border-left: 4px solid #FF6B35; padding: 15px; margin: 15px 0;">
        <strong>Room {booking_data.get('room_number')} • Check-in: 2:00 PM</strong>
    </div>
    <p>📍 <strong>Address:</strong> 123 Marina Beach Road, Chennai - 600001</p>
    <p>Please carry a valid government ID for check-in.</p>
    """
    return send_email(
        user_email,
        f"🌟 Check-in Tomorrow - Room {booking_data.get('room_number')}",
        html,
    )


def send_otp_email(user_email, user_name, otp):
    html = f"""
    <h2 style="color: #FF6B35;">🔐 Your OTP</h2>
    <p>Dear {user_name}, your One-Time Password is:</p>
    <div style="text-align: center; margin: 30px 0;">
        <div style="background: #FF6B35; color: white; font-size: 36px; font-weight: bold; 
             padding: 20px 40px; border-radius: 10px; letter-spacing: 8px; display: inline-block;">
            {otp}
        </div>
    </div>
    <p style="color: #dc3545;">⏰ This OTP is valid for <strong>10 minutes only</strong>.</p>
    <p style="color: #888; font-size: 12px;">If you did not request this OTP, please ignore this email.</p>
    """
    return send_email(user_email, f"🔐 OTP: {otp} - {HOTEL_NAME}", html)


def send_cancellation_email(user_email, user_name, booking_data, refund_amount=None):
    html = f"""
    <h2 style="color: #dc3545;">📋 Booking Cancelled</h2>
    <p>Dear {user_name}, your booking has been cancelled as requested.</p>
    <p><strong>Booking ID:</strong> #{booking_data.get('booking_id')}</p>
    {'<p><strong>Refund Amount:</strong> ₹' + str(refund_amount) + ' will be credited within 5-7 business days.</p>' if refund_amount else ''}
    <p>We hope to see you again soon! <a href="http://localhost:5000/rooms" style="color: #FF6B35;">Browse rooms</a></p>
    """
    return send_email(
        user_email, f"Booking Cancelled - #{booking_data.get('booking_id')}", html
    )


def send_review_request(user_email, user_name, booking_data):
    html = f"""
    <h2 style="color: #D4AF37;">⭐ How Was Your Stay?</h2>
    <p>Dear {user_name}, thank you for staying with us!</p>
    <p>Your feedback helps us improve and helps other guests make decisions.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="http://localhost:5000/guest/review/{booking_data.get('booking_id')}" 
           style="background: #D4AF37; color: white; padding: 14px 28px; 
                  text-decoration: none; border-radius: 25px; font-weight: bold;">
            ✍️ Write a Review (Earn 50 Points)
        </a>
    </div>
    """
    return send_email(user_email, f"⭐ Share Your Experience - {HOTEL_NAME}", html)
