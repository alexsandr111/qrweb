import os
import random
import sqlite3
import string
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO

import qrcode
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_PATH = os.environ.get("PAYMENTS_DB", "payments.db")
DEFAULT_PURPOSE = "Возврат неиспользованного аванса"
FIXED_REQUISITES = {
    "Name": 'ООО "ЭНЕРДЖИ МЕНЕДЖМЕНТ"',
    "PersonalAcc": "40702810900000057455",
    "BankName": "Банк ГПБ (АО) г. Москва",
    "BIC": "044525823",
    "CorrespAcc": "30101810200000000823",
    "PayeeINN": "9709082458",
    "KPP": "770401001",
}

app = FastAPI(title="Payment QR Generator")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static",
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            payer_name TEXT NOT NULL,
            amount_rub REAL,
            amount_kopecks INTEGER,
            created_at DATETIME,
            qr_string TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT 'Возврат неиспользованного аванса'
        )
        """
    )
    columns = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA table_info(payments)").fetchall()
    }
    if "purpose" not in columns:
        default_purpose_sql = DEFAULT_PURPOSE.replace("'", "''")
        conn.execute(
            f"ALTER TABLE payments ADD COLUMN purpose TEXT NOT NULL DEFAULT '{default_purpose_sql}'"
        )
    conn.commit()
    conn.close()


initialize_db()


@app.get("/")
async def form(request: Request):
    return templates.TemplateResponse(
        "form.html", {"request": request, "errors": [], "values": {}}, status_code=200
    )


def generate_id(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


def sanitize_amount(amount_str: str) -> tuple[Decimal, int]:
    try:
        amount = Decimal(amount_str.replace(",", ".").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Сумма должна быть числом")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    kopecks = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return amount, kopecks


def build_qr_string(payer_name: str, amount_kopecks: int, purpose: str) -> str:
    parts = ["ST00011"]
    for key, value in FIXED_REQUISITES.items():
        parts.append(f"{key}={value}")
    parts.append(f"Purpose={purpose}")
    parts.append(f"LastName={payer_name}")
    parts.append(f"SUM={amount_kopecks}")
    return "|".join(parts)


def insert_payment(
    payer_name: str, amount_rub: Decimal, amount_kopecks: int, purpose: str
) -> str:
    conn = get_connection()
    try:
        payment_id = generate_id()
        while conn.execute("SELECT 1 FROM payments WHERE id = ?", (payment_id,)).fetchone():
            payment_id = generate_id()
        qr_string = build_qr_string(payer_name, amount_kopecks, purpose)
        conn.execute(
            """
            INSERT INTO payments (id, payer_name, amount_rub, amount_kopecks, created_at, qr_string, purpose)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_id,
                payer_name,
                float(amount_rub),
                amount_kopecks,
                datetime.utcnow().isoformat(timespec="seconds"),
                qr_string,
                purpose,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return payment_id


@app.post("/")
async def create_payment(
    request: Request,
    payer_name: str = Form(""),
    amount: str = Form(""),
    purpose: str = Form(DEFAULT_PURPOSE),
):
    errors = []
    values = {"payer_name": payer_name, "amount": amount, "purpose": purpose}

    if not payer_name.strip():
        errors.append("ФИО плательщика обязательно")
    elif len(payer_name) > 150:
        errors.append("ФИО слишком длинное (до 150 символов)")

    cleaned_purpose = purpose.strip()
    if not cleaned_purpose:
        errors.append("Укажите назначение платежа")
    elif len(cleaned_purpose) > 255:
        errors.append("Назначение платежа должно быть до 255 символов")

    try:
        amount_rub, amount_kopecks = sanitize_amount(amount)
    except ValueError as exc:
        errors.append(str(exc))
        amount_rub = amount_kopecks = None

    if errors:
        return templates.TemplateResponse(
            "form.html", {"request": request, "errors": errors, "values": values}, status_code=400
        )

    payment_id = insert_payment(
        payer_name.strip(), amount_rub, amount_kopecks, cleaned_purpose
    )
    return RedirectResponse(url=f"/qr/{payment_id}", status_code=303)


def fetch_payment(payment_id: str):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT
                id,
                payer_name,
                amount_rub,
                amount_kopecks,
                created_at,
                qr_string,
                COALESCE(purpose, ?) as purpose
            FROM payments
            WHERE id = ?
            """,
            (DEFAULT_PURPOSE, payment_id),
        ).fetchone()
    finally:
        conn.close()
    return row


@app.get("/qr/{payment_id}")
async def qr_page(request: Request, payment_id: str):
    payment = fetch_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    short_link = request.url_for("qr_page", payment_id=payment_id)
    return templates.TemplateResponse(
        "qr.html",
        {
            "request": request,
            "payment": payment,
            "share_link": str(short_link),
        },
    )


@app.get("/qr/{payment_id}/image")
async def qr_image(payment_id: str):
    payment = fetch_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    img = qrcode.make(payment["qr_string"], box_size=10, border=4)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/health")
async def health():
    return {"status": "ok"}
