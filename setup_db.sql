-- ─────────────────────────────────────────────────────────────
-- ShopSight — MySQL Setup Script (Multi-tenant v2)
-- Run this ONCE before starting the Flask app.
-- Shop accounts are created through the app's /register page —
-- this script only creates the empty schema.
-- ─────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS sales_dashboard;
USE sales_dashboard;

-- 1. Shops — one row per tenant/business using the dashboard.
--    This is the "company directory" a platform superadmin can see —
--    who is registered, and how to contact them. It holds no sales data.
CREATE TABLE IF NOT EXISTS shops (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(150) NOT NULL,
    slug       VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users — each shop-owner user belongs to exactly one shop.
--    'superadmin' accounts have shop_id = NULL (platform staff, not a shop).
--    Username is globally unique (acts like a login handle/email).
--    password_hash stores a salted Werkzeug pbkdf2:sha256 hash — never plaintext.
--    full_name/email/department/phone/location are per-user profile fields —
--    previously these were (incorrectly) stored in browser localStorage under
--    one shared key, so every account on the same browser saw the same values.
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    shop_id       INT NULL,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'owner',   -- 'owner' | 'superadmin'
    full_name     VARCHAR(150) NULL,
    email         VARCHAR(150) NULL,
    department    VARCHAR(100) NULL,
    phone         VARCHAR(30)  NULL,
    location      VARCHAR(150) NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE
);

-- 3. Sales — every row is scoped to a shop_id so tenants never see each other's data
CREATE TABLE IF NOT EXISTS sales (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    shop_id   INT NOT NULL,
    product   VARCHAR(100) NOT NULL,
    quantity  INT          NOT NULL,
    price     DECIMAL(10,2) NOT NULL,
    date      DATE         DEFAULT (CURRENT_DATE),
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE CASCADE,
    INDEX idx_shop_date (shop_id, date)
);

-- ─── Done! ────────────────────────────────────────────────
-- Next steps:
--   1. Start the app and go to /register to create your first shop + owner login.
--   2. Run generate_synthetic_data.py to seed realistic sales history (see README).
--   3. Run create_superadmin.py once to create your own platform-owner login
--      (there is no public signup for this — see README).
