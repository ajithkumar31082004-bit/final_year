"""
Blissful Abodes - Database Models
Supports both SQLite (local) and MySQL (production)
"""

import sqlite3
import os
from datetime import datetime
from flask import g, has_app_context
from urllib.parse import urlparse

# Import pymysql only when needed (for MySQL connections)
try:
    import pymysql
except ImportError:
    pymysql = None

# Determine database type
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_PUBLIC_URL")
USE_MYSQL = bool(DATABASE_URL) or bool(os.environ.get("MYSQL_HOST"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "blissful_abodes.db")


class _RowProxy:
    def __init__(self, data_dict):
        self._dict = data_dict
        self._tuple = tuple(data_dict.values()) if data_dict else ()

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._tuple[key]
        return self._dict[key]

    def keys(self):
        return self._dict.keys()

    def values(self):
        return self._tuple

    def __repr__(self):
        return repr(self._dict)

    def __len__(self):
        return len(self._tuple)


class _CursorProxy:
    def __init__(self, cursor):
        self._cursor = cursor
        
    def execute(self, sql, *args, **kwargs):
        if isinstance(sql, str):
            sql = sql.replace('?', '%s')
            # Translate SQLite specific INSERT OR IGNORE/REPLACE to MySQL
            sql = sql.replace('INSERT OR IGNORE', 'INSERT IGNORE')
            sql = sql.replace('insert or ignore', 'insert ignore')
            sql = sql.replace('INSERT OR REPLACE', 'REPLACE')
            sql = sql.replace('insert or replace', 'replace')
        return self._cursor.execute(sql, *args, **kwargs)
        
    def fetchone(self):
        row = self._cursor.fetchone()
        if row is not None:
            return _RowProxy(row)
        return None

    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows is not None:
            return [_RowProxy(r) for r in rows]
        return []

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
        if rows is not None:
            return [_RowProxy(r) for r in rows]
        return []

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __iter__(self):
        for row in self._cursor:
            yield _RowProxy(row)


class _ConnectionProxy:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        cursor = self._conn.cursor(*args, **kwargs)
        if USE_MYSQL:
            return _CursorProxy(cursor)
        return cursor

    def execute(self, sql, *args, **kwargs):
        if USE_MYSQL:
            if isinstance(sql, str):
                sql = sql.replace('?', '%s')
                # Translate SQLite specific INSERT OR IGNORE/REPLACE to MySQL
                sql = sql.replace('INSERT OR IGNORE', 'INSERT IGNORE')
                sql = sql.replace('insert or ignore', 'insert ignore')
                sql = sql.replace('INSERT OR REPLACE', 'REPLACE')
                sql = sql.replace('insert or replace', 'replace')
            cursor = self._conn.cursor()
            cursor.execute(sql, *args, **kwargs)
            return _CursorProxy(cursor)
        else:
            return self._conn.execute(sql, *args, **kwargs)

    def close(self):
        if not has_app_context():
            self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    """Get database connection (MySQL or SQLite)"""
    if has_app_context():
        conn = g.get("_db_conn")
        if conn is None:
            if USE_MYSQL:
                conn = _get_mysql_connection()
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
            g._db_conn = conn
        return _ConnectionProxy(conn)

    if USE_MYSQL:
        return _ConnectionProxy(_get_mysql_connection())
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return _ConnectionProxy(conn)




def _normalize_sql_for_mysql(sql: str) -> str:
    """Convert SQLite-style schema DDL to MySQL-compatible DDL when needed."""
    if not USE_MYSQL:
        return sql
    
    import re
    
    # 1. Replace autoincrement
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'INT PRIMARY KEY AUTO_INCREMENT')
    
    # 2. Convert standard SQLite TEXT columns to VARCHAR to support indexing and foreign keys in MySQL.
    large_text_cols = {
        'description', 'comment', 'special_requests', 'details', 
        'notes', 'content', 'preferences', 'amenities', 'images', 
        'photos', 'fraud_flags', 'staff_response'
    }
    
    def replace_col(match):
        col_name = match.group(1)
        rest = match.group(2)
        
        # If the column name is in the whitelist, keep it as TEXT
        if col_name.lower() in large_text_cols:
            return f"{col_name} TEXT{rest}"
            
        # Determine the varchar length (128 for keys/IDs, 255 for others)
        length = 128 if ('PRIMARY KEY' in rest.upper() or 
                         'user_id' in col_name.lower() or 
                         'room_id' in col_name.lower() or 
                         'booking_id' in col_name.lower() or
                         'room_number' in col_name.lower() or
                         'code' in col_name.lower()) else 255
        
        # Map DEFAULT CURRENT_TIMESTAMP to DATETIME
        if 'DEFAULT CURRENT_TIMESTAMP' in rest.upper():
            return f"{col_name} DATETIME{rest}"
            
        return f"{col_name} VARCHAR({length}){rest}"

    # Match column definitions: "col_name TEXT ..."
    sql = re.sub(
        r'\b(?!FOREIGN\b|PRIMARY\b|UNIQUE\b|KEY\b|CHECK\b)([a-zA-Z_][a-zA-Z0-9_]*)\s+TEXT\b(.*?)(?=,|\r?\n|\))',
        replace_col,
        sql,
        flags=re.IGNORECASE
    )
    
    # 3. Fallback standard replacements
    replacements = [
        ('TEXT UNIQUE NOT NULL', 'VARCHAR(255) UNIQUE NOT NULL'),
        ('TEXT PRIMARY KEY', 'VARCHAR(128) PRIMARY KEY'),
        ('TEXT NOT NULL DEFAULT', 'VARCHAR(255) NOT NULL DEFAULT'),
        ('TEXT DEFAULT CURRENT_TIMESTAMP', 'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('TEXT DEFAULT "', 'VARCHAR(255) DEFAULT "'),
        ("TEXT DEFAULT '", "VARCHAR(255) DEFAULT '")
    ]
    for old, new in replacements:
        sql = sql.replace(old, new)
        
    return sql


def _get_mysql_connection():
    """Create MySQL connection from DATABASE_URL or individual env vars"""
    try:
        if "://" in DATABASE_URL:
            # Parse MySQL connection URL
            parsed = urlparse(DATABASE_URL)
            host = parsed.hostname
            user = parsed.username
            password = parsed.password
            database = parsed.path.lstrip("/")
            port = parsed.port or 3306
        else:
            # Use individual environment variables
            host = os.environ.get("MYSQL_HOST")
            user = os.environ.get("MYSQL_USER")
            password = os.environ.get("MYSQL_PASSWORD")
            database = os.environ.get("MYSQL_DB")
            port = int(os.environ.get("MYSQL_PORT", 3306))
        
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print(f"[DB] MySQL connection failed: {e}")
        raise


def close_db(error=None):
    if not has_app_context():
        return
    conn = g.pop("_db_conn", None)
    if conn is not None:
        conn.close()


def _create_index(cursor, index_name: str, table_name: str, columns: str):
    """Helper to create index safely on both SQLite and MySQL."""
    if USE_MYSQL:
        try:
            cursor.execute(f"CREATE INDEX {index_name} ON {table_name}({columns})")
        except Exception as e:
            # Ignore Duplicate Key name error (1061) in MySQL
            if "1061" not in str(e):
                print(f"[DB] Index {index_name} info/error: {e}")
    else:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})")


def init_db():
    """Initialize all database tables"""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Rooms table
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Bookings table
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

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
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Loyalty transactions
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Notifications
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Coupons
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Audit logs
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Inventory
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Staff shifts
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Housekeeping tasks
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Maintenance issues
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Wishlists
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Messages (internal staff)
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Chatbot messages
    cursor.execute(_normalize_sql_for_mysql(
        """
        CREATE TABLE IF NOT EXISTS chatbot_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    ))

    # Service requests (general + room service)
    cursor.execute(_normalize_sql_for_mysql(
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
    ))

    # Indexes for hot queries
    _create_index(cursor, "idx_users_email", "users", "email")
    _create_index(cursor, "idx_users_role_active", "users", "role, is_active")
    _create_index(cursor, "idx_bookings_user", "bookings", "user_id")
    _create_index(cursor, "idx_bookings_status", "bookings", "status")
    _create_index(cursor, "idx_bookings_payment", "bookings", "payment_status")
    _create_index(cursor, "idx_bookings_created", "bookings", "created_at")
    _create_index(cursor, "idx_bookings_checkin", "bookings", "check_in")
    _create_index(cursor, "idx_rooms_status", "rooms", "status")
    _create_index(cursor, "idx_rooms_type", "rooms", "room_type")
    _create_index(cursor, "idx_notifications_user_read", "notifications", "user_id, read_status")
    _create_index(cursor, "idx_reviews_room", "reviews", "room_id")
    _create_index(cursor, "idx_reviews_user", "reviews", "user_id")
    _create_index(cursor, "idx_coupons_code", "coupons", "code")

    conn.commit()
    conn.close()
    print("[DB] All tables created successfully")
