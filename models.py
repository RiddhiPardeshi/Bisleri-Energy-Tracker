from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class DailyEntry(db.Model):
    __tablename__ = "daily_entries"

    id = db.Column(db.Integer, primary_key=True)

    # -------------------------
    # Basic Information
    # -------------------------
    date = db.Column(db.Date, nullable=False)
    batch_no = db.Column(db.String(20))

    # -------------------------
    # Generation Meter
    # -------------------------
    generation_opening = db.Column(db.Float)
    generation_closing = db.Column(db.Float)
    generation_total = db.Column(db.Float)

    # -------------------------
    # Import Meter
    # -------------------------
    import_opening = db.Column(db.Float)
    import_closing = db.Column(db.Float)
    import_total = db.Column(db.Float)

    # -------------------------
    # Export Meter
    # -------------------------
    export_opening = db.Column(db.Float)
    export_closing = db.Column(db.Float)
    export_total = db.Column(db.Float)

    # -------------------------
    # Consumption
    # -------------------------
    consumption = db.Column(db.Float)

    # -------------------------
    # Production
    # -------------------------
    production = db.Column(db.Integer)
    production_type = db.Column(db.String(50))
    boxes = db.Column(db.Integer)

    # -------------------------
    # Detailed Loss Inputs (UNITS)
    # -------------------------

    # Blowing
    blowing_preform = db.Column(db.Integer, default=0)

    # Filling
    filling_preform = db.Column(db.Integer, default=0)
    filling_cap = db.Column(db.Integer, default=0)

    # Labeling
    labeling_bottle = db.Column(db.Integer, default=0)
    labeling_cap = db.Column(db.Integer, default=0)
    labeling_sticker = db.Column(db.Integer, default=0)

    # Shrink
    shrink_paper = db.Column(db.Integer, default=0)
    shrink_bottle = db.Column(db.Integer, default=0)
    shrink_cap = db.Column(db.Integer, default=0)
    shrink_sticker = db.Column(db.Integer, default=0)

    # -------------------------
    # Detailed Loss Inputs (RUPEES - manually entered by operator)
    # -------------------------

    # Blowing
    blowing_preform_rs = db.Column(db.Float, default=0)

    # Filling
    filling_preform_rs = db.Column(db.Float, default=0)
    filling_cap_rs = db.Column(db.Float, default=0)

    # Labeling
    labeling_bottle_rs = db.Column(db.Float, default=0)
    labeling_cap_rs = db.Column(db.Float, default=0)
    labeling_sticker_rs = db.Column(db.Float, default=0)

    # Shrink
    shrink_paper_rs = db.Column(db.Float, default=0)
    shrink_bottle_rs = db.Column(db.Float, default=0)
    shrink_cap_rs = db.Column(db.Float, default=0)
    shrink_sticker_rs = db.Column(db.Float, default=0)

    # -------------------------
    # Totals (Auto-calculated, no rate multiplication)
    # -------------------------
    total_loss_units = db.Column(db.Integer)
    total_loss_rs = db.Column(db.Float)


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)

    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200))
    amount = db.Column(db.Float)
    payment_mode = db.Column(db.String(20))

# -----------------------------
# Stock Inventory
# -----------------------------
class Stock(db.Model):
    __tablename__ = "stock"

    id = db.Column(db.Integer, primary_key=True)

    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))

    opening_stock = db.Column(db.Integer, default=0)
    stock_in = db.Column(db.Integer, default=0)
    stock_out = db.Column(db.Integer, default=0)
    closing_stock = db.Column(db.Integer, default=0)

    unit = db.Column(db.String(20))

    last_updated = db.Column(
        db.Date,
        nullable=False,
        default=db.func.current_date()
    )


# -----------------------------
# Admin Login
# -----------------------------
class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)