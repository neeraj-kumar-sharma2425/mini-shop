import os
import secrets
import sqlite3

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database ka path. Deploy par DATABASE_PATH env variable se change kar sakte hain.
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'shop.db'))

app = Flask(__name__)
# SECRET_KEY deploy par env variable mein rakhein. Na ho to random key banti hai
# (tab server restart hone par sab users ko dobara login karna padega).
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)


# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS cart_items (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            PRIMARY KEY (user_id, product_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        );
    ''')
    count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    if count == 0:
        sample = [
            ('Wireless Headphones', 1999.0, 25, 'Electronics'),
            ('Smart Watch', 2999.0, 15, 'Electronics'),
            ('Cotton T-Shirt', 499.0, 50, 'Clothing'),
            ('Running Shoes', 2499.0, 20, 'Footwear'),
            ('Coffee Mug', 299.0, 100, 'Home'),
            ('Backpack', 1299.0, 30, 'Accessories'),
        ]
        conn.executemany(
            'INSERT INTO products (name, price, stock, category) VALUES (?, ?, ?, ?)', sample)
    conn.commit()
    conn.close()


# Server start hote hi tables aur sample products ready ho jayein
init_db()


# ---------- Helpers ----------
def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    conn = get_db()
    user = conn.execute('SELECT id, name, email FROM users WHERE id = ?', (uid,)).fetchone()
    conn.close()
    return dict(user) if user else None


# ---------- Pages ----------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/health')
def health():
    # Deploy platform ye check karta hai ki app chal raha hai ya nahi
    return jsonify(status='ok')


# ---------- Products ----------
@app.route('/api/products')
def list_products():
    conn = get_db()
    rows = conn.execute('SELECT * FROM products ORDER BY id').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------- Auth ----------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not name or not email or len(password) < 6:
        return jsonify(ok=False, message='Naam, email bharein aur password kam se kam 6 characters ka ho'), 400

    conn = get_db()
    try:
        conn.execute('INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)',
                     (name, email, generate_password_hash(password)))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify(ok=False, message='Ye email pehle se registered hai'), 409
    conn.close()
    return jsonify(ok=True, message='Registration successful! Ab login karein')


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    if user and check_password_hash(user['password_hash'], data.get('password') or ''):
        session['user_id'] = user['id']
        return jsonify(ok=True, message='Login successful',
                       user={'id': user['id'], 'name': user['name']})
    return jsonify(ok=False, message='Email ya password galat hai'), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify(ok=True, message='Logout ho gaye')


@app.route('/api/me')
def me():
    return jsonify(user=current_user())


# ---------- Cart ----------
@app.route('/api/cart', methods=['GET'])
def get_cart():
    user = current_user()
    if not user:
        return jsonify(items=[], total=0)
    conn = get_db()
    rows = conn.execute('''
        SELECT p.id, p.name, p.price, c.quantity
        FROM cart_items c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
    ''', (user['id'],)).fetchall()
    conn.close()
    items, total = [], 0.0
    for r in rows:
        subtotal = r['price'] * r['quantity']
        total += subtotal
        items.append({'id': r['id'], 'name': r['name'], 'price': r['price'],
                      'quantity': r['quantity'], 'subtotal': subtotal})
    return jsonify(items=items, total=total)


@app.route('/api/cart', methods=['POST'])
def add_to_cart():
    user = current_user()
    if not user:
        return jsonify(ok=False, message='Pehle login karein'), 401
    data = request.get_json(silent=True) or {}
    try:
        product_id = int(data['product_id'])
        qty = max(1, int(data.get('quantity', 1)))
    except (KeyError, TypeError, ValueError):
        return jsonify(ok=False, message='Galat data bheja gaya'), 400

    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        conn.close()
        return jsonify(ok=False, message='Product nahi mila'), 404
    conn.execute('''
        INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)
        ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity
    ''', (user['id'], product_id, qty))
    conn.commit()
    conn.close()
    return jsonify(ok=True, message=product['name'] + ' cart mein add ho gaya')


# ---------- Checkout & Orders ----------
@app.route('/api/checkout', methods=['POST'])
def checkout():
    user = current_user()
    if not user:
        return jsonify(ok=False, message='Pehle login karein'), 401
    conn = get_db()
    rows = conn.execute('''
        SELECT p.id, p.name, p.price, p.stock, c.quantity
        FROM cart_items c
        JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
    ''', (user['id'],)).fetchall()
    if not rows:
        conn.close()
        return jsonify(ok=False, message='Cart khaali hai'), 400

    # Order banane se pehle stock check karte hain
    for r in rows:
        if r['stock'] < r['quantity']:
            conn.close()
            return jsonify(ok=False, message='Stock kam hai: ' + r['name']), 409

    total = sum(r['price'] * r['quantity'] for r in rows)
    cur = conn.execute('INSERT INTO orders (user_id, total, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
                       (user['id'], total))
    order_id = cur.lastrowid
    for r in rows:
        conn.execute('INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)',
                     (order_id, r['id'], r['quantity'], r['price']))
        conn.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (r['quantity'], r['id']))
    conn.execute('DELETE FROM cart_items WHERE user_id = ?', (user['id'],))
    conn.commit()
    conn.close()
    return jsonify(ok=True, message='Order #%d placed! Total ₹%.2f' % (order_id, total))


@app.route('/api/orders')
def my_orders():
    user = current_user()
    if not user:
        return jsonify(orders=[])
    conn = get_db()
    rows = conn.execute('SELECT id, total, created_at FROM orders WHERE user_id = ? ORDER BY id DESC',
                        (user['id'],)).fetchall()
    conn.close()
    return jsonify(orders=[dict(r) for r in rows])


if __name__ == '__main__':
    # Local chalane ke liye: python app.py  (deploy par gunicorn use hota hai)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
