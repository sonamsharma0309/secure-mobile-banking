from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)

    password_hash = db.Column(db.String(255), nullable=False)
    mpin_hash = db.Column(db.String(255), nullable=False)

    card_encrypted = db.Column(db.LargeBinary, nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # relationship
    transactions = db.relationship("Transaction", backref="user", lazy=True, cascade="all, delete-orphan")


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    tx_type = db.Column(db.String(40), nullable=False)     # e.g. UPI, Card, Wallet
    merchant = db.Column(db.String(120), nullable=False)   # e.g. Amazon
    amount = db.Column(db.Integer, nullable=False)         # in INR (demo)
    status = db.Column(db.String(20), nullable=False, default="Success")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), nullable=False, index=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
