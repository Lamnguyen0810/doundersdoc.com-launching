"""Dev helper: create all tables directly (production uses Alembic)."""
from app.db import init_db

if __name__ == "__main__":
    init_db()
    print("tables created")
