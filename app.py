from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
import random
import string
import bcrypt

# AI module (make sure ai.py exists)
from ai import chatbot_response

app = Flask(__name__)
app.secret_key = "rent_a_ride_secret_key"


# ================= DATABASE CONNECTION (FIXED FOR CLOUD) =================
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "dcs@123"),
        database=os.getenv("DB_NAME", "rent_a_ride")
    )


# ================= HOME =================
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM vehicles LIMIT 6")
    vehicles = cursor.fetchall()

    return render_template("index.html", vehicles=vehicles)


# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        db = get_db()
        cursor = db.cursor()

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]
        phone = request.form["phone"]
        address = request.form["address"]

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already exists")
            return redirect(url_for("register"))

        cursor.execute("""
            INSERT INTO users(full_name,email,password,phone,address)
            VALUES(%s,%s,%s,%s,%s)
        """, (full_name, email, hashed, phone, address))

        db.commit()
        flash("Registered Successfully")
        return redirect(url_for("login"))

    return render_template("register.html")


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        db = get_db()
        cursor = db.cursor(dictionary=True)

        email = request.form["email"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode(), user["password"].encode()):

            session["user_id"] = user["user_id"]
            session["user_name"] = user["full_name"]

            return redirect(url_for("home"))

        flash("Invalid credentials")

    return render_template("login.html")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT bookings.*, vehicles.vehicle_name, vehicles.brand
        FROM bookings
        JOIN vehicles ON bookings.vehicle_id = vehicles.vehicle_id
        WHERE bookings.user_id=%s
    """, (session["user_id"],))

    bookings = cursor.fetchall()

    return render_template("dashboard.html", bookings=bookings)


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================= VEHICLES =================
@app.route("/vehicles")
def vehicles():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    search = request.args.get("search")

    if search:
        cursor.execute("SELECT * FROM vehicles WHERE vehicle_name LIKE %s",
                       ('%' + search + '%',))
    else:
        cursor.execute("SELECT * FROM vehicles")

    vehicles = cursor.fetchall()

    return render_template("vehicles.html", vehicles=vehicles)


# ================= BOOK VEHICLE =================
@app.route("/book/<int:vehicle_id>", methods=["GET", "POST"])
def book_vehicle(vehicle_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM vehicles WHERE vehicle_id=%s", (vehicle_id,))
    vehicle = cursor.fetchone()

    if request.method == "POST":

        days = int(request.form["total_days"])
        amount = days * float(vehicle["price_per_day"])

        cursor.execute("""
            INSERT INTO bookings(user_id,vehicle_id,pickup_date,return_date,total_days,total_amount,booking_status)
            VALUES(%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["user_id"],
            vehicle_id,
            request.form["pickup_date"],
            request.form["return_date"],
            days,
            amount,
            "Booked"
        ))

        db.commit()

        booking_id = cursor.lastrowid

        return redirect(url_for("payment", booking_id=booking_id))

    return render_template("booking.html", vehicle=vehicle)


# ================= BOOKINGS PAGE =================
@app.route("/bookings")
def bookings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT bookings.*, vehicles.vehicle_name
        FROM bookings
        JOIN vehicles ON bookings.vehicle_id = vehicles.vehicle_id
        WHERE bookings.user_id=%s
    """, (session["user_id"],))

    bookings = cursor.fetchall()

    return render_template("bookings.html", bookings=bookings)


# ================= CANCEL BOOKING =================
@app.route("/cancel_booking/<int:booking_id>")
def cancel_booking(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cursor = db.cursor()

    # 1. FIRST delete payment record (IMPORTANT)
    cursor.execute(
        "DELETE FROM payments WHERE booking_id=%s",
        (booking_id,)
    )

    # 2. THEN delete booking record
    cursor.execute(
        "DELETE FROM bookings WHERE booking_id=%s",
        (booking_id,)
    )

    db.commit()

    flash("Booking Cancelled Successfully")
    return redirect(url_for("dashboard"))


# ================= CHATBOT =================
@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():

    response = None

    if request.method == "POST":
        response = chatbot_response(request.form["message"])

    return render_template("chatbot.html", response=response)


# ================= PAYMENT =================
@app.route("/payment/<int:booking_id>", methods=["GET", "POST"])
def payment(booking_id):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT bookings.*, vehicles.vehicle_name
        FROM bookings
        JOIN vehicles ON bookings.vehicle_id = vehicles.vehicle_id
        WHERE booking_id=%s
    """, (booking_id,))

    booking = cursor.fetchone()

    if request.method == "POST":

        txn = "TXN" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

        cursor.execute("""
            UPDATE bookings SET payment_status='Paid'
            WHERE booking_id=%s
        """, (booking_id,))

        cursor.execute("""
            INSERT INTO payments(booking_id,payment_method,transaction_id)
            VALUES(%s,%s,%s)
        """, (booking_id, request.form["payment_method"], txn))

        db.commit()

        return redirect(url_for("booking_receipt", booking_id=booking_id))

    return render_template("payment.html", booking=booking)


# ================= RECEIPT =================
@app.route("/receipt/<int:booking_id>")
def booking_receipt(booking_id):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT bookings.*, vehicles.vehicle_name, users.full_name
        FROM bookings
        JOIN vehicles ON bookings.vehicle_id = vehicles.vehicle_id
        JOIN users ON bookings.user_id = users.user_id
        WHERE booking_id=%s
    """, (booking_id,))

    receipt = cursor.fetchone()

    return render_template("receipt.html", receipt=receipt)


# ================= RUN (IMPORTANT FOR CLOUD RUN) =================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)