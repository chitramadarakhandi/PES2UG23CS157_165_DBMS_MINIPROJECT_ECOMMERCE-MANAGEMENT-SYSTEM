# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import get_db_connection
from utils import login_required, admin_required

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_secret')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXT = {'png','jpg','jpeg','gif'}

# Helper: allowed file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

# HOME - show search bar & featured items
@app.route('/')
def home():
    q = request.args.get('q','')
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    if q:
        cur.execute("SELECT * FROM products WHERE name LIKE %s OR category LIKE %s ORDER BY created_at DESC", (f'%{q}%', f'%{q}%'))
    else:
        cur.execute("SELECT * FROM products ORDER BY created_at DESC LIMIT 12")
    products = cur.fetchall()
    cur.close(); conn.close()
    return render_template('home.html', products=products, q=q)

# PRODUCTS listing
@app.route('/products')
def products():
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products ORDER BY name")
    items = cur.fetchall()
    cur.close(); conn.close()
    return render_template('products.html', products=items)

# PRODUCT DETAILS
@app.route('/product/<int:pid>')
def product_detail(pid):
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE product_id=%s", (pid,))
    p = cur.fetchone()
    cur.close(); conn.close()
    if not p:
        return "Product not found", 404
    return render_template('product_detail.html', p=p)

