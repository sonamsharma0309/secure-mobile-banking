import re
from datetime import datetime, timedelta
from random import choice, randint

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Transaction, LoginAttempt
from security import load_or_create_secret_key, load_or_create_fernet, make_csrf_token, validate_csrf

def create_app():
    app = Flask(__name__)
    app.secret_key = load_or_create_secret_key()

    # session hardening (dev-friendly)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # If you run HTTPS, you can set True
    app.config["SESSION_COOKIE_SECURE"] = False

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///banking.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    fernet = load_or_create_fernet()

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    # ---------- validators ----------
    def is_valid_email(email: str) -> bool:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))

    def is_strong_password(pw: str) -> bool:
        # min 8, 1 upper, 1 lower, 1 digit, 1 special
        if not pw or len(pw) < 8:
            return False
        rules = [r"[A-Z]", r"[a-z]", r"\d", r"[^\w\s]"]
        return all(re.search(rule, pw) for rule in rules)

    def is_16_digit_card(card: str) -> bool:
        return bool(re.fullmatch(r"\d{16}", card or ""))

    def is_4_digit_mpin(mpin: str) -> bool:
        return bool(re.fullmatch(r"\d{4}", mpin or ""))

    def mask_card(last4: str) -> str:
        return f"•••• •••• •••• {last4}"

    def client_ip() -> str:
        # best-effort (works locally too)
        return request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"

    # ---------- login lockout logic ----------
    LOCK_WINDOW_MIN = 10
    MAX_FAILS = 5
    LOCK_MINUTES = 10

    def is_locked(email: str) -> tuple[bool, str]:
        """Return (locked, msg)."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=LOCK_WINDOW_MIN)

        fails = LoginAttempt.query.filter(
            LoginAttempt.email == email,
            LoginAttempt.success == False,
            LoginAttempt.created_at >= window_start
        ).count()

        if fails >= MAX_FAILS:
            # lock until last fail + LOCK_MINUTES
            last_fail = LoginAttempt.query.filter(
                LoginAttempt.email == email,
                LoginAttempt.success == False
            ).order_by(LoginAttempt.created_at.desc()).first()

            if last_fail:
                unlock_at = last_fail.created_at + timedelta(minutes=LOCK_MINUTES)
                if now < unlock_at:
                    remaining = int((unlock_at - now).total_seconds() // 60) + 1
                    return True, f"Too many failed attempts. Try again in ~{remaining} minute(s)."
        return False, ""

    def seed_demo_transactions(user_id: int):
        if Transaction.query.filter_by(user_id=user_id).count() > 0:
            return

        merchants = ["Amazon", "Flipkart", "Swiggy", "Zomato", "Uber", "Netflix", "Airtel", "Jio", "IRCTC", "BookMyShow"]
        types = ["UPI Transfer", "Card Payment", "Wallet Top-up"]
        for _ in range(12):
            tx = Transaction(
                user_id=user_id,
                tx_type=choice(types),
                merchant=choice(merchants),
                amount=randint(120, 4999),
                status=choice(["Success", "Success", "Success", "Pending"])  # mostly success
            )
            db.session.add(tx)
        db.session.commit()

    # ---------- routes ----------
    @app.get("/")
    def index():
        csrf = make_csrf_token(session)
        return render_template("index.html", csrf=csrf)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            csrf = make_csrf_token(session)
            return render_template("register.html", csrf=csrf)

        if not validate_csrf(session, request.form.get("csrf")):
            flash("Security check failed (CSRF). Please try again.", "danger")
            return redirect(url_for("register"))

        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        mpin = request.form.get("mpin") or ""
        card_number = (request.form.get("card_number") or "").strip().replace(" ", "")

        errors = []
        if len(full_name) < 2:
            errors.append("Full name must be at least 2 characters.")
        if not is_valid_email(email):
            errors.append("Enter a valid email address.")
        if not is_strong_password(password):
            errors.append("Password must be 8+ chars with Uppercase, Lowercase, Digit & Special character.")
        if not is_4_digit_mpin(mpin):
            errors.append("M-PIN must be exactly 4 digits.")
        if not is_16_digit_card(card_number):
            errors.append("Card number must be exactly 16 digits (numbers only).")

        if User.query.filter_by(email=email).first():
            errors.append("Email already registered. Please login.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password, method="scrypt")
        mpin_hash = generate_password_hash(mpin, method="scrypt")

        card_cipher = fernet.encrypt(card_number.encode("utf-8"))
        last4 = card_number[-4:]

        user = User(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            mpin_hash=mpin_hash,
            card_encrypted=card_cipher,
            card_last4=last4
        )
        db.session.add(user)
        db.session.commit()

        flash("✅ Account created with full privacy. Please login.", "success")
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            csrf = make_csrf_token(session)
            return render_template("login.html", csrf=csrf)

        if not validate_csrf(session, request.form.get("csrf")):
            flash("Security check failed (CSRF). Please try again.", "danger")
            return redirect(url_for("login"))

        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        mpin = request.form.get("mpin") or ""

        locked, msg = is_locked(email)
        if locked:
            flash(msg, "danger")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if not user:
            db.session.add(LoginAttempt(email=email, success=False, ip=client_ip()))
            db.session.commit()
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login"))

        if not check_password_hash(user.password_hash, password):
            db.session.add(LoginAttempt(email=email, success=False, ip=client_ip()))
            db.session.commit()
            flash("Invalid credentials.", "danger")
            return redirect(url_for("login"))

        if not check_password_hash(user.mpin_hash, mpin):
            db.session.add(LoginAttempt(email=email, success=False, ip=client_ip()))
            db.session.commit()
            flash("Invalid credentials (M-PIN).", "danger")
            return redirect(url_for("login"))

        db.session.add(LoginAttempt(email=email, success=True, ip=client_ip()))
        db.session.commit()

        login_user(user)
        seed_demo_transactions(user.id)

        flash("✅ Logged in successfully.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        csrf = make_csrf_token(session)
        card_masked = mask_card(current_user.card_last4)

        # Demo balance derived from transactions (for dynamic feeling)
        txs = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).limit(10).all()
        total_spend = sum(t.amount for t in txs if t.status == "Success")
        balance = max(58240 - total_spend, 1200)

        return render_template(
            "dashboard.html",
            csrf=csrf,
            card_masked=card_masked,
            balance=balance
        )

    # Dynamic API endpoint
    @app.get("/api/transactions")
    @login_required
    def api_transactions():
        txs = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).limit(12).all()
        data = []
        for t in txs:
            data.append({
                "tx_type": t.tx_type,
                "merchant": t.merchant,
                "amount": t.amount,
                "status": t.status,
                "time": t.created_at.strftime("%d %b %Y, %I:%M %p")
            })
        return jsonify({"items": data})

    @app.post("/logout")
    @login_required
    def logout():
        if not validate_csrf(session, request.form.get("csrf")):
            flash("Security check failed (CSRF).", "danger")
            return redirect(url_for("dashboard"))

        logout_user()
        flash("Logged out safely.", "info")
        return redirect(url_for("index"))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
