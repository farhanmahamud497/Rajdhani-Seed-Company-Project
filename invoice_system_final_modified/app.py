import base64
import os
import re
import sqlite3
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from weasyprint import HTML
from num2words import num2words
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ====================
# CONSTANTS & CONFIG
# ====================
DATABASE = 'invoices.db'
SCHEMA = 'schema.sql'

COMPANY_INFO = {
    'name': "Rajdhani Seed Company",
    'address': "174, Siddique Bazar, Hannan Mansion, Dhaka-1000, Bangladesh",
    'contacts': [
        "Cell: 01711-133256",
        "Cell: 01712-599600",
        "Phone: +88-02-226637665"
    ],
    'email': "rajdhani_seed@yahoo.com | rajdhaniseedbd@gmail.com"
}

# ====================
# FLASK APP SETUP
# ====================
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'your-secret-key-here'

# ====================
# AUTHENTICATION SETUP
# ====================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Hardcoded admin users
ADMINS = {
    'admin1': {'password': generate_password_hash('admin1pass'), 'id': 1},
    'admin2': {'password': generate_password_hash('admin2pass'), 'id': 2},
    'admin3': {'password': generate_password_hash('admin3pass'), 'id': 3}
}

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    for username, user_info in ADMINS.items():
        if user_info['id'] == int(user_id):
            return User(user_info['id'], username)
    return None

