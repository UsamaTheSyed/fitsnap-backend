"""
FitSnap B2B Widget — SQLite Database Layer
Creates and manages the brands + brand_products tables.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fitsnap_widget.db")


def init_db():
    """Create tables if they don't exist. Called once on app startup."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT NOT NULL,
            website_url TEXT,
            email TEXT,
            api_key TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            monthly_tryon_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS brand_products (
            id TEXT PRIMARY KEY,
            brand_api_key TEXT NOT NULL,
            product_name TEXT,
            product_image_url TEXT,
            product_url TEXT,
            price TEXT,
            category TEXT,
            description TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (brand_api_key) REFERENCES brands(api_key)
        )
    """)

    conn.commit()
    conn.close()


def get_db():
    """Return a connection with Row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
