from flask import Flask, render_template, request, redirect, url_for, session, flash
from ai import recommend_vehicle, chatbot_response
from datetime import datetime
import random
import mysql.connector
import bcrypt
import string 
app = Flask(__name__)
app.secret_key = "rent_a_ride_secret_key"


# ================= DATABASE CONNECTION =================

#db = mysql.connector.connect(
 #  password="docker123",
  #  database="rent_a_ride"
#)

#cursor = db.cursor(dictionary=True)
@app.route("/")
def test():
    return "Rent A Ride Cloud Run Working!"


# ================= HOME PAGE =================

@app.route("/")
def home():

    # If user not logged in
    if "user_id" not in session:

        return redirect(url_for("login"))

    # Homepage after login
    cursor.execute("SELECT * FROM vehicles LIMIT 6")

    vehicles = cursor.fetchall()

    return render_template(
        "index.html",
        vehicles=vehicles
    )


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]
        phone = request.form["phone"]
        address = request.form["address"]

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        check_query = "SELECT * FROM users WHERE email=%s"
        cursor.execute(check_query, (email,))

        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already exists")
            return redirect(url_for("register"))

        insert_query = """
        INSERT INTO users(full_name,email,password,phone,address)
        VALUES(%s,%s,%s,%s,%s)
        """

        values = (
            full_name,
            email,
            hashed_password,
            phone,
            address
        )

        cursor.execute(insert_query, values)
        db.commit()

        flash("Registration Successful")
        return redirect(url_for("login"))

    return render_template("register.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        query = "SELECT * FROM users WHERE email=%s"
        cursor.execute(query, (email,))

        user = cursor.fetchone()

        if user:

            stored_password = user["password"]

            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):

                session["user_id"] = user["user_id"]
                session["user_name"] = user["full_name"]

                flash("Login Successful")

                return redirect(url_for("home"))

        flash("Invalid Email or Password")

    return render_template("login.html")