# ====================
# DATABASE FUNCTIONS
# ====================
def get_db():
    """Get a database connection with Row factory"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def init_db():
    """Initialize the database with our schema"""
    print("Initializing database...")
    db = get_db()
    try:
        with app.open_resource(SCHEMA, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        
        required_tables = {'products', 'invoices', 'invoice_items'}
        existing_tables = {row['name'] for row in 
                         db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        
        if not required_tables.issubset(existing_tables):
            raise Exception("Failed to create all required tables")
            
        print("Database initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        return False
    finally:
        db.close()

def check_db():
    """Check if database is properly initialized"""
    if not os.path.exists(DATABASE):
        return False
    
    db = get_db()
    try:
        required_tables = {'products', 'invoices', 'invoice_items'}
        existing_tables = {row['name'] for row in 
                         db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        return required_tables.issubset(existing_tables)
    except:
        return False
    finally:
        db.close()

def add_sample_products():
    """Add sample products to the database"""
    sample_products = [
        ("Tomato Seed", "Hybrid Tomato F1", "100g packet", 120.00, 500),
        ("Chili Seed", "Hot Chili Variety", "50g packet", 80.00, 300),
        ("Eggplant Seed", "Long Purple", "100g packet", 90.00, 200)
    ]
    
    db = get_db()
    try:
        for product in sample_products:
            db.execute(
                "INSERT INTO products (name, description, packing, rate, quantity) VALUES (?, ?, ?, ?, ?)",
                product
            )
        db.commit()
        print("Added sample products")
    except Exception as e:
        print(f"Error adding sample products: {str(e)}")
    finally:
        db.close()

# ====================
# UTILITY FUNCTIONS
# ====================
def encode_logo_to_base64():
    """Encode logo to base64 for reliable PDF embedding"""
    logo_path = os.path.join(app.static_folder, 'img', 'rajdhani_logo.png')
    try:
        with open(logo_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error loading logo: {str(e)}")
        return None

def get_logo_data():
    """Get logo data in appropriate format for both web and PDF"""
    base64_logo = encode_logo_to_base64()
    return {
        'web': url_for('static', filename='img/rajdhani_logo.png'),
        'pdf': f"data:image/png;base64,{base64_logo}" if base64_logo else None
    }

def validate_mobile_number(mobile):
    """Validate and clean mobile number"""
    clean_mobile = re.sub(r'\D', '', mobile)
    if len(clean_mobile) == 11 and clean_mobile.startswith('01'):
        return clean_mobile
    elif len(clean_mobile) == 13 and clean_mobile.startswith('8801'):
        return clean_mobile[3:]  # Remove country code
    elif len(clean_mobile) == 10 and clean_mobile.startswith('1'):
        return '0' + clean_mobile  # Add leading zero
    return None

def get_products():
    """Get all available products"""
    db = get_db()
    try:
        return db.execute('SELECT * FROM products WHERE quantity > 0 ORDER BY name').fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {str(e)}")
        return []
    finally:
        db.close()

def number_to_words(num):
    """Convert number to words for amount in words"""
    try:
        return num2words(num, lang='en_IN').title() + " Taka Only"
    except:
        return ""

# ====================
# AUTHENTICATION ROUTES
# ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in ADMINS and check_password_hash(ADMINS[username]['password'], password):
            user = User(ADMINS[username]['id'], username)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ====================
# APPLICATION ROUTES
# ====================
@app.route('/')
@login_required
def home():
    products = get_products()
    return render_template('invoice.html', products=products)

@app.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            description = request.form.get('description', '').strip()
            packing = request.form['packing'].strip()
            rate = float(request.form['rate'])
            quantity = int(request.form['quantity'])
            
            db = get_db()
            db.execute(
                "INSERT INTO products (name, description, packing, rate, quantity) VALUES (?, ?, ?, ?, ?)",
                (name, description, packing, rate, quantity)
            )
            db.commit()
            flash('Product added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Product with this name already exists!', 'danger')
        except ValueError:
            flash('Invalid price or quantity value!', 'danger')
        except Exception as e:
            flash(f'Error adding product: {str(e)}', 'danger')
        finally:
            db.close()
        return redirect(url_for('manage_products'))
    
    db = get_db()
    try:
        products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
        return render_template('products.html', products=products)
    finally:
        db.close()

@app.route('/products/add')
@login_required
def add_product_page():
    return render_template('add_product.html')

@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    db = get_db()
    try:
        product = db.execute('SELECT * FROM products WHERE id = ?', (id,)).fetchone()
        
        if not product:
            flash('Product not found!', 'danger')
            return redirect(url_for('manage_products'))
        
        if request.method == 'POST':
            name = request.form['name'].strip()
            description = request.form['description'].strip()
            packing = request.form['packing'].strip()
            rate = float(request.form['rate'])
            quantity = int(request.form['quantity'])
            
            try:
                db.execute(
                    "UPDATE products SET name = ?, description = ?, packing = ?, rate = ?, quantity = ? WHERE id = ?",
                    (name, description, packing, rate, quantity, id)
                )
                db.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('manage_products'))
            except sqlite3.IntegrityError:
                flash('Another product with this name already exists!', 'danger')
        
        return render_template('edit_product.html', product=product)
    finally:
        db.close()

@app.route('/products/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    db = get_db()
    try:
        db.execute('DELETE FROM products WHERE id = ?', (id,))
        db.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('manage_products'))

@app.route('/invoices')
@login_required
def invoice_list():
    db = get_db()
    try:
        invoices = db.execute('SELECT * FROM invoices ORDER BY created_at DESC').fetchall()
        return render_template('invoice_list.html', invoices=invoices)
    finally:
        db.close()

@app.route('/invoices/<invoice_number>')
@login_required
def view_invoice(invoice_number):
    db = get_db()
    try:
        # Fetch invoice data
        invoice = db.execute(
            'SELECT * FROM invoices WHERE invoice_number = ?', (invoice_number,)
        ).fetchone()
        
        if not invoice:
            flash('Invoice not found!', 'danger')
            return redirect(url_for('invoice_list'))
        
        # Fetch invoice items joined with product names
        items = db.execute(
            '''
            SELECT i.*, p.name as product_name
            FROM invoice_items i
            JOIN products p ON i.product_id = p.id
            WHERE i.invoice_id = ?
            ''',
            (invoice['id'],)
        ).fetchall()

        # Get logo data
        logo_data = get_logo_data()

        return render_template(
            'invoice_template.html',
            company={
                **COMPANY_INFO,
                'logo_web': logo_data['web'],
                'logo_pdf': logo_data['pdf']
            },
            buyer_info={
                'name': invoice['buyer_name'],
                'address': invoice['buyer_address'],
                'mobile': invoice['buyer_mobile'],
                'payment_method': invoice['payment_method']
            },
            invoice_number=invoice['invoice_number'],
            goods_description=invoice['goods_description'],
            items=items,
            total_amount=invoice['total_amount'],
            amount_in_words=invoice['amount_in_words'],
            invoice_date=datetime.strptime(invoice['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d %B, %Y'),
            is_pdf=False  # Indicate this is for web view
        )
    finally:
        db.close()

@app.route('/generate-invoice', methods=['POST'])
@login_required
def generate_invoice():
    try:
        action = request.form.get('action', 'preview')
        buyer_name = request.form.get('buyerName', '').strip()
        buyer_address = request.form.get('buyerAddress', '').strip()
        buyer_mobile = request.form.get('buyerMobile', '').strip()
        payment_method = request.form.get('paymentMethod', 'Cash')
        goods_description = request.form.get('goodsDescription', '').strip()
        
        if not buyer_name:
            raise ValueError("Buyer name is required")
        
        # Generate unique invoice number
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        clean_mobile = re.sub(r'\D', '', buyer_mobile)[-6:]  # Last 6 digits
        invoice_number = f"INV-{timestamp}-{clean_mobile or 'MOB'}"
        
        db = get_db()
        
        # Process items
        quantities = request.form.getlist('quantity[]')
        product_ids = request.form.getlist('product_id[]')
        packings = request.form.getlist('packing[]')
        rates = request.form.getlist('rate[]')
        
        # Validate items
        if not all([quantities, product_ids, packings, rates]) or len(quantities) == 0:
            flash("Please add at least one item to the invoice", "danger")
            return redirect(url_for('home'))
            
        items = []
        total_amount = 0.0

        for i in range(len(quantities)):
            try:
                quantity = int(quantities[i])
                product_id = int(product_ids[i])
                rate = float(rates[i])
                packing = packings[i].strip()
                
                if quantity <= 0 or rate < 0:
                    continue
                
                # Check product availability
                product = db.execute(
                    'SELECT name, quantity FROM products WHERE id = ?', 
                    (product_id,)
                ).fetchone()
                
                if not product:
                    raise ValueError(f"Product with ID {product_id} not found")
                
                if product['quantity'] < quantity:
                    raise ValueError(
                        f"Insufficient stock for {product['name']}. "
                        f"Available: {product['quantity']}, Requested: {quantity}"
                    )
                
                amount = quantity * rate
                items.append({
                    'product_id': product_id,
                    'product_name': product['name'],
                    'quantity': quantity,
                    'packing': packing,
                    'rate': rate,
                    'amount': amount
                })
                total_amount += amount
            except (ValueError, IndexError) as e:
                flash(str(e), 'danger')
                return redirect(url_for('home'))
        
        if not items:
            flash("No valid items in invoice", 'danger')
            return redirect(url_for('home'))
        
        # Create invoice record
        amount_in_words = number_to_words(total_amount)
        cur = db.cursor()
        cur.execute(
            "INSERT INTO invoices (invoice_number, buyer_name, buyer_address, buyer_mobile, "
            "payment_method, goods_description, total_amount, amount_in_words) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                invoice_number,
                buyer_name,
                buyer_address,
                buyer_mobile,
                payment_method,
                goods_description,
                total_amount,
                amount_in_words
            )
        )
        invoice_id = cur.lastrowid
        
        # Create invoice items
        for item in items:
            cur.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, product_name, quantity, packing, rate, amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    invoice_id,
                    item['product_id'],
                    item['product_name'],
                    item['quantity'],
                    item['packing'],
                    item['rate'],
                    item['amount']
                )
            )
            
            # Update product quantity
            db.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (item['quantity'], item['product_id'])
            )
        
        db.commit()
        
        # Generate PDF
        return generate_pdf(invoice_number, action)
    
    except Exception as e:
        flash(f"Error generating invoice: {str(e)}", 'danger')
        return redirect(url_for('home'))
    finally:
        db.close()

def generate_pdf(invoice_number, action):
    db = get_db()
    try:
        invoice = db.execute(
            'SELECT * FROM invoices WHERE invoice_number = ?', 
            (invoice_number,)
        ).fetchone()
        
        if not invoice:
            flash('Invoice not found!', 'danger')
            return redirect(url_for('invoice_list'))
        
        items = db.execute(
            'SELECT product_name, quantity, packing, rate, amount '
            'FROM invoice_items '
            'WHERE invoice_id = ?',
            (invoice['id'],)
        ).fetchall()
        
        # Get logo data
        logo_data = get_logo_data()
        
        invoice_data = {
            'company': {
                **COMPANY_INFO,
                'logo_web': logo_data['web'],
                'logo_pdf': logo_data['pdf']
            },
            'buyer_info': {
                'name': invoice['buyer_name'],
                'address': invoice['buyer_address'],
                'mobile': invoice['buyer_mobile'],
                'payment_method': invoice['payment_method']
            },
            'invoice_number': invoice['invoice_number'],
            'goods_description': invoice['goods_description'],
            'items': items,
            'total_amount': invoice['total_amount'],
            'amount_in_words': invoice['amount_in_words'],
            'invoice_date': datetime.strptime(invoice['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%d %B, %Y'),
            'is_pdf': True  # Indicate this is for PDF generation
        }
        
        rendered = render_template('invoice_template.html', **invoice_data)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as pdf:
            HTML(string=rendered).write_pdf(pdf.name)
            
            # Sanitize filename
            safe_invoice_number = re.sub(r'[^a-zA-Z0-9_-]', '', invoice_number)
            return send_file(
                pdf.name,
                download_name=f'Rajdhani_Invoice_{safe_invoice_number}.pdf',
                mimetype='application/pdf',
                as_attachment=(action == 'download')
            )
    finally:
        db.close()

# ====================
# ADDITIONAL ROUTES
# ====================
@app.route('/invoice-search')
@login_required
def invoice_search():
    """Render the invoice search form"""
    return render_template('invoice_search.html')

@app.route('/search-invoice', methods=['POST'])
@login_required
def search_invoice():
    """Handle invoice search form submission"""
    invoice_number = request.form.get('invoice_number')
    if not invoice_number:
        flash('Please enter an invoice number', 'danger')
        return redirect(url_for('invoice_search'))
    
    db = get_db()
    try:
        invoice = db.execute(
            'SELECT * FROM invoices WHERE invoice_number = ?', 
            (invoice_number,)
        ).fetchone()
        
        if invoice:
            return redirect(url_for('view_invoice', invoice_number=invoice_number))
        else:
            flash(f'Invoice {invoice_number} not found!', 'danger')
            return redirect(url_for('invoice_search'))
    finally:
        db.close()

@app.route('/recent-invoices')
@login_required
def recent_invoices():
    """Show recent invoices"""
    db = get_db()
    try:
        invoices = db.execute('SELECT * FROM invoices ORDER BY created_at DESC LIMIT 10').fetchall()
        return render_template('recent_invoices.html', invoices=invoices)
    finally:
        db.close()

@app.route('/inventory-report')
@login_required
def inventory_report():
    """Show inventory report"""
    db = get_db()
    try:
        products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
        return render_template('inventory_report.html', products=products)
    finally:
        db.close()

# ====================
# INITIALIZATION & RUN
# ====================
if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(os.path.join(app.static_folder, 'img'), exist_ok=True)
    
    # Initialize database if needed
    if not os.path.exists(DATABASE) or not check_db():
        print("Initializing database...")
        if init_db():
            add_sample_products()
        else:
            print("Database initialization failed. Please check schema.sql")
    
    app.run(debug=True, port=5001)