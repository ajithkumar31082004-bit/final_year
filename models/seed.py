"""
Seed data - Creates initial hotel data in the database
100 rooms, default users (all 5 roles), sample bookings, reviews, coupons
"""

import sqlite3
import json
import random
import uuid
from datetime import datetime, timedelta
from models.database import get_db, DATABASE_PATH
from services.security import hash_password

ROOM_TYPES = {
    "Single": {
        "count": 25,
        "floors": [1, 2, 3],
        "prefix": "S",
        "start": 100,
        "base_price": 2000,
        "max_price": 4000,
        "max_guests": 1,
        "bed_type": "Single",
        "amenities": [
            "Wi-Fi",
            "AC",
            "TV",
            "Hot Water",
            "Room Service",
            "Daily Housekeeping",
        ],
        "description": "Cozy single room perfect for solo travelers, featuring modern amenities with a comfortable single bed.",
        "view": "City View",
        "size": 220,
    },
    "Double": {
        "count": 25,
        "floors": [2, 3, 4],
        "prefix": "D",
        "start": 125,
        "base_price": 4500,
        "max_price": 7000,
        "max_guests": 2,
        "bed_type": "Queen",
        "amenities": [
            "Wi-Fi",
            "AC",
            "TV",
            "Mini-bar",
            "Work Desk",
            "Room Service",
            "Bathtub",
            "Daily Housekeeping",
        ],
        "description": "Spacious double room with a premium queen-sized bed, ideal for couples and business travelers.",
        "view": "City View",
        "size": 320,
    },
    "Family": {
        "count": 25,
        "floors": [4, 5],
        "prefix": "F",
        "start": 150,
        "base_price": 7500,
        "max_price": 11000,
        "max_guests": 4,
        "bed_type": "King + Bunk",
        "amenities": [
            "Wi-Fi",
            "AC",
            "2 TVs",
            "Mini Kitchen",
            "Extra Beds",
            "Room Service",
            "Bathtub",
            "Balcony",
            "Daily Housekeeping",
        ],
        "description": "Expansive family suite with separate sleeping areas, ideal for families with children.",
        "view": "Garden View",
        "size": 480,
    },
    "Couple": {
        "count": 15,
        "floors": [5, 6],
        "prefix": "C",
        "start": 175,
        "base_price": 6500,
        "max_price": 9500,
        "max_guests": 2,
        "bed_type": "King",
        "amenities": [
            "Wi-Fi",
            "AC",
            "TV",
            "Jacuzzi",
            "King Bed",
            "Romantic Décor",
            "Champagne",
            "Room Service",
            "Bathtub",
            "Daily Housekeeping",
        ],
        "description": "Romantic couple suite with a Jacuzzi, king-sized bed, and exquisite décor for a perfect romantic getaway.",
        "view": "Sea View",
        "size": 380,
    },
    "VIP Suite": {
        "count": 10,
        "floors": [6, 7],
        "prefix": "V",
        "start": 190,
        "base_price": 15000,
        "max_price": 25000,
        "max_guests": 3,
        "bed_type": "King",
        "amenities": [
            "Wi-Fi",
            "AC",
            "Jacuzzi",
            "Ocean View",
            "Butler Service",
            "Private Lounge",
            "Mini Bar",
            "Smart TV",
            "Balcony",
            "Private Pool Access",
            "24/7 Room Service",
        ],
        "description": "Opulent VIP Suite with breathtaking ocean views, butler service, and world-class amenities for the most discerning guests.",
        "view": "Ocean View",
        "size": 750,
    },
}