# ================= USER DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    booking_query = """
    SELECT bookings.*, vehicles.vehicle_name, vehicles.brand
    FROM bookings
    JOIN vehicles
    ON bookings.vehicle_id = vehicles.vehicle_id
    WHERE bookings.user_id=%s
    """

    cursor.execute(booking_query, (user_id,))

    bookings = cursor.fetchall()

    return render_template(
        "dashboard.html",
        bookings=bookings,
        user_name=session["user_name"]
    )


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged Out Successfully")

    return redirect(url_for("home"))


# ================= VEHICLES PAGE =================

@app.route("/vehicles")
def vehicles():

    search = request.args.get("search")
    vehicle_type = request.args.get("type")

    query = "SELECT * FROM vehicles WHERE 1=1"

    values = []

    # Search by vehicle name
    if search:

        query += " AND vehicle_name LIKE %s"

        values.append('%' + search + '%')

    # Filter by type
    if vehicle_type and vehicle_type != "All":

        query += " AND vehicle_type=%s"

        values.append(vehicle_type)

    cursor.execute(query, tuple(values))

    vehicles = cursor.fetchall()

    return render_template(
        "vehicles.html",
        vehicles=vehicles
    )


# ================= BOOK VEHICLE =================

# ================= BOOK VEHICLE =================

@app.route("/book/<int:vehicle_id>", methods=["GET", "POST"])
def book_vehicle(vehicle_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    vehicle_query = "SELECT * FROM vehicles WHERE vehicle_id=%s"
    cursor.execute(vehicle_query, (vehicle_id,))

    vehicle = cursor.fetchone()

    if request.method == "POST":

        pickup_date = request.form["pickup_date"]
        return_date = request.form["return_date"]
        total_days = int(request.form["total_days"])

        total_amount = total_days * float(vehicle["price_per_day"])

        insert_query = """
        INSERT INTO bookings(
        user_id,
        vehicle_id,
        pickup_date,
        return_date,
        total_days,
        total_amount,
        booking_status
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s)
        """

        values = (
            session["user_id"],
            vehicle_id,
            pickup_date,
            return_date,
            total_days,
            total_amount,
            "Booked"
        )

        cursor.execute(insert_query, values)
        db.commit()

        # ---------- NEW CODE: Get the generated booking_id ----------
        new_booking_id = cursor.lastrowid 

        update_vehicle = """
        UPDATE vehicles
        SET availability_status='Booked'
        WHERE vehicle_id=%s
        """

        cursor.execute(update_vehicle, (vehicle_id,))
        db.commit()

        flash("Vehicle Booked Successfully. Please complete your payment.")

        # ---------- NEW CODE: Redirect to Payment page ----------
        return redirect(url_for("payment", booking_id=new_booking_id))

    return render_template("booking.html", vehicle=vehicle)

# ================= ADMIN LOGIN =================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        query = "SELECT * FROM admin WHERE username=%s AND password=%s"

        cursor.execute(query, (username, password))

        admin = cursor.fetchone()

        if admin:

            session["admin"] = admin["username"]

            flash("Admin Login Successful")

            return redirect(url_for("admin_dashboard"))

        flash("Invalid Admin Credentials")

    return render_template("admin_login.html")


# ================= ADMIN DASHBOARD =================

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    # Total Users
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()

    # Total Vehicles
    cursor.execute("SELECT COUNT(*) AS total_vehicles FROM vehicles")
    total_vehicles = cursor.fetchone()

    # Total Bookings
    cursor.execute("SELECT COUNT(*) AS total_bookings FROM bookings")
    total_bookings = cursor.fetchone()

    # Revenue
    cursor.execute("SELECT SUM(total_amount) AS revenue FROM bookings")
    revenue = cursor.fetchone()

    # Recent Bookings
    query = """
    SELECT bookings.*, users.full_name, vehicles.vehicle_name
    FROM bookings
    JOIN users
    ON bookings.user_id = users.user_id
    JOIN vehicles
    ON bookings.vehicle_id = vehicles.vehicle_id
    ORDER BY booking_id DESC
    """

    cursor.execute(query)

    bookings = cursor.fetchall()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_vehicles=total_vehicles,
        total_bookings=total_bookings,
        revenue=revenue,
        bookings=bookings
    )


# ================= ADD VEHICLE =================

@app.route("/admin/add_vehicle", methods=["GET", "POST"])
def add_vehicle():

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":

        vehicle_name = request.form["vehicle_name"]
        vehicle_type = request.form["vehicle_type"]
        brand = request.form["brand"]
        model = request.form["model"]
        fuel_type = request.form["fuel_type"]
        transmission = request.form["transmission"]
        seating_capacity = request.form["seating_capacity"]
        price_per_day = request.form["price_per_day"]
        vehicle_number = request.form["vehicle_number"]

        insert_query = """
        INSERT INTO vehicles(
        vehicle_name,
        vehicle_type,
        brand,
        model,
        fuel_type,
        transmission,
        seating_capacity,
        price_per_day,
        vehicle_number
        )
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """

        values = (
            vehicle_name,
            vehicle_type,
            brand,
            model,
            fuel_type,
            transmission,
            seating_capacity,
            price_per_day,
            vehicle_number
        )

        cursor.execute(insert_query, values)
        db.commit()

        flash("Vehicle Added Successfully")

        return redirect(url_for("admin_dashboard"))

    return render_template("add_vehicle.html")


# ================= DELETE VEHICLE =================

@app.route("/admin/delete_vehicle/<int:vehicle_id>")
def delete_vehicle(vehicle_id):

    if "admin" not in session:
        return redirect(url_for("admin_login"))

    delete_query = "DELETE FROM vehicles WHERE vehicle_id=%s"

    cursor.execute(delete_query, (vehicle_id,))
    db.commit()

    flash("Vehicle Deleted Successfully")

    return redirect(url_for("admin_dashboard"))


# ================= BOOKINGS PAGE =================

@app.route("/bookings")
def bookings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    query = """
    SELECT bookings.*, vehicles.vehicle_name
    FROM bookings
    JOIN vehicles
    ON bookings.vehicle_id = vehicles.vehicle_id
    WHERE bookings.user_id=%s
    """

    cursor.execute(query, (user_id,))

    bookings = cursor.fetchall()
    booking_id = cursor.lastrowid

    return redirect(
        url_for(
            "payment",
            booking_id=booking_id
        )
    )

# ================= CANCEL BOOKING =================

@app.route("/cancel_booking/<int:booking_id>")
def cancel_booking(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get vehicle id from booking
    query = "SELECT vehicle_id FROM bookings WHERE booking_id=%s"

    cursor.execute(query, (booking_id,))

    booking = cursor.fetchone()

    if booking:

        vehicle_id = booking["vehicle_id"]

        # Delete booking
        delete_query = "DELETE FROM bookings WHERE booking_id=%s"

        cursor.execute(delete_query, (booking_id,))

        db.commit()

        # Make vehicle available again
        update_query = """
        UPDATE vehicles
        SET availability_status='Available'
        WHERE vehicle_id=%s
        """

        cursor.execute(update_query, (vehicle_id,))

        db.commit()

        flash("Booking Cancelled Successfully")

    return redirect(url_for("dashboard"))

# ================= AI VEHICLE RECOMMENDATION =================

# ================= AI VEHICLE RECOMMENDATION =================

@app.route("/ai_recommend", methods=["GET", "POST"])
def ai_recommend():
    if request.method == "POST":
        # 1. Get user inputs from the form
        budget = float(request.form["budget"])
        passengers = int(request.form["passengers"])
        trip_type = request.form["trip_type"]

        # 2. Query the database based on Budget and Passengers
        # We check if price_per_day is within budget and seating_capacity is enough
        query = """
        SELECT * FROM vehicles 
        WHERE price_per_day <= %s 
        AND seating_capacity >= %s
        ORDER BY price_per_day ASC
        """
        
        cursor.execute(query, (budget, passengers))
        recommended_vehicles = cursor.fetchall()

        # 3. Render your existing vehicle.html page with the matching vehicles
        return render_template(
            "vehicles.html", 
            vehicles=recommended_vehicles
        )

    # 4. If GET request, display the form
    return render_template("ai_recommend.html")
# ================= AI CHATBOT =================

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():

    response = None

    if request.method == "POST":

        user_message = request.form["message"]

        response = chatbot_response(user_message)

    return render_template(
        "chatbot.html",
        response=response
    )


# ================= PAYMENT =================

import string # Add this at the top of your file with the other imports

# ================= PAYMENT =================

@app.route("/payment/<int:booking_id>", methods=["GET", "POST"])
def payment(booking_id):

    # Get booking details
    query = """
    SELECT bookings.*, vehicles.vehicle_name
    FROM bookings
    JOIN vehicles
    ON bookings.vehicle_id = vehicles.vehicle_id
    WHERE booking_id=%s
    """
    cursor.execute(query, (booking_id,))
    booking = cursor.fetchone()

    if request.method == "POST":
        payment_method = request.form["payment_method"]

        # 1. Generate a random Transaction ID (e.g., TXN8F3920A)
        transaction_id = "TXN" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

        # 2. Update payment status in bookings
        update_query = """
        UPDATE bookings
        SET payment_status='Paid'
        WHERE booking_id=%s
        """
        cursor.execute(update_query, (booking_id,))

        # 3. Insert record into payments table
        insert_payment_query = """
        INSERT INTO payments (booking_id, payment_method, transaction_id)
        VALUES (%s, %s, %s)
        """
        cursor.execute(insert_payment_query, (booking_id, payment_method, transaction_id))

        db.commit()

        flash("Payment Successful!")

        # 4. Redirect to the receipt page
        return redirect(url_for("booking_receipt", booking_id=booking_id))

    return render_template(
        "payment.html",
        booking=booking
    )
@app.route('/receipt/<int:booking_id>')
def booking_receipt(booking_id):

    query = '''
    SELECT
    bookings.*,
    vehicles.vehicle_name,
    vehicles.brand,
    users.full_name,
    payments.payment_method,
    payments.transaction_id

    FROM bookings

    JOIN vehicles
    ON bookings.vehicle_id = vehicles.vehicle_id

    JOIN users
    ON bookings.user_id = users.user_id

    JOIN payments
    ON bookings.booking_id = payments.booking_id

    WHERE bookings.booking_id=%s
    '''

    cursor.execute(query, (booking_id,))

    receipt = cursor.fetchone()

    return render_template('receipt.html', receipt=receipt)

# ================= MAIN =================

import os

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8080))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )

