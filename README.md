# ShopSight

A multi-tenant sales analytics dashboard with ML-based revenue forecasting
(linear regression + moving-average), built with Flask, MySQL, and Chart.js.

## Features
- **Multi-tenant accounts** — any shop can self-register and gets an isolated
  dashboard; no shop can see another shop's data.
- **Real authentication** — passwords are salted and hashed with
  Werkzeug's `pbkdf2:sha256`, never stored in plaintext.
- **Sales CRUD** — add, edit, delete, filter by product/date/month, CSV
  import/export.
- **ML forecasting** — 6-month revenue forecast via linear regression and a
  moving-average baseline, with a model-accuracy (R²) readout.
- **Light/dark theme**, responsive layout.

## Local setup
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit .env with your local DB credentials
mysql -u root -p < setup_db.sql

python app.py                   # http://localhost:5000
```
Go to `/register` to create your first shop and login — there are no more
hardcoded demo accounts.

### Seed realistic sales history (for the ML model)
A brand-new shop has zero sales rows, so the forecast has nothing to learn
from. Seed 24 months of realistic, seasonal synthetic data:
```bash
python generate_synthetic_data.py --username <your_login_username> --months 24
```
This isn't random noise — it models a monthly growth trend per product,
an Oct-Dec festive-season spike, a monsoon-month dip, and a weekend bump,
so the linear regression actually has a trend + seasonality to fit.

## Platform-owner (superadmin) access
There's a separate role for whoever owns the platform itself — you, not any
individual shop. It's created once via a script, not through public sign-up:
```bash
python create_superadmin.py --username youradmin --password "Str0ng!Pass1"
```
Logging in as that account lands on `/admin` — a directory of registered
shops (name, owner, email, phone, signup date). It has **no route into any
shop's sales data**: every sales route in `app.py` is wrapped in a
`@shop_scoped` decorator that hard-redirects a superadmin away, even if they
type the URL directly. This is real, enforced access control, not just a
hidden nav link.

**A note on "encrypted so we can't access it":** what's built here is
*application-level access control* — the Flask app itself refuses to serve
sales data to a superadmin. That's the right amount of protection for a
project like this and it's what most SaaS platforms actually do. It does
**not** stop someone with direct MySQL access (e.g. via phpMyAdmin) from
reading the `sales` table — that would require encrypting each shop's sales
values at the database layer with a key the platform owner doesn't hold,
which is a much bigger, genuinely hard problem (key management, and every
query needs the shop's own key to decrypt). Worth knowing the difference if
this comes up in an interview, but not worth building unless you have a
specific reason to need it.

## How the multi-tenancy works
- `shops` — one row per business.
- `users` — belongs to one shop; `username` is globally unique (acts like
  a login handle). Password is hashed, never plaintext.
- `sales` — every row carries a `shop_id`. Every query in `app.py` filters
  by `session['shop_id']`, and edit/delete routes also check the row's
  `shop_id` matches the session before touching it — so one shop can't
  edit or delete another shop's data just by guessing a URL.

## The ML model
Two forecasts run side by side, both surfaced in the UI with an R² accuracy readout:
- **Regression (trend + seasonality)** — not a plain single-feature linear
  regression on a time index (that structurally cannot represent a
  festive-season spike or a monsoon dip, no matter how much data you feed
  it). It fits on a time trend *plus* a cyclical sin/cos encoding of
  month-of-year, so it can actually learn seasonal shape. On synthetic
  data with a real seasonal pattern, this took R² from ~0% to ~59% in
  testing — worth mentioning if this comes up in an interview, since "I
  added more data" and "I fixed the model" are different claims and this
  project can back up the second one.
- **Moving average (3-month window)** — a simple baseline for comparison.

Further improvements if you get real multi-year data:
- Add holiday/promotion flags as explicit features.
- Try `Prophet` or a seasonal ARIMA, which handle this natively instead of
  hand-rolled Fourier features.
- If you get a dataset from Kaggle, look for **2+ years of history** and a
  schema close to yours (product, quantity, price/revenue, date) — a
  categorically different dataset (e.g. Walmart weekly sales) needs column
  mapping before it's useful here.

## Deployment (resume-ready, free tier)
This app is small enough to run comfortably on free tiers. As of 2026:

- **App hosting — Render** is the easiest free option: connect your GitHub
  repo, it auto-detects `requirements.txt` and the `Procfile`
  (`web: gunicorn app:app`), and gives you a free HTTPS URL. Railway is a
  solid alternative with a similar workflow.
- **Database** — free *managed MySQL* has gotten harder to find (Heroku and
  PlanetScale both dropped their free tiers). Practical options:
  - Railway's free trial credit covers a small MySQL instance for a
    portfolio-scale project.
  - Aiven has a free MySQL tier suitable for low-traffic demos.
  - If you just need something to point at for a resume demo, `db4free.net`
    works too but is slow — fine for a live demo link, not for real load.
- Set `SECRET_KEY`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` as
  environment variables in your host's dashboard (never commit `.env`).
- Set `FLASK_DEBUG=0` (or leave unset) in production — debug mode leaks
  a Python console to anyone who can trigger a 500 error.

Since exact free-tier terms shift often, check current pricing pages
before committing to one.

## For your resume
Worth calling out explicitly, since interviewers will ask about these:
- Multi-tenant data isolation (shop-scoped queries + ownership checks on
  every mutation, not just reads)
- Hashed credentials, env-based secrets management
- ML forecasting pipeline (feature construction → model → 6-month
  projection with an accuracy metric surfaced in the UI)
- CSV import/export, filterable analytics, responsive dark/light UI
