from database import db_cursor

def create_tables():
    with db_cursor() as cur:

        cur.execute("""
        CREATE TABLE IF NOT EXISTS shoes (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            price NUMERIC(10,2) NOT NULL,
            sizes TEXT NOT NULL,
            color TEXT,
            quantity INTEGER DEFAULT 0,
            category TEXT,
            image_url TEXT,
            description TEXT,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            shoe_id INTEGER,
            shoe_title TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            selected_size TEXT,
            delivery_location TEXT,
            quantity INTEGER,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        );
        """)

        cur.execute("""
        INSERT INTO system_settings(setting_key, setting_value)
        VALUES
        ('admin_pin','123456'),
        ('admin_phone','+251943910788'),
        ('imgbb_key','ce2a839521108eaf5f62bed0552ae258')
        ON CONFLICT(setting_key) DO NOTHING;
        """)