DEFAULT_USERS = [
    {
        "user_id": "user_superadmin_001",
        "email": "vikram@blissfulabodes.com",
        "phone": "+91 9876543210",
        "password": "Admin@123",
        "first_name": "Vikram",
        "last_name": "Patel",
        "role": "superadmin",
        "is_verified": 1,
        "department": "Executive",
        "tier_level": "Platinum",
        "loyalty_points": 50000,
    },
    {
        "user_id": "user_admin_001",
        "email": "anil@blissfulabodes.com",
        "phone": "+91 9876543211",
        "password": "Admin@123",
        "first_name": "Anil",
        "last_name": "Sharma",
        "role": "admin",
        "is_verified": 1,
        "department": "Management",
        "tier_level": "Gold",
        "loyalty_points": 25000,
    },
    {
        "user_id": "user_manager_001",
        "email": "suresh@blissfulabodes.com",
        "phone": "+91 9876543212",
        "password": "Staff@123",
        "first_name": "Suresh",
        "last_name": "Menon",
        "role": "manager",
        "is_verified": 1,
        "department": "Operations",
        "tier_level": "Silver",
        "loyalty_points": 5000,
    },
    {
        "user_id": "user_staff_001",
        "email": "priya@blissfulabodes.com",
        "phone": "+91 9876543213",
        "password": "Staff@123",
        "first_name": "Priya",
        "last_name": "Sharma",
        "role": "staff",
        "is_verified": 1,
        "department": "Front Desk",
        "shift": "morning",
        "tier_level": "Silver",
        "loyalty_points": 1000,
    },
    {
        "user_id": "user_guest_001",
        "email": "rajesh@example.com",
        "phone": "+91 9876543214",
        "password": "Guest@123",
        "first_name": "Rajesh",
        "last_name": "Kumar",
        "role": "guest",
        "is_verified": 1,
        "department": None,
        "tier_level": "Gold",
        "loyalty_points": 8500,
    },
    {
        "user_id": "user_guest_002",
        "email": "meena@example.com",
        "phone": "+91 9876543215",
        "password": "Guest@123",
        "first_name": "Meena",
        "last_name": "Iyer",
        "role": "guest",
        "is_verified": 1,
        "department": None,
        "tier_level": "Silver",
        "loyalty_points": 3200,
    },
    {
        "user_id": "user_staff_002",
        "email": "ravi@blissfulabodes.com",
        "phone": "+91 9876543216",
        "password": "Staff@123",
        "first_name": "Ravi",
        "last_name": "Kumar",
        "role": "staff",
        "is_verified": 1,
        "department": "Housekeeping",
        "shift": "afternoon",
        "tier_level": "Silver",
        "loyalty_points": 500,
    },
    {
        "user_id": "user_manager_002",
        "email": "kavitha@blissfulabodes.com",
        "phone": "+91 9876543217",
        "password": "Staff@123",
        "first_name": "Kavitha",
        "last_name": "Nair",
        "role": "manager",
        "is_verified": 1,
        "department": "Food & Beverage",
        "tier_level": "Silver",
        "loyalty_points": 2000,
    },
]

SAMPLE_REVIEWS = [
    {
        "overall_rating": 5,
        "comment": "Absolutely stunning hotel! The VIP suite had an incredible ocean view. Butler service was impeccable. Will definitely return!",
        "sentiment": "positive",
    },
    {
        "overall_rating": 4,
        "comment": "Very comfortable stay. The staff was extremely helpful and courteous. The room was clean and well-maintained.",
        "sentiment": "positive",
    },
    {
        "overall_rating": 5,
        "comment": "Best hotel in Chennai! Love the location near Marina Beach. The food was delicious and the pool was amazing.",
        "sentiment": "positive",
    },
    {
        "overall_rating": 3,
        "comment": "Decent stay but the WiFi was a bit slow. Room service could be faster. Overall okay experience.",
        "sentiment": "neutral",
    },
    {
        "overall_rating": 4,
        "comment": "The couple suite with Jacuzzi was wonderful for our anniversary. The romantic décor was perfect.",
        "sentiment": "positive",
    },
    {
        "overall_rating": 5,
        "comment": "Exceptional service! The manager personally greeted us. The family suite was spacious and the kids loved it.",
        "sentiment": "positive",
    },
    {
        "overall_rating": 2,
        "comment": "Room was okay but could be cleaner. AC was noisy. Expected more for the price.",
        "sentiment": "negative",
    },
    {
        "overall_rating": 5,
        "comment": "World-class experience! Every detail was perfect from check-in to check-out. The sea view is breathtaking.",
        "sentiment": "positive",
    },
    {
        "overall_rating": 4,
        "comment": "Great location, friendly staff. The breakfast buffet was excellent. Room was slightly small but comfortable.",
        "sentiment": "positive",
    },
    {
        "overall_rating": 5,
        "comment": "பிளிஸ்ஃபுல் அபோட்ஸ் அருமையான ஹோட்டல்! சேவை சிறந்தது. Everything was perfect!",
        "sentiment": "positive",
    },
]