# REGISTER
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        if not (name and email and password):
            flash("Please fill all fields", 'danger'); return redirect(url_for('register'))
        pw_hash = generate_password_hash(password)
        conn = get_db_connection(); cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'customer')", (name,email,pw_hash))
            conn.commit()
            flash("Registered successfully, please login", 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash("Error: " + str(e), 'danger')
        finally:
            cur.close(); conn.close()
    return render_template('register.html')

# LOGIN
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db_connection(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash("Logged in", 'success')

            # Redirect admin directly to dashboard, customers to home
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('home'))

        flash("Invalid credentials", 'danger')
    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ADMIN: add product (with image upload)
@app.route('/admin/add_product', methods=['GET','POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        category = request.form.get('category')
        description = request.form.get('description')
        price = float(request.form.get('price',0))
        stock = int(request.form.get('stock_qty',0))
        image = request.files.get('image')
        filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image.save(dest)
        conn = get_db_connection(); cur = conn.cursor()
        try:
            cur.execute("INSERT INTO products (name,category,description,price,stock_qty,image_path) VALUES (%s,%s,%s,%s,%s,%s)",
                        (name,category,description,price,stock,filename))
            conn.commit()
            flash("Product added", 'success')
            return redirect(url_for('products'))
        except Exception as e:
            conn.rollback()
            flash("Error: "+str(e),'danger')
        finally:
            cur.close(); conn.close()
    return render_template('add_product.html')

# ADMIN: delete product
@app.route('/admin/delete_product/<int:pid>', methods=['POST'])
@admin_required
def delete_product(pid):
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE product_id=%s", (pid,))
    conn.commit(); cur.close(); conn.close()
    flash("Product deleted",'info')
    return redirect(url_for('products'))

# CART (session-based)
def _get_cart():
    return session.setdefault('cart', {})

@app.route('/cart')
def cart():
    cart = _get_cart()
    items = []
    total = 0.0
    for pid, it in cart.items():
        items.append({'product_id': int(pid), 'name': it['name'], 'price': it['price'], 'qty': it['qty'], 'subtotal': it['price']*it['qty']})
        total += it['price']*it['qty']
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add/<int:pid>', methods=['POST'])
def cart_add(pid):
    qty = int(request.form.get('qty',1))
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products WHERE product_id=%s", (pid,))
    p = cur.fetchone(); cur.close(); conn.close()
    if not p:
        flash("Product not found",'danger'); return redirect(url_for('products'))
    cart = _get_cart()
    key = str(pid)
    if key in cart:
        cart[key]['qty'] += qty
    else:
        cart[key] = {'name': p['name'], 'price': float(p['price']), 'qty': qty}
    session.modified = True
    flash("Added to cart", 'success')
    return redirect(request.referrer or url_for('products'))

@app.route('/cart/remove/<int:pid>', methods=['POST'])
def cart_remove(pid):
    cart = _get_cart()
    cart.pop(str(pid), None)
    session.modified = True
    return redirect(url_for('cart'))

# Checkout (creates order, order_details, payment)
@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    cart = _get_cart()
    if not cart:
        flash("Cart empty",'warning'); return redirect(url_for('products'))
    items = []
    total = 0.0
    for pid, it in cart.items():
        items.append({'product_id': int(pid), 'name': it['name'], 'price': it['price'], 'qty': it['qty']})
        total += it['price'] * it['qty']

    if request.method == 'POST':
        user_id = session['user_id']
        conn = get_db_connection(); cur = conn.cursor()
        try:
            # create order
            cur.execute("INSERT INTO orders (user_id,status) VALUES (%s,'Pending')", (user_id,))
            order_id = cur.lastrowid
            # insert order_details
            for it in items:
                cur.execute("INSERT INTO order_details (order_id,product_id,quantity,price) VALUES (%s,%s,%s,%s)",
                            (order_id, it['product_id'], it['qty'], it['price']))
            # call stored proc to calc total
            cur.execute("CALL sp_calc_order_total(%s)", (order_id,))
            # fetch total
            cur.execute("SELECT total_amount FROM orders WHERE order_id=%s", (order_id,))
            tot = cur.fetchone()[0]
            # simulate payment
            cur.execute("INSERT INTO payments (order_id,amount,payment_mode,payment_status) VALUES (%s,%s,%s,'Success')",
                        (order_id, tot, request.form.get('payment_mode','Card')))
            # update order status
            cur.execute("UPDATE orders SET status='Confirmed' WHERE order_id=%s", (order_id,))
            conn.commit()
            session['cart'] = {}
            flash("Order placed successfully! Order ID: {}".format(order_id),'success')
            return redirect(url_for('orders'))
        except Exception as e:
            conn.rollback()
            flash("Error processing order: "+str(e),'danger')
        finally:
            cur.close(); conn.close()
    return render_template('checkout.html', items=items, total=total)

# ORDERS
@app.route('/orders')
@login_required
def orders():
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    if session.get('role') == 'admin':
        cur.execute("SELECT o.*, u.name as customer FROM orders o JOIN users u ON o.user_id=u.user_id ORDER BY o.order_date DESC")
        orders = cur.fetchall()
    else:
        cur.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY order_date DESC", (session['user_id'],))
        orders = cur.fetchall()
    # fetch details
    for o in orders:
        cur.execute("SELECT od.*, p.name FROM order_details od JOIN products p ON od.product_id=p.product_id WHERE od.order_id=%s", (o['order_id'],))
        o['items'] = cur.fetchall()
    cur.close(); conn.close()
    return render_template('orders.html', orders=orders)

# ADMIN DASHBOARD (stats)
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS cnt FROM products"); products = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) AS cnt FROM orders"); orders = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role='customer'"); customers = cur.fetchone()['cnt']
    cur.execute("SELECT fn_total_revenue() AS revenue"); revenue = cur.fetchone()['revenue']
    cur.close(); conn.close()
    return render_template('admin_dashboard.html', products=products, orders=orders, customers=customers, revenue=revenue)

# helper to serve images (Flask serves static automatically, but this is optional)
@app.route('/images/<path:filename>')
def images(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# === TEMPORARY ROUTE: Create admin user ===
# ADMIN: Manage all products
@app.route('/admin/manage_products')
@admin_required
def manage_products():
    conn = get_db_connection(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM products ORDER BY created_at DESC")
    products = cur.fetchall()
    cur.close(); conn.close()
    return render_template('manage_products.html', products=products)


if __name__ == '__main__':
    app.run(debug=True)
