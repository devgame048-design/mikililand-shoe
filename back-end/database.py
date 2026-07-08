import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config

@contextmanager
def db_cursor():
    conn = psycopg2.connect(Config.DATABASE_URL)

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()