def generate_rooms(conn):
    """Generate 100 rooms"""
    cursor = conn.cursor()
    room_idx = 0
    image_map = {
        "S": "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg",
        "D": "https://cdn.pixabay.com/photo/2020/12/24/19/10/hotel-room-5858068_1280.jpg",
        "F": "https://cdn.pixabay.com/photo/2020/12/24/19/11/hotel-room-5858069_1280.jpg",
        "C": "https://cdn.pixabay.com/photo/2021/02/07/20/08/luxury-5992539_1280.jpg",
        "V": "https://cdn.pixabay.com/photo/2019/12/26/16/51/luxury-suite-4720815_1280.jpg",
    }

    for room_type, config in ROOM_TYPES.items():
        floors = config["floors"]
        room_num = config["start"]

        for i in range(config["count"]):
            room_id = f"room_{config['prefix']}_{room_num:03d}"
            floor = floors[i % len(floors)]

            # Price variation
            price_range = config["max_price"] - config["base_price"]
            price = config["base_price"] + (price_range * (i / config["count"]))
            price = round(price / 100) * 100  # Round to nearest 100

            # Room status distribution
            status_weights = ["available"] * 12 + ["occupied"] * 6 + ["cleaning"] * 2
            status = random.choice(status_weights)

            images = json.dumps(
                [
                    image_map.get(config["prefix"], "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg"),
                    image_map.get(config["prefix"], "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg"),
                    image_map.get(config["prefix"], "https://cdn.pixabay.com/photo/2020/12/24/19/08/hotel-room-5858067_1280.jpg"),
                ]
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO rooms 
                (room_id, room_number, room_type, floor, base_price, current_price, 
                 max_guests, amenities, description, images, status, is_active,
                 view_type, bed_type, size_sqft)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
                (
                    room_id,
                    f"{config['prefix']}{room_num}",
                    room_type,
                    floor,
                    config["base_price"],
                    price,
                    config["max_guests"],
                    json.dumps(config["amenities"]),
                    config["description"],
                    images,
                    status,
                    config["view"],
                    config["bed_type"],
                    config["size"],
                ),
            )
            room_num += 1
            room_idx += 1

    conn.commit()
    print(f"[SEED] Generated {room_idx} rooms")


def generate_users(conn):
    """Create default users for all roles"""
    cursor = conn.cursor()

    for user in DEFAULT_USERS:
        password_hash = hash_password(user["password"])

        cursor.execute(
            """
            INSERT OR IGNORE INTO users 
            (user_id, email, phone, password_hash, first_name, last_name, role,
             loyalty_points, tier_level, is_active, is_verified, department, shift, preferences)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        """,
            (
                user["user_id"],
                user["email"],
                user["phone"],
                password_hash,
                user["first_name"],
                user["last_name"],
                user["role"],
                user.get("loyalty_points", 0),
                user.get("tier_level", "Silver"),
                user.get("is_verified", 0),
                user.get("department"),
                user.get("shift"),
                json.dumps({}),
            ),
        )

    conn.commit()
    print(f"[SEED] Created {len(DEFAULT_USERS)} default users")


