from flask import Flask, request, jsonify
from flask_cors import CORS
from models import create_tables
from database import db_cursor
from functools import wraps, lru_cache
import requests
import json
import time

app = Flask(__name__)

# Allows your Netlify frontend to securely communicate with this API without CORS blocks
CORS(app, resources={r"/*": {"origins": "*"}})

# Automatically initialize database tables on startup
create_tables()

# Authentication Middleware - MUST BE DEFINED BEFORE USING IT
def require_admin_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token != "mikililand-admin-session-token":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def home():
    return {
        "status": "running",
        "message": "Mikililand Backend V2"
    }

# 1. Configuration Endpoint (Fetches admin settings like phone numbers)
@app.route("/config", methods=["GET"])
def get_config():
    try:
        with db_cursor() as cur:
            cur.execute("SELECT setting_key, setting_value FROM system_settings;")
            rows = cur.fetchall()
            # Structures rows into a key-value dictionary object
            settings = {row['setting_key']: row['setting_value'] for row in rows}
        return jsonify(settings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Shoes Catalog Endpoint (GET - Public)
# 2. Shoes Catalog Endpoint (GET - Public)
@app.route("/shoes", methods=["GET"])
def get_shoes():
    try:
        with db_cursor() as cur:
            # Fix: Only fetch items that are actively set to 'available'
            cur.execute("SELECT * FROM shoes WHERE status = 'available' ORDER BY id DESC;")
            shoes = cur.fetchall()
        return jsonify(shoes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Admin Create Shoe (Authenticated)
@app.route("/admin/shoes", methods=["POST"])
@require_admin_token
def admin_create_shoe():
    try:
        data = request.json or {}
        # Validate required fields
        required_fields = ['name', 'brand', 'price', 'sizes', 'image_url']
        if not all(data.get(field) for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate price is numeric
        try:
            float(data.get('price'))
        except (ValueError, TypeError):
            return jsonify({"error": "Price must be a valid number"}), 400
        
        # Convert sizes string to array
        sizes_str = data.get('sizes', '')
        sizes_array = [s.strip() for s in sizes_str.replace(',', ' ').split() if s.strip()]
        
        with db_cursor() as cur:
            cur.execute("""
                INSERT INTO shoes (name, brand, price, sizes, color, quantity, category, image_url, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (
                data.get('name'), data.get('brand'), data.get('price'), 
                json.dumps(sizes_array),  # Convert to JSON
                data.get('color'), data.get('quantity', 1), data.get('category'),
                data.get('image_url'), data.get('description'), 'available'
            ))
            shoe_id = cur.fetchone()['id']
        return jsonify({"success": True, "message": "Shoe added successfully", "id": shoe_id}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Old POST /shoes endpoint (backward compatibility)
@app.route("/shoes", methods=["POST"])
def handle_shoes_post():
    try:
        data = request.json or {}
        # Validate required fields
        required_fields = ['name', 'brand', 'price', 'sizes']
        if not all(data.get(field) for field in required_fields):
            return jsonify({"error": "Missing required fields: name, brand, price, sizes"}), 400
        
        # Validate price is numeric
        try:
            float(data.get('price'))
        except (ValueError, TypeError):
            return jsonify({"error": "Price must be a valid number"}), 400
        
        # Convert sizes string to array
        sizes_str = data.get('sizes', '')
        sizes_array = [s.strip() for s in sizes_str.replace(',', ' ').split() if s.strip()]
        
        with db_cursor() as cur:
            cur.execute("""
                INSERT INTO shoes (name, brand, price, sizes, color, quantity, category, image_url, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (
                data.get('name'), data.get('brand'), data.get('price'), json.dumps(sizes_array),
                data.get('color'), data.get('quantity', 0), data.get('category'),
                data.get('image_url'), data.get('description'), data.get('status', 'available')
            ))
            shoe_id = cur.fetchone()['id']
        return jsonify({"message": "Shoe added successfully", "id": shoe_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 3. Admin Login Authentication Endpoint
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json or {}
        # Supports both "pin" or "password" field variations depending on frontend choices
        input_pin = data.get("pin") or data.get("password") or data.get("passcode")
        
        if not input_pin:
            return jsonify({"error": "PIN or Password is required"}), 400

        with db_cursor() as cur:
            cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'admin_pin';")
            result = cur.fetchone()
            db_pin = result['setting_value'] if result else "123456"

        if str(input_pin) == str(db_pin):
            return jsonify({
                "success": True, 
                "message": "Login successful",
                "token": "mikililand-admin-session-token"
            }), 200
        else:
            return jsonify({"success": False, "error": "Invalid PIN"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. Customer Orders Endpoint (To handle checkout workflow)
@app.route("/orders", methods=["GET", "POST"])
def handle_orders():
    if request.method == "GET":
        try:
            with db_cursor() as cur:
                cur.execute("SELECT * FROM orders ORDER BY id DESC;")
                orders = cur.fetchall()
            return jsonify(orders), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    elif request.method == "POST":
        try:
            data = request.json or {}
            # Validate required fields
            required_fields = ['shoe_id', 'shoe_title', 'customer_name', 'customer_phone', 'selected_size', 'delivery_location']
            if not all(data.get(field) for field in required_fields):
                return jsonify({"error": "Missing required fields: shoe_id, shoe_title, customer_name, customer_phone, selected_size, delivery_location"}), 400
            
            # Validate quantity is positive integer
            try:
                quantity = int(data.get('quantity', 1))
                if quantity <= 0:
                    return jsonify({"error": "Quantity must be greater than 0"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Quantity must be a valid integer"}), 400
            
            with db_cursor() as cur:
                cur.execute("""
                    INSERT INTO orders (shoe_id, shoe_title, customer_name, customer_phone, selected_size, delivery_location, quantity, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                """, (
                    data.get('shoe_id'), data.get('shoe_title'), data.get('customer_name'), data.get('customer_phone'), data.get('selected_size'), data.get('delivery_location'),
                    quantity, data.get('status', 'Pending')
                ))
                order_id = cur.fetchone()['id']
            return jsonify({"message": "Order placed successfully", "id": order_id}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# 5. Admin Dashboard Endpoint
@app.route("/admin/dashboard", methods=["GET"])
@require_admin_token
def admin_dashboard():
    try:
        with db_cursor() as cur:
            # Get metrics
            cur.execute("SELECT COUNT(*) as count, SUM(quantity) as total FROM shoes WHERE status = 'available';")
            stock_data = cur.fetchone()
            
            cur.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'Delivered';")
            sold_data = cur.fetchone()
            
            # Calculate revenue from delivered orders by joining with shoes
            cur.execute("""
                SELECT SUM(CAST(shoes.price AS NUMERIC) * orders.quantity) as total 
                FROM orders 
                LEFT JOIN shoes ON orders.shoe_id = shoes.id 
                WHERE orders.status = 'Delivered';
            """)
            revenue_data = cur.fetchone()
            
            # Get all shoes
            cur.execute("SELECT * FROM shoes ORDER BY id DESC;")
            shoes = cur.fetchall()
            
            # Get all orders
            cur.execute("SELECT * FROM orders ORDER BY id DESC;")
            orders = cur.fetchall()
            
            # Get settings
            cur.execute("SELECT setting_key, setting_value FROM system_settings;")
            settings = {row['setting_key']: row['setting_value'] for row in cur.fetchall()}
            
            return jsonify({
                "metrics": {
                    "total_stock": stock_data['total'] or 0,
                    "total_sold": sold_data['count'] or 0,
                    "total_revenue": float(revenue_data['total'] or 0)
                },
                "shoes": shoes,
                "orders": orders,
                "admin_phone": settings.get('admin_phone'),
                "imgbb_key": settings.get('imgbb_key')
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 6. Admin Settings Endpoint (Save API key, phone, PIN)
@app.route("/admin/settings", methods=["POST"])
@require_admin_token
def save_admin_settings():
    try:
        data = request.json or {}
        
        with db_cursor() as cur:
            if data.get('admin_phone'):
                cur.execute("""
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES ('admin_phone', %s)
                    ON CONFLICT(setting_key) DO UPDATE SET setting_value = %s;
                """, (data.get('admin_phone'), data.get('admin_phone')))
            
            if data.get('imgbb_key'):
                cur.execute("""
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES ('imgbb_key', %s)
                    ON CONFLICT(setting_key) DO UPDATE SET setting_value = %s;
                """, (data.get('imgbb_key'), data.get('imgbb_key')))
            
            if data.get('new_pin'):
                cur.execute("""
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES ('admin_pin', %s)
                    ON CONFLICT(setting_key) DO UPDATE SET setting_value = %s;
                """, (data.get('new_pin'), data.get('new_pin')))
        
        return jsonify({"message": "Settings saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 7. Admin Image Upload Endpoint
@app.route("/admin/upload", methods=["POST"])
@require_admin_token
def admin_upload():
    try:
        if 'image' not in request.files:
            return jsonify({"success": False, "message": "No image provided"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"}), 400
        
        # Get API key from database
        with db_cursor() as cur:
            cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'imgbb_key';")
            result = cur.fetchone()
            api_key = result['setting_value'] if result else None
        
        if not api_key:
            return jsonify({"success": False, "message": "ImgBB API key not configured"}), 400
        
        # Upload to ImgBB
        imgbb_url = "https://api.imgbb.com/1/upload"
        files = {'image': (file.filename, file.read())}
        data = {'key': api_key}
        
        response = requests.post(imgbb_url, files=files, data=data, timeout=15)
        
        if response.status_code == 200:
            imgbb_data = response.json()
            if imgbb_data.get('success'):
                return jsonify({
                    "success": True, 
                    "url": imgbb_data['data']['display_url']
                }), 200
            else:
                return jsonify({"success": False, "message": "ImgBB upload failed"}), 400
        else:
            return jsonify({"success": False, "message": "ImgBB connection error"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# 8. Admin Shoe Edit/Delete Endpoints
@app.route("/admin/shoes/<int:shoe_id>", methods=["PUT", "DELETE"])
@require_admin_token
def admin_manage_shoe(shoe_id):
    try:
        with db_cursor() as cur:
            if request.method == "PUT":
                data = request.json or {}
                # Convert sizes string to array
                sizes_str = data.get('sizes', '')
                sizes_array = [s.strip() for s in sizes_str.replace(',', ' ').split() if s.strip()]
                
                cur.execute("""
                    UPDATE shoes 
                    SET name=%s, brand=%s, price=%s, sizes=%s, color=%s, quantity=%s, 
                        category=%s, image_url=%s, description=%s, status=%s
                    WHERE id=%s;
                """, (
                    data.get('name'), data.get('brand'), data.get('price'), json.dumps(sizes_array),
                    data.get('color'), data.get('quantity'), data.get('category'),
                    data.get('image_url'), data.get('description'), data.get('status', 'available'),
                    shoe_id
                ))
                return jsonify({"message": "Shoe updated"}), 200
            
            elif request.method == "DELETE":
                cur.execute("DELETE FROM shoes WHERE id=%s;", (shoe_id,))
                return jsonify({"message": "Shoe deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 9. Admin Shoe Status Toggle
@app.route("/admin/shoes/<int:shoe_id>/status", methods=["PUT"])
@require_admin_token
def toggle_shoe_status(shoe_id):
    try:
        data = request.json or {}
        status = data.get('status', 'available')
        
        with db_cursor() as cur:
            cur.execute("UPDATE shoes SET status=%s WHERE id=%s;", (status, shoe_id))
        
        return jsonify({"message": "Status updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Admin Direct Sale Endpoint
@app.route("/admin/shoes/<int:shoe_id>/sell", methods=["POST"])
@require_admin_token
def admin_direct_sale(shoe_id):
    try:
        data = request.json or {}
        quantity = int(data.get('quantity', 1))
        
        if quantity <= 0:
            return jsonify({"success": False, "message": "Quantity must be greater than 0"}), 400
        
        with db_cursor() as cur:
            # Get shoe info
            cur.execute("SELECT * FROM shoes WHERE id=%s;", (shoe_id,))
            shoe = cur.fetchone()
            
            if not shoe:
                return jsonify({"success": False, "message": "Shoe not found"}), 404
            
            if shoe['quantity'] < quantity:
                return jsonify({"success": False, "message": "Insufficient stock"}), 400
            
            # Create order record
            cur.execute("""
                INSERT INTO orders (shoe_id, shoe_title, customer_name, customer_phone, selected_size, delivery_location, quantity, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """, (
                shoe_id, f"{shoe['brand']} {shoe['name']}", 
                data.get('customer_name', 'Direct Shop'), 
                data.get('customer_phone', 'Counter'), 
                data.get('size', 'N/A'),
                data.get('delivery_location', 'Shop'),
                quantity, 'Delivered'
            ))
            order_id = cur.fetchone()['id']
            
            # Decrease stock
            new_quantity = shoe['quantity'] - quantity
            cur.execute("UPDATE shoes SET quantity=%s WHERE id=%s;", (new_quantity, shoe_id))
        
        return jsonify({"success": True, "message": "Sale recorded successfully", "id": order_id}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# 10. Admin Order Management Endpoints
@app.route("/admin/orders/<int:order_id>/deliver", methods=["PUT"])
@require_admin_token
def mark_order_delivered(order_id):
    try:
        with db_cursor() as cur:
            cur.execute("UPDATE orders SET status='Delivered' WHERE id=%s;", (order_id,))
        return jsonify({"message": "Order marked as delivered"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/orders/<int:order_id>", methods=["DELETE"])
@require_admin_token
def delete_order(order_id):
    try:
        with db_cursor() as cur:
            cur.execute("DELETE FROM orders WHERE id=%s;", (order_id,))
        return jsonify({"message": "Order deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
