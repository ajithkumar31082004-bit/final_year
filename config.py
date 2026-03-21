import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'blissful-abodes-secret-key-2025-change-in-production')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'blissful_abodes.db')
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = False  # True in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File uploads
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@blissfulabodes.com')
    
    # Razorpay
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_placeholder')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'placeholder_secret')
    
    # Hotel Config
    HOTEL_NAME = 'Blissful Abodes Chennai'
    HOTEL_ADDRESS = '123 Marina Beach Road, Chennai, Tamil Nadu - 600001, India'
    HOTEL_PHONE = '+91 44 2345 6789'
    HOTEL_EMAIL = 'info@blissfulabodes.com'
    HOTEL_GSTIN = '33AAACB1234F1Z5'
    GST_RATE = 0.18
    CHECKIN_TIME = '14:00'
    CHECKOUT_TIME = '12:00'
    TOTAL_ROOMS = 100
    
    # AWS (optional)
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'placeholder_access_key')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'placeholder_secret_key')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'blissful-abodes-media')
    
    # Google Maps
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', 'placeholder_maps_key')
    # Gemini (Chatbot)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyCB4pOLezxCsJoYge0i6KiikIeOxcpbtD0')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

    # Offers eligibility
    OFFERS_REQUIRE_FIRST_BOOKING = True
    OFFERS_MIN_POINTS = 1000

    # Refund policy (hours before check-in)
    REFUND_FULL_HOURS = 48
    REFUND_HALF_HOURS = 24
    
    # WTF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