def generate_sample_bookings(conn):
    """Generate sample historical bookings"""
    cursor = conn.cursor()

    cursor.execute("SELECT room_id, room_number FROM rooms")
    rooms = cursor.fetchall()

    users = ["user_guest_001", "user_guest_002"]
    statuses = ["confirmed", "completed", "confirmed", "completed", "cancelled"]

    for i in range(30):
        room = random.choice(rooms)
        user_id = random.choice(users)

        start_days_ago = random.randint(5, 120)
        stay_length = random.randint(1, 5)
        check_in = datetime.now() - timedelta(days=start_days_ago)
        check_out = check_in + timedelta(days=stay_length)

        base = random.choice([2000, 4500, 7500, 6500, 15000])
        gst = base * stay_length * 0.18
        total = base * stay_length + gst

        status = random.choice(statuses)

        booking_id = f"BK{datetime.now().strftime('%Y')}{i+1:05d}"

        cursor.execute(
            """
            INSERT OR IGNORE INTO bookings
            (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
             base_amount, gst_amount, total_amount, status, payment_status,
             payment_method, loyalty_points_earned, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                booking_id,
                user_id,
                room[0],
                room[1],
                check_in.strftime("%Y-%m-%d"),
                check_out.strftime("%Y-%m-%d"),
                random.randint(1, 2),
                base * stay_length,
                gst,
                total,
                status,
                "completed" if status == "completed" else "paid",
                random.choice(["UPI", "card", "netbanking"]),
                int((base * stay_length) / 10),
                (datetime.now() - timedelta(days=start_days_ago + 1)).isoformat(),
            ),
        )

    conn.commit()
    print("[SEED] Generated 30 sample bookings")


def generate_reviews(conn):
    """Generate sample reviews"""
    cursor = conn.cursor()

    cursor.execute("SELECT room_id FROM rooms LIMIT 20")
    rooms = cursor.fetchall()
    users = ["user_guest_001", "user_guest_002"]

    for i, review_data in enumerate(SAMPLE_REVIEWS):
        review_id = str(uuid.uuid4())
        room = rooms[i % len(rooms)]
        user = random.choice(users)

        aspects = {
            "cleanliness": random.uniform(3, 5),
            "staff": random.uniform(3, 5),
            "location": random.uniform(4, 5),
            "value": random.uniform(3, 5),
            "amenities": random.uniform(3, 5),
        }

        cursor.execute(
            """
            INSERT OR IGNORE INTO reviews
            (review_id, user_id, room_id, overall_rating, comment, 
             verified_stay, sentiment, sentiment_score,
             cleanliness_rating, staff_rating, location_rating, value_rating, amenities_rating)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                review_id,
                user,
                room[0],
                review_data["overall_rating"],
                review_data["comment"],
                review_data["sentiment"],
                (
                    0.85
                    if review_data["sentiment"] == "positive"
                    else -0.5 if review_data["sentiment"] == "negative" else 0
                ),
                round(aspects["cleanliness"], 1),
                round(aspects["staff"], 1),
                round(aspects["location"], 1),
                round(aspects["value"], 1),
                round(aspects["amenities"], 1),
            ),
        )

    conn.commit()
    print("[SEED] Generated sample reviews")


def generate_coupons(conn):
    """Generate default coupon codes"""
    cursor = conn.cursor()

    coupons = [
        ("WELCOME10", "percentage", 10, 0, 999999, "2026-12-31"),
        ("WEEKEND15", "percentage", 15, 2000, 500, "2026-08-31"),
        ("VIP25", "percentage", 25, 10000, 100, "2026-06-30"),
        ("FLAT500", "fixed", 500, 3000, 300, "2026-09-30"),
        ("PONGAL15", "percentage", 15, 1000, 200, "2026-01-31"),
        ("SUMMER20", "percentage", 20, 5000, 150, "2026-07-31"),
        ("DIWALI20", "percentage", 20, 5000, 200, "2026-11-30"),
        ("COUPLE30", "percentage", 30, 8000, 50, "2026-03-31"),
    ]

    for code, dtype, val, min_amount, max_uses, valid_until in coupons:
        coupon_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT OR IGNORE INTO coupons
            (coupon_id, code, discount_type, discount_value, min_booking_amount,
             max_uses, valid_until, is_active, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'user_admin_001')
        """,
            (coupon_id, code, dtype, val, min_amount, max_uses, valid_until),
        )

    conn.commit()
    print("[SEED] Generated coupon codes")


def generate_inventory(conn):
    """Generate inventory items"""
    cursor = conn.cursor()

    items = [
        ("Bed Sheets (Single)", "Linen", 200, 50),
        ("Bed Sheets (Double)", "Linen", 350, 80),
        ("Towels (Bath)", "Linen", 400, 100),
        ("Towels (Hand)", "Linen", 400, 100),
        ("Toiletry Kits", "Amenities", 500, 100),
        ("Shampoo (Bottles)", "Amenities", 300, 50),
        ("Soap Bars", "Amenities", 500, 100),
        ("Key Cards", "Equipment", 300, 100),
        ("Water Bottles (1L)", "F&B", 500, 100),
        ("Tea Bags", "F&B", 1000, 200),
        ("Coffee Sachets", "F&B", 800, 200),
        ("Toilet Paper Rolls", "Consumables", 600, 150),
        ("Room Freshener", "Amenities", 100, 30),
        ("Slippers (pairs)", "Amenities", 250, 50),
        ("Hangers", "Equipment", 400, 100),
    ]

    for name, category, stock, reorder in items:
        item_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT OR IGNORE INTO inventory
            (item_id, name, category, stock_count, reorder_level, unit)
            VALUES (?, ?, ?, ?, ?, 'units')
        """,
            (item_id, name, category, stock, reorder),
        )

    conn.commit()
    print("[SEED] Generated inventory items")


