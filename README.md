# ShopSight

> A multi-shop sales management and analytics platform built with Flask, MySQL, Python, HTML, CSS, and JavaScript.

ShopSight lets multiple independent shops manage their own sales data — entered manually or imported via CSV — and see analytics and an ML-based revenue forecast for their business only. A platform Superadmin manages *which shops are registered*, with no access to any shop's sales figures.

---

## 📌 Project Overview

### Main goals
- Let shop owners self-register and manage their own shop.
- Enter sales manually or import them via CSV; export via CSV.
- Analyze shop-specific sales data with filters and charts.
- Forecast future revenue with an ML model trained on each shop's own history.
- Keep every shop's data strictly isolated from every other shop.
- Give a platform Superadmin the ability to manage shop *accounts* without ever seeing shop *data*.

---

## 👥 User Roles

ShopSight has two roles.

### 👑 Superadmin
Manages the platform itself, not any shop's sales. Created once via a command-line script — there is no public sign-up for this role.

**Can:**
- View a directory of all registered shops (name, owner, email, phone, signup date, active/suspended status).
- See aggregate counts (total shops, active shops).
- Suspend a shop (blocks that shop's login without touching their data) and reactivate it later.
- Permanently delete a shop (removes the owner's login and every sales row for that shop).
- Reset a shop owner's password, generating a one-time temporary password.

**Cannot:**
- View any shop's individual sales rows, totals, or charts.
- Reach a sales route at all — `/`, `/add`, `/edit`, `/delete`, `/import_csv`, `/export_csv` all redirect a Superadmin to `/admin`, even if the URL is typed directly.

This separation is enforced with a `@shop_scoped` / `@superadmin_only` decorator pair at the Flask route level — it is not a hidden UI link that a curious user could still reach by guessing a URL.

### 🏪 Shop Owner
Manages their own shop's data only.

**Can:**
- Add, edit, and delete their own sales records.
- Import sales via CSV, export their sales to CSV.
- View KPIs and charts filtered by product, date range, or month, with quick period tabs (today / yesterday / past 7 days / this month / all time).
- View a 6-month revenue forecast with a model-accuracy (R²) readout.
- Edit their own profile (name, email, department, phone, location).

**Cannot:**
- See or reach another shop's data — every query is scoped by `shop_id`, and edit/delete additionally verify the row belongs to that shop before touching it (so one shop can't edit another's sale just by guessing its ID in a URL).

---

## ✨ Features

### Authentication & security
- Passwords hashed with Werkzeug's `pbkdf2:sha256` — never stored in plaintext.
- Password policy enforced client- and server-side: 8+ characters, one uppercase, one lowercase, one number, one special character.
- Secrets (`SECRET_KEY`, DB credentials) come from environment variables / `.env`, never hardcoded in source.
- Per-user profile fields (name, email, department, phone, location) are stored server-side, scoped to that user's own row.

### Sales management
- Full CRUD on sales records, scoped to the logged-in shop.
- Filter by product, date range, or month.
- CSV import and export.

### Analytics
- Revenue and units-sold breakdown by product, with All / Month / Week / Today period tabs.
- KPI cards: total revenue, units sold, this month's revenue, top product, today/yesterday/week/month comparisons, month-over-month growth.

### ML forecasting
- 6-month revenue forecast from two models shown side by side: a regression fit on a time trend **plus** a cyclical sin/cos encoding of month-of-year (so it can represent seasonal patterns, not just a straight-line trend), and a 3-month moving-average baseline.
- Model accuracy (R²) is surfaced directly in the UI.
- `generate_synthetic_data.py` can seed a shop with realistic multi-year sales history (growth trend, festive-season spike, monsoon dip, weekend bump) so the forecast has enough signal to be meaningful on a fresh account.

### Superadmin dashboard
- Shop directory with registered/active counts.
- Suspend / reactivate / delete a shop.
- Generate a temporary password for a shop owner.
- No sales data anywhere on this page, by design.

### UI
- Light/dark theme toggle with corrected contrast in light mode.
- Charts sized to a fixed-height container so browser zoom doesn't cause runaway canvas growth.
- Self-registration form scrolls correctly on small screens.

---

## 🗂 Project Structure
```
app.py                     Flask app — routes, auth, ML forecasting logic
setup_db.sql                Database schema (shops, users, sales)
generate_synthetic_data.py Seeds realistic sales history for a shop
create_superadmin.py       One-time script to create a platform-owner login
requirements.txt
Procfile                   For gunicorn-based deployment (Render/Railway)
.env.example                Template for required environment variables
templates/
  index.html                Shop dashboard (KPIs, charts, ML forecast, records)
  login.html
  register.html              Shop self-registration
  edit.html                   Edit a single sale
  admin.html                  Superadmin shop directory
static/
  style.css
  script.js
```

## 🗃 Data Model
- **shops** — `id`, `name`, `slug`, `is_active`, `created_at`.
- **users** — `id`, `shop_id` (NULL for a Superadmin), `username` (globally unique), `password_hash`, `role` (`owner` | `superadmin`), `full_name`, `email`, `department`, `phone`, `location`, `created_at`.
- **sales** — `id`, `shop_id`, `product`, `quantity`, `price`, `date`.

Every sales query filters on `shop_id`, sourced from the session, never from a request parameter.

---

## 🚀 Local Setup
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # fill in your local DB credentials
mysql -u root -p < setup_db.sql

python app.py                   # http://localhost:5000
```
Go to `/register` to create your first shop and login.

**Seed sales history** (a new shop starts with zero sales, so there's nothing for the forecast to learn from):
```bash
python generate_synthetic_data.py --username <your_login_username> --months 24
```

**Create your Superadmin login** (one time, not through the public site):
```bash
python create_superadmin.py --username youradmin --password "Str0ng!Pass1"
```
Log in with that account and you'll land on `/admin`.

---

## ☁️ Deployment
This app runs comfortably on free tiers as of 2026:
- **App hosting** — Render (auto-detects `requirements.txt` and the `Procfile`, free HTTPS URL) or Railway.
- **Database** — free managed MySQL is harder to find than it used to be (Heroku and PlanetScale both dropped their free tiers). Railway's trial credit or Aiven's free MySQL tier both work for a portfolio-scale project; `db4free.net` is a slower but simple option for a demo link.
- Set `SECRET_KEY`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` as environment variables on your host — never commit `.env`.
- Leave `FLASK_DEBUG` unset (or `0`) in production.

---

## 🎓 Tech Stack
Flask · MySQL · scikit-learn · NumPy · Werkzeug · Chart.js · python-dotenv · Gunicorn
