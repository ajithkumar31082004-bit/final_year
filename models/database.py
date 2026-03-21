"""
Blissful Abodes - Database Models
SQLite-based database with all tables for the hotel management system
"""

import sqlite3
import os
from datetime import datetime
from flask import g, has_app_context

DATABASE_PATH = os.environ.get("DATABASE_PATH", "blissful_abodes.db")


class _ConnectionProxy:
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        # No-op: real close happens in close_db() teardown.
        return None

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    """Get database connection"""
    if has_app_context():
        conn = g.get("_db_conn")
        if conn is None:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g._db_conn = conn
        return _ConnectionProxy(conn)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_db(error=None):
    if not has_app_context():
        return
    conn = g.pop("_db_conn", None)
    if conn is not None:
        conn.close()


def init_db():
    """Initialize all database tables"""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'guest',
            loyalty_points INTEGER DEFAULT 0,
            tier_level TEXT DEFAULT 'Silver',
            is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            otp TEXT,
            otp_expiry TEXT,
            profile_photo TEXT,
            date_of_birth TEXT,
            anniversary_date TEXT,
            preferred_language TEXT DEFAULT 'en',
            preferences TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT,
            department TEXT,
            shift TEXT
        )
    """
    )

    # Rooms table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            floor INTEGER NOT NULL,
            base_price REAL NOT NULL,
            current_price REAL NOT NULL,
            max_guests INTEGER NOT NULL,
            amenities TEXT DEFAULT '[]',
            description TEXT,
            images TEXT DEFAULT '[]',
            status TEXT DEFAULT 'available',
            is_active INTEGER DEFAULT 1,
            view_type TEXT,
            bed_type TEXT,
            size_sqft INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Bookings table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            room_number TEXT,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            num_guests INTEGER DEFAULT 1,
            base_amount REAL NOT NULL,
            gst_amount REAL NOT NULL,
            discount_amount REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            coupon_code TEXT,
            loyalty_points_used INTEGER DEFAULT 0,
            loyalty_points_earned INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'pending',
            payment_method TEXT,
            payment_id TEXT,
            razorpay_order_id TEXT,
            special_requests TEXT,
            fraud_score REAL DEFAULT 0,
            is_flagged INTEGER DEFAULT 0,
            fraud_flags TEXT DEFAULT '[]',
            cancellation_probability REAL DEFAULT 0,
            qr_code_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            checked_in_at TEXT,
            checked_out_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """
    )

    # Lightweight schema migration for existing DBs
    try:
        cols = [r["name"] for r in cursor.execute("PRAGMA table_info(bookings)").fetchall()]
        if "fraud_flags" not in cols:
            cursor.execute("ALTER TABLE bookings ADD COLUMN fraud_flags TEXT DEFAULT '[]'")
        if "special_requests" not in cols:
            cursor.execute("ALTER TABLE bookings ADD COLUMN special_requests TEXT")
    except Exception:
        pass

    # Reviews table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            review_id TEXT PRIMARY KEY,
            booking_id TEXT,
            user_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            overall_rating REAL NOT NULL,
            cleanliness_rating REAL DEFAULT 0,
            staff_rating REAL DEFAULT 0,
            location_rating REAL DEFAULT 0,
            value_rating REAL DEFAULT 0,
            amenities_rating REAL DEFAULT 0,
            comment TEXT,
            photos TEXT DEFAULT '[]',
            verified_stay INTEGER DEFAULT 0,
            helpful_count INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            featured INTEGER DEFAULT 0,
            sentiment TEXT DEFAULT 'neutral',
            sentiment_score REAL DEFAULT 0,
            staff_response TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """
    )

    # Loyalty transactions
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS loyalty_transactions (
            transaction_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            points INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            reference_id TEXT,
            description TEXT,
            balance_after INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """
    )

    # Notifications
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            read_status INTEGER DEFAULT 0,
            action_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """
    )

    # Coupons
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS coupons (
            coupon_id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT NOT NULL,
            discount_value REAL NOT NULL,
            min_booking_amount REAL DEFAULT 0,
            max_uses INTEGER DEFAULT 999999,
            used_count INTEGER DEFAULT 0,
            valid_from TEXT,
            valid_until TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Audit logs
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            result TEXT DEFAULT 'success',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Inventory
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            item_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            stock_count INTEGER DEFAULT 0,
            reorder_level INTEGER DEFAULT 10,
            unit TEXT DEFAULT 'units',
            unit_cost REAL DEFAULT 0,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Staff shifts
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_shifts (
            shift_id TEXT PRIMARY KEY,
            staff_id TEXT NOT NULL,
            date TEXT NOT NULL,
            shift_type TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES users(user_id)
        )
    """
    )

    # Housekeeping tasks
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS housekeeping_tasks (
            task_id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            room_number TEXT,
            assigned_to TEXT,
            task_type TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """
    )

    # Maintenance issues
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_issues (
            issue_id TEXT PRIMARY KEY,
            room_id TEXT,
            room_number TEXT,
            reported_by TEXT,
            issue_type TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """
    )

    # Wishlists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            room_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, room_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        )
    """
    )

    # Messages (internal staff)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            recipient_id TEXT,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Chatbot messages
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chatbot_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Service requests (general + room service)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS service_requests (
            request_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            room_id TEXT,
            room_number TEXT,
            request_type TEXT NOT NULL,
            details TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Indexes for hot queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_payment ON bookings(payment_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_created ON bookings(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookings_checkin ON bookings(check_in)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rooms_type ON rooms(room_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, read_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_room ON reviews(room_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code)")

    conn.commit()
    conn.close()
    print("[DB] All tables created successfully")
