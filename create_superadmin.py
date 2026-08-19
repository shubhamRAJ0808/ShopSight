"""
create_superadmin.py
───────────────────────────────────────────────────────────────────────────
Creates a platform-owner ("superadmin") login. There is deliberately no
public sign-up route for this — a superadmin account is created once, by
whoever owns the platform, by running this script directly on the server.

A superadmin has shop_id = NULL and can only reach /admin (the shop
directory: names, owners, contact info, registration dates). Every sales
route is hard-blocked for this role at the Flask level (see @shop_scoped
in app.py) — a superadmin cannot view, export, or touch any shop's sales
data through the app, full stop.

Usage:
    python create_superadmin.py --username youradmin --password "Str0ng!Pass"
"""
import os, argparse, re
from werkzeug.security import generate_password_hash
import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'sales_dashboard'),
}

PASSWORD_RULE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--username', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--full-name', default='Platform Admin')
    args = ap.parse_args()

    if not PASSWORD_RULE.match(args.password):
        raise SystemExit(
            "Password needs 8+ characters, one uppercase, one lowercase, "
            "one number, and one special character.")

    db  = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id FROM users WHERE username=%s", (args.username,))
    if cur.fetchone():
        raise SystemExit(f"Username '{args.username}' already exists.")

    cur.execute(
        """INSERT INTO users (shop_id, username, password_hash, role, full_name)
           VALUES (NULL, %s, %s, 'superadmin', %s)""",
        (args.username, generate_password_hash(args.password), args.full_name))
    db.commit()
    db.close()
    print(f"Superadmin '{args.username}' created. Log in at /login — you'll land on /admin.")
