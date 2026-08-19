import os, re, csv, json, secrets, string
from datetime import datetime, timedelta, date
from decimal import Decimal

from flask import (Flask, render_template, request, redirect,
                    Response, session, flash)
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import numpy as np
from sklearn.linear_model import LinearRegression

try:
    from dotenv import load_dotenv
    load_dotenv()          # loads variables from a local .env file if present
except ImportError:
    pass                    # python-dotenv is optional in production (env vars set by host)

app = Flask(__name__)

# ── Config (all from environment — never hardcode secrets) ───────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-insecure-change-me')
DEBUG_MODE     = os.environ.get('FLASK_DEBUG', '0') == '1'

DB_CONFIG = {
    'host':     os.environ.get('DB_HOST', 'localhost'),
    'user':     os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'sales_dashboard'),
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def logged_in():
    return session.get('user_id') is not None

def is_superadmin():
    return session.get('role') == 'superadmin'

from functools import wraps

def shop_scoped(view):
    """Requires a logged-in shop user. Superadmins are explicitly blocked —
    they manage the shop directory, they never touch sales data, even via a
    hand-typed URL."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not logged_in(): return redirect('/login')
        if is_superadmin(): return redirect('/admin')
        return view(*args, **kwargs)
    return wrapped

def superadmin_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not logged_in(): return redirect('/login')
        if not is_superadmin(): return redirect('/')
        return view(*args, **kwargs)
    return wrapped

# ── Password strength: 8+ chars, upper, lower, digit, special char ───────────
PASSWORD_RULE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')
PASSWORD_HELP = 'Password needs 8+ characters, one uppercase, one lowercase, one number, and one special character.'

# ── Decimal / Date JSON fix ───────────────────────────────────────────────────
class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):          return float(obj)
        if isinstance(obj, (datetime, date)): return str(obj)
        return super().default(obj)
def jdump(obj): return json.dumps(obj, cls=SafeEncoder)

def slugify(name):
    s = re.sub(r'[^a-z0-9]+', '-', name.strip().lower()).strip('-')
    return s or 'shop'

# ══════════════════════════════════════════════════════════════════════════════
#  ML ENGINE  (unchanged logic — linear regression + moving-average forecast)
# ══════════════════════════════════════════════════════════════════════════════
def _add_months(d: date, n: int) -> date:
    """Correct calendar-month arithmetic (the old '+31 days' approach drifted
    off the real month by the 6th forecast step)."""
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, 1)

def run_ml_forecast(monthly_labels, monthly_values, n_ahead=6):
    n = len(monthly_values)
    if n < 3:
        return [], [], [], [], 0, 0, 0, 0

    # ── Features: a linear time trend PLUS cyclical (sin/cos) month-of-year
    #    encoding. A single-feature regression on just "month index" can only
    #    ever fit a straight line — it structurally cannot represent a
    #    festive-season spike or a monsoon dip, no matter how much data you
    #    feed it. Adding sin/cos(month) lets a still-simple linear model
    #    capture seasonality without needing a much heavier model.
    months = [int(lbl.split('-')[1]) for lbl in monthly_labels]
    def features(idx, month):
        angle = 2 * np.pi * month / 12
        return [idx, np.sin(angle), np.cos(angle)]

    X = np.array([features(i, months[i]) for i in range(n)])
    y = np.array(monthly_values, dtype=float)
    model = LinearRegression().fit(X, y)
    r2    = max(0, round(model.score(X, y) * 100, 1))

    last_dt = datetime.strptime(monthly_labels[-1], '%Y-%m').date()
    lr_labels, lr_values = [], []
    for i in range(1, n_ahead + 1):
        fdate = _add_months(last_dt, i)
        lr_labels.append(fdate.strftime('%Y-%m'))
        fx = np.array([features(n + i - 1, fdate.month)])
        lr_values.append(max(0, round(float(model.predict(fx)[0]), 2)))

    window  = min(3, n)
    history = list(y)
    ma_labels, ma_values = [], []
    for i in range(1, n_ahead + 1):
        mv = round(float(np.mean(history[-window:])), 2)
        ma_labels.append(_add_months(last_dt, i).strftime('%Y-%m'))
        ma_values.append(max(0, mv))
        history.append(mv)

    growth_rate = 0
    if n >= 2 and monthly_values[0] > 0:
        growth_rate = round(
            ((monthly_values[-1] - monthly_values[0]) / monthly_values[0]) * 100 / max(n - 1, 1), 1)

    return (lr_labels, lr_values, ma_labels, ma_values,
            lr_values[0] if lr_values else 0,
            ma_values[0] if ma_values else 0,
            r2, growth_rate)

# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        shop_name = request.form.get('shop_name', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email     = request.form.get('email', '').strip()
        username  = request.form.get('username', '').strip()
        password  = request.form.get('password', '')
        confirm   = request.form.get('confirm_password', '')

        if not shop_name or not username or not password or not full_name or not email:
            error = 'All fields are required.'
        elif not PASSWORD_RULE.match(password):
            error = PASSWORD_HELP
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                error = 'That username is already taken. Please choose another.'
            else:
                slug = slugify(shop_name)
                # ensure slug uniqueness
                cur.execute("SELECT id FROM shops WHERE slug=%s", (slug,))
                if cur.fetchone():
                    slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

                cur.execute("INSERT INTO shops (name, slug) VALUES (%s,%s)", (shop_name, slug))
                shop_id = cur.lastrowid
                cur.execute(
                    """INSERT INTO users (shop_id, username, password_hash, role, full_name, email)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (shop_id, username, generate_password_hash(password), 'owner', full_name, email))
                db.commit()
                user_id = cur.lastrowid
                db.close()

                session['user_id']   = user_id
                session['username']  = username
                session['shop_id']   = shop_id
                session['shop_name'] = shop_name
                session['role']      = 'owner'
                return redirect('/')
            db.close()
    return render_template('register.html', error=error)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES     = 15

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""SELECT u.*, s.name AS shop_name, s.is_active AS shop_active
                       FROM users u
                       LEFT JOIN shops s ON s.id = u.shop_id
                       WHERE u.username=%s""", (username,))
        user = cur.fetchone()

        now = datetime.utcnow()
        if user and user['locked_until'] and user['locked_until'] > now:
            mins_left = max(1, int((user['locked_until'] - now).total_seconds() // 60) + 1)
            error = f"Too many failed attempts. Try again in {mins_left} minute(s)."
        elif user and user['role'] == 'owner' and user['shop_active'] == 0:
            error = 'This shop account has been deactivated. Contact the platform admin.'
        elif user and check_password_hash(user['password_hash'], password):
            # successful login — clear any lockout state
            cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=%s", (user['id'],))
            db.commit()
            session['user_id']   = user['id']
            session['username']  = user['username']
            session['shop_id']   = user['shop_id']
            session['shop_name'] = user['shop_name'] or 'Platform Admin'
            session['role']      = user['role']
            db.close()
            return redirect('/admin' if user['role'] == 'superadmin' else '/')
        else:
            if user:
                attempts = user['failed_attempts'] + 1
                locked_until = None
                if attempts >= MAX_FAILED_ATTEMPTS:
                    locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                    attempts = 0
                cur.execute("UPDATE users SET failed_attempts=%s, locked_until=%s WHERE id=%s",
                            (attempts, locked_until, user['id']))
                db.commit()
            error = 'Invalid username or password. Please try again.'
        db.close()
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/profile/update', methods=['POST'])
def update_profile():
    if not logged_in(): return redirect('/login')
    full_name  = request.form.get('full_name', '').strip()
    email      = request.form.get('email', '').strip()
    department = request.form.get('department', '').strip()
    phone      = request.form.get('phone', '').strip()
    location   = request.form.get('location', '').strip()

    db = get_db(); c = db.cursor()
    c.execute("""UPDATE users SET full_name=%s, email=%s, department=%s, phone=%s, location=%s
                 WHERE id=%s""",
              (full_name, email, department, phone, location, session['user_id']))
    db.commit(); db.close()
    return redirect('/')

# ══════════════════════════════════════════════════════════════════════════════
#  HOME DASHBOARD  (protected + shop-scoped)
# ══════════════════════════════════════════════════════════════════════════════
@app.route('/')
@shop_scoped
def home():
    shop_id = session['shop_id']

    db     = get_db()
    cursor = db.cursor(dictionary=True)

    # Real per-user profile fields (previously — and incorrectly — stored in
    # browser localStorage under one shared key, so every login on the same
    # browser showed the same profile). Now scoped to this user's own row.
    cursor.execute("""SELECT full_name, email, department, phone, location
                       FROM users WHERE id=%s""", (session['user_id'],))
    profile = cursor.fetchone() or {}
    today        = datetime.today().date()
    yesterday    = today - timedelta(days=1)
    week_start   = today - timedelta(days=6)
    month_start  = today.replace(day=1)
    prev_m_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_m_end   = month_start - timedelta(days=1)

    # Filters
    f_product   = request.args.get('product', '')
    f_date_from = request.args.get('date_from', '')
    f_date_to   = request.args.get('date_to', '')
    f_month     = request.args.get('month', '')

    wp, params = ["shop_id = %s"], [shop_id]
    if f_product:
        wp.append("product = %s"); params.append(f_product)
    if f_month:
        wp.append("DATE_FORMAT(date,'%%Y-%%m') = %s"); params.append(f_month)
    elif f_date_from and f_date_to:
        wp.append("date BETWEEN %s AND %s"); params.extend([f_date_from, f_date_to])
    elif f_date_from:
        wp.append("date >= %s"); params.append(f_date_from)
    elif f_date_to:
        wp.append("date <= %s"); params.append(f_date_to)
    where_sql = "WHERE " + " AND ".join(wp)

    cursor.execute(f"SELECT * FROM sales {where_sql} ORDER BY date DESC", params)
    sales = cursor.fetchall()

    cursor.execute("SELECT DISTINCT product FROM sales WHERE shop_id=%s ORDER BY product", (shop_id,))
    all_products = [r['product'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT DATE_FORMAT(date,'%Y-%m') AS m FROM sales WHERE shop_id=%s ORDER BY m DESC", (shop_id,))
    all_months = [r['m'] for r in cursor.fetchall()]

    def as_date(d): return d if isinstance(d, date) else d.date()
    def prev(rows, fd, td=None):
        td = td or fd
        return sum(float(r['quantity'] * r['price']) for r in rows
                   if fd <= as_date(r['date']) <= td)

    total_revenue = sum(float(r['quantity'] * r['price']) for r in sales)
    total_units   = sum(r['quantity'] for r in sales)
    total_orders  = len(sales)
    avg_order_val = round(total_revenue / total_orders, 2) if total_orders else 0

    today_rev      = prev(sales, today)
    yesterday_rev  = prev(sales, yesterday)
    week_rev       = prev(sales, week_start, today)
    month_rev      = prev(sales, month_start, today)
    prev_month_rev = prev(sales, prev_m_start, prev_m_end)
    month_growth   = round((month_rev - prev_month_rev) / prev_month_rev * 100, 1) if prev_month_rev else None

    cursor.execute("""
        SELECT product, SUM(quantity) AS total_qty, SUM(quantity*price) AS total_rev
        FROM sales WHERE shop_id=%s AND date >= %s GROUP BY product ORDER BY total_rev DESC LIMIT 1
    """, (shop_id, month_start))
    tm = cursor.fetchone()
    top_month_product = tm['product']         if tm else "N/A"
    top_month_rev     = float(tm['total_rev']) if tm else 0

    cursor.execute(f"""
        SELECT product, SUM(quantity) AS total_qty, SUM(quantity*price) AS total_rev
        FROM sales {where_sql} GROUP BY product ORDER BY total_rev DESC
    """, params)
    pd2 = cursor.fetchall()
    chart_labels  = [r['product']          for r in pd2]
    chart_qty     = [int(r['total_qty'])   for r in pd2]
    chart_revenue = [float(r['total_rev']) for r in pd2]
    top_product   = pd2[0]['product'] if pd2 else "N/A"

    cursor.execute("""
        SELECT DATE_FORMAT(date,'%Y-%m') AS month, SUM(quantity*price) AS monthly_rev
        FROM sales WHERE shop_id=%s GROUP BY month ORDER BY month
    """, (shop_id,))
    md = cursor.fetchall()
    monthly_labels = [r['month']              for r in md]
    monthly_values = [float(r['monthly_rev']) for r in md]

    (lr_labels, lr_values, ma_labels, ma_values,
     next_lr, next_ma, model_accuracy, growth_rate) = run_ml_forecast(
         monthly_labels, monthly_values, n_ahead=6)

    all_fc_labels = monthly_labels + lr_labels
    hist_series   = monthly_values + [None] * len(lr_labels)
    lr_series     = ([None] * (len(monthly_values) - 1) + [monthly_values[-1]] + lr_values
                     if monthly_values else lr_values)
    ma_series     = ([None] * (len(monthly_values) - 1) + [monthly_values[-1]] + ma_values
                     if monthly_values else ma_values)

    lr_tooltips = [''] * len(monthly_labels) + [f'LR: ₹{v:,.0f}' for v in lr_values]
    ma_tooltips = [''] * len(monthly_labels) + [f'MA: ₹{v:,.0f}' for v in ma_values]

    def prod_period(fd, td=None):
        td = td or fd
        c2 = db.cursor(dictionary=True)
        c2.execute("""SELECT product, SUM(quantity) AS qty, SUM(quantity*price) AS rev
                      FROM sales WHERE shop_id=%s AND date BETWEEN %s AND %s
                      GROUP BY product ORDER BY rev DESC""", (shop_id, fd, td))
        rows = c2.fetchall()
        return {'labels': [r['product'] for r in rows],
                'qty':    [int(r['qty']) for r in rows],
                'rev':    [float(r['rev']) for r in rows]}

    period_today     = prod_period(today)
    period_yesterday = prod_period(yesterday)
    period_week      = prod_period(week_start, today)
    period_month     = prod_period(month_start, today)
    period_all       = {'labels': chart_labels, 'qty': chart_qty, 'rev': chart_revenue}

    db.close()
    return render_template("index.html",
        username=session['username'], shop_name=session['shop_name'], role=session['role'],
        profile=profile,
        sales=sales,
        all_products=all_products, all_months=all_months,
        f_product=f_product, f_date_from=f_date_from,
        f_date_to=f_date_to, f_month=f_month,
        total_revenue=total_revenue, total_units=total_units,
        total_orders=total_orders,  avg_order_val=avg_order_val,
        today_rev=today_rev, yesterday_rev=yesterday_rev,
        week_rev=week_rev,   month_rev=month_rev,
        prev_month_rev=prev_month_rev, month_growth=month_growth,
        top_product=top_product,
        top_month_product=top_month_product, top_month_rev=top_month_rev,
        growth_rate=growth_rate,
        next_lr=round(next_lr, 2), next_ma=round(next_ma, 2),
        model_accuracy=model_accuracy,
        chart_labels    =jdump(chart_labels),
        chart_qty       =jdump(chart_qty),
        chart_revenue   =jdump(chart_revenue),
        monthly_labels  =jdump(monthly_labels),
        monthly_values  =jdump(monthly_values),
        all_fc_labels   =jdump(all_fc_labels),
        hist_series     =jdump(hist_series),
        lr_series       =jdump(lr_series),
        ma_series       =jdump(ma_series),
        lr_tooltips     =jdump(lr_tooltips),
        ma_tooltips     =jdump(ma_tooltips),
        lr_labels       =jdump(lr_labels),
        lr_values       =jdump(lr_values),
        ma_labels       =jdump(ma_labels),
        ma_values       =jdump(ma_values),
        period_today    =jdump(period_today),
        period_yesterday=jdump(period_yesterday),
        period_week     =jdump(period_week),
        period_month    =jdump(period_month),
        period_all      =jdump(period_all),
        today_str=str(today),
    )

# ── CRUD routes (all protected + shop-scoped) ────────────────────────────────
@app.route('/add', methods=['POST'])
@shop_scoped
def add_sale():
    db = get_db(); c = db.cursor()
    c.execute("INSERT INTO sales (shop_id,product,quantity,price,date) VALUES (%s,%s,%s,%s,%s)",
              (session['shop_id'], request.form['product'], int(request.form['quantity']),
               float(request.form['price']),
               request.form.get('date') or str(datetime.today().date())))
    db.commit(); db.close(); return redirect('/')

@app.route('/edit/<int:sid>', methods=['GET', 'POST'])
@shop_scoped
def edit_sale(sid):
    shop_id = session['shop_id']
    db = get_db(); c = db.cursor(dictionary=True)
    if request.method == 'POST':
        c.execute("""UPDATE sales SET product=%s,quantity=%s,price=%s,date=%s
                     WHERE id=%s AND shop_id=%s""",
                  (request.form['product'], int(request.form['quantity']),
                   float(request.form['price']),
                   request.form.get('date') or str(datetime.today().date()), sid, shop_id))
        db.commit(); db.close(); return redirect('/')
    c.execute("SELECT * FROM sales WHERE id=%s AND shop_id=%s", (sid, shop_id))
    sale = c.fetchone(); db.close()
    if not sale:
        return redirect('/')   # not found, or belongs to a different shop
    return render_template("edit.html", sale=sale)

@app.route('/delete/<int:sid>', methods=['POST'])
@shop_scoped
def delete_sale(sid):
    db = get_db(); c = db.cursor()
    c.execute("DELETE FROM sales WHERE id=%s AND shop_id=%s", (sid, session['shop_id']))
    db.commit(); db.close()
    return redirect('/')

@app.route('/import_csv', methods=['POST'])
@shop_scoped
def import_csv():
    f = request.files.get('csv_file')
    if not f: return redirect('/')
    db = get_db(); c = db.cursor()
    for row in csv.DictReader(f.stream.read().decode('utf-8').splitlines()):
        c.execute("INSERT INTO sales (shop_id,product,quantity,price,date) VALUES (%s,%s,%s,%s,%s)",
                  (session['shop_id'],
                   row.get('Product') or row.get('product', ''),
                   int(row.get('Quantity') or row.get('quantity', 0)),
                   float(row.get('Price') or row.get('price', 0)),
                   row.get('Date') or row.get('date') or str(datetime.today().date())))
    db.commit(); db.close(); return redirect('/')

@app.route('/export_csv')
@shop_scoped
def export_csv():
    db = get_db(); c = db.cursor(dictionary=True)
    c.execute("SELECT * FROM sales WHERE shop_id=%s ORDER BY date DESC", (session['shop_id'],))
    rows = c.fetchall(); db.close()
    def gen():
        yield "id,product,quantity,price,revenue,date\n"
        for r in rows:
            yield f"{r['id']},{r['product']},{r['quantity']},{float(r['price']):.2f},{float(r['quantity']*r['price']):.2f},{r['date']}\n"
    return Response(gen(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=sales_export.csv"})

# ══════════════════════════════════════════════════════════════════════════════
#  SUPERADMIN — platform-owner view. Shop directory & account management ONLY.
#  Every route below stays off the `sales` table on purpose — a superadmin
#  manages *who* is registered and *whether* their account is in good
#  standing, never what any individual shop sold. See README for the
#  access-model notes.
# ══════════════════════════════════════════════════════════════════════════════
def generate_temp_password():
    """A random password that already satisfies PASSWORD_RULE."""
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(12)) + secrets.choice('!@#$%^&*')
        if PASSWORD_RULE.match(pwd):
            return pwd

@app.route('/admin')
@superadmin_only
def admin_dashboard():
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS n FROM shops")
    shop_count = cur.fetchone()['n']
    cur.execute("SELECT COUNT(*) AS n FROM shops WHERE is_active=0")
    deactivated_count = cur.fetchone()['n']
    cur.execute("""
        SELECT s.id, s.name, s.slug, s.created_at, s.is_active,
               u.username AS owner_username, u.full_name, u.email, u.phone
        FROM shops s
        JOIN users u ON u.shop_id = s.id AND u.role = 'owner'
        ORDER BY s.created_at DESC
        LIMIT 6
    """)
    recent_shops = cur.fetchall()
    db.close()
    return render_template('admin.html', shop_count=shop_count,
                            active_count=shop_count - deactivated_count,
                            deactivated_count=deactivated_count,
                            recent_shops=recent_shops,
                            username=session['username'])

@app.route('/admin/shops')
@superadmin_only
def admin_shops():
    q      = request.args.get('q', '').strip()
    status = request.args.get('status', '')   # '', 'active', 'inactive'

    db  = get_db()
    cur = db.cursor(dictionary=True)
    sql = """
        SELECT s.id, s.name, s.slug, s.created_at, s.is_active,
               u.id AS owner_id, u.username AS owner_username,
               u.full_name, u.email, u.phone
        FROM shops s
        JOIN users u ON u.shop_id = s.id AND u.role = 'owner'
        WHERE 1=1
    """
    params = []
    if q:
        sql += """ AND (s.name LIKE %s OR u.full_name LIKE %s
                         OR u.email LIKE %s OR u.username LIKE %s)"""
        like = f"%{q}%"
        params += [like, like, like, like]
    if status == 'active':
        sql += " AND s.is_active=1"
    elif status == 'inactive':
        sql += " AND s.is_active=0"
    sql += " ORDER BY s.created_at DESC"

    cur.execute(sql, params)
    shops = cur.fetchall()
    db.close()
    return render_template('admin_shops.html', shops=shops, q=q, status=status,
                            username=session['username'])

@app.route('/admin/shops/<int:shop_id>/update', methods=['POST'])
@superadmin_only
def admin_shop_update(shop_id):
    shop_name  = request.form.get('shop_name', '').strip()
    full_name  = request.form.get('full_name', '').strip()
    email      = request.form.get('email', '').strip()
    phone      = request.form.get('phone', '').strip()

    if not shop_name or not full_name:
        flash('Shop name and owner name are required.', 'error')
        return redirect('/admin/shops')

    db = get_db(); cur = db.cursor()
    cur.execute("UPDATE shops SET name=%s WHERE id=%s", (shop_name, shop_id))
    cur.execute("""UPDATE users SET full_name=%s, email=%s, phone=%s
                    WHERE shop_id=%s AND role='owner'""",
                (full_name, email, phone, shop_id))
    db.commit(); db.close()
    flash(f'"{shop_name}" updated.', 'success')
    return redirect('/admin/shops')

@app.route('/admin/shops/<int:shop_id>/toggle-active', methods=['POST'])
@superadmin_only
def admin_shop_toggle_active(shop_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT name, is_active FROM shops WHERE id=%s", (shop_id,))
    shop = cur.fetchone()
    if not shop:
        db.close()
        flash('Shop not found.', 'error')
        return redirect('/admin/shops')

    new_state = 0 if shop['is_active'] else 1
    cur.execute("UPDATE shops SET is_active=%s WHERE id=%s", (new_state, shop_id))
    db.commit(); db.close()
    verb = 'reactivated' if new_state else 'deactivated'
    flash(f'"{shop["name"]}" {verb}. Its owner will {"regain" if new_state else "lose"} login access immediately.',
          'success')
    return redirect('/admin/shops')

@app.route('/admin/shops/<int:shop_id>/reset-password', methods=['POST'])
@superadmin_only
def admin_shop_reset_password(shop_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, username FROM users WHERE shop_id=%s AND role='owner'", (shop_id,))
    owner = cur.fetchone()
    if not owner:
        db.close()
        flash('Shop owner not found.', 'error')
        return redirect('/admin/shops')

    temp_password = generate_temp_password()
    cur.execute("""UPDATE users SET password_hash=%s, failed_attempts=0, locked_until=NULL
                    WHERE id=%s""",
                (generate_password_hash(temp_password), owner['id']))
    db.commit(); db.close()
    # Shown once — we only ever store the hash, never the plaintext password.
    flash(f'New temporary password for "{owner["username"]}": {temp_password} '
          f'— share it securely, it will not be shown again.', 'success')
    return redirect('/admin/shops')

if __name__ == '__main__':
    app.run(debug=DEBUG_MODE)