def generate_notifications(conn):
    """Generate sample notifications"""
    cursor = conn.cursor()

    notifs = [
        (
            "user_guest_001",
            "Booking Confirmed! 🎉",
            "Your booking BK202500001 has been confirmed. Check-in tomorrow at 2 PM.",
            "success",
            "/guest/bookings",
        ),
        (
            "user_guest_001",
            "Special Offer! 🎁",
            "Exclusive weekend offer - Get 20% off on your next booking with code WEEKEND15",
            "info",
            "/rooms",
        ),
        (
            "user_guest_001",
            "Loyalty Upgrade! 🏆",
            "Congratulations! You have been upgraded to Gold tier!",
            "success",
            "/guest/loyalty",
        ),
        (
            "user_admin_001",
            "Low Occupancy Alert ⚠️",
            "Occupancy is at 58% - below target. Consider activating promotional rates.",
            "warning",
            "/admin/analytics",
        ),
        (
            "user_admin_001",
            "New Review Posted ⭐",
            "A guest rated their stay 5 stars. Review requires moderation.",
            "info",
            "/admin/reviews",
        ),
        (
            "user_staff_001",
            "Room Checkout 🏃",
            "Room D132 has been checked out. Please schedule housekeeping.",
            "info",
            "/staff/housekeeping",
        ),
        (
            "user_manager_001",
            "Inventory Alert 📦",
            "Towel stock is below reorder level (80 units left). Please create purchase order.",
            "warning",
            "/manager/inventory",
        ),
    ]

    for user_id, title, msg, ntype, url in notifs:
        notif_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT OR IGNORE INTO notifications
            (notification_id, user_id, title, message, notification_type, action_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (notif_id, user_id, title, msg, ntype, url),
        )

    conn.commit()
    print("[SEED] Generated sample notifications")


def generate_upcoming_bookings(conn):
    """Generate upcoming bookings for demo"""
    cursor = conn.cursor()

    cursor.execute("SELECT room_id, room_number, current_price FROM rooms LIMIT 10")
    rooms = cursor.fetchall()

    for i in range(10):
        room = rooms[i % len(rooms)]
        days_ahead = random.randint(1, 15)
        stay = random.randint(1, 4)

        check_in = datetime.now() + timedelta(days=days_ahead)
        check_out = check_in + timedelta(days=stay)
        base = room[2] * stay
        gst = base * 0.18
        total = base + gst

        booking_id = f"BK{datetime.now().strftime('%Y')}U{i+1:04d}"
        user = "user_guest_001" if i % 2 == 0 else "user_guest_002"

        cursor.execute(
            """
            INSERT OR IGNORE INTO bookings
            (booking_id, user_id, room_id, room_number, check_in, check_out, num_guests,
             base_amount, gst_amount, total_amount, status, payment_status,
             payment_method, loyalty_points_earned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', 'paid', 'UPI', ?)
        """,
            (
                booking_id,
                user,
                room[0],
                room[1],
                check_in.strftime("%Y-%m-%d"),
                check_out.strftime("%Y-%m-%d"),
                random.randint(1, 2),
                base,
                gst,
                total,
                int(base / 10),
            ),
        )

    conn.commit()
    print("[SEED] Generated upcoming bookings")


def seed_all():
    """Run all seed functions"""
    from models.database import init_db

    init_db()

    conn = get_db()
    try:
        generate_users(conn)
        generate_rooms(conn)
        generate_sample_bookings(conn)
        generate_upcoming_bookings(conn)
        generate_reviews(conn)
        generate_coupons(conn)
        generate_inventory(conn)
        generate_notifications(conn)
        print("[SEED] ✅ Database seeding complete!")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_all()
