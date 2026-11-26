#!/usr/bin/env python3
import json
import os
import re
import smtplib
import sqlite3
import time
from datetime import datetime
from email.message import EmailMessage
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import dns.resolver  # type: ignore
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DB_PATH = BASE_DIR / "berichten.db"
ENV_PATH = BASE_DIR / ".env"

RATE_LIMIT = {}
MAX_REQUESTS = 5
WINDOW_SECONDS = 600


def laad_env():
    if not ENV_PATH.exists():
        return
    for regel in ENV_PATH.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        k, v = regel.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS berichten (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datum TEXT NOT NULL,
                ip TEXT,
                naam TEXT NOT NULL,
                telefoon TEXT,
                email TEXT NOT NULL,
                onderwerp TEXT,
                bericht TEXT NOT NULL,
                mail_verzonden INTEGER DEFAULT 0
            )
        """)


def _bouw_bericht(data: dict, afzender: str, ontvanger: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Nieuwe offerte/contactaanvraag: {data['onderwerp'] or 'Algemeen'} — {data['naam']}"
    msg["From"] = f"Website Van Ravenswaaij Tuinen <{afzender}>"
    msg["To"] = ontvanger
    msg["Reply-To"] = data["email"]
    msg.set_content(
        f"Naam:      {data['naam']}\n"
        f"Telefoon:  {data['telefoon'] or 'Niet opgegeven'}\n"
        f"E-mail:    {data['email']}\n"
        f"Onderwerp: {data['onderwerp'] or 'Niet gekozen'}\n"
        f"Datum:     {data['datum']}\n\n"
        f"Bericht:\n"
        f"----------------------------------------\n"
        f"{data['bericht']}\n"
        f"----------------------------------------\n"
    )
    return msg


def stuur_email(data: dict) -> bool:
    ontvanger = os.getenv("MAIL_TO", "t.jansen283@proton.me").strip()
    afzender = os.getenv("MAIL_FROM", "website@vanravenswaaijtuinen.nl").strip()
    modus = os.getenv("MAIL_MODE", "direct").strip().lower()
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "25"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()

    msg = _bouw_bericht(data, afzender, ontvanger)

    if modus == "smtp" or (smtp_host and modus != "direct"):
        target_host = smtp_host or "127.0.0.1"
        with smtplib.SMTP(target_host, smtp_port, timeout=15) as server:
            if smtp_port in (587, 465) and server.has_extn("starttls"):
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True

    domein = ontvanger.split("@", 1)[1]
    if HAS_DNSPYTHON:
        mx_records = dns.resolver.resolve(domein, "MX")
        mx_host = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip(".")
        helo_domein = afzender.split("@", 1)[1] if "@" in afzender else "localhost"
        with smtplib.SMTP(mx_host, 25, timeout=15) as server:
            server.ehlo(helo_domein)
            if server.has_extn("starttls"):
                server.starttls()
                server.ehlo(helo_domein)
            server.send_message(msg)
        return True

    with smtplib.SMTP("127.0.0.1", 25, timeout=15) as server:
        server.send_message(msg)
    return True


class TuinenHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def _stuur_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/contact":
            self._stuur_json(404, {"ok": False, "melding": "Endpoint niet gevonden."})
            return

        client_ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
        nu = time.time()
        geschiedenis = [t for t in RATE_LIMIT.get(client_ip, []) if nu - t < WINDOW_SECONDS]
        if len(geschiedenis) >= MAX_REQUESTS:
            self._stuur_json(429, {"ok": False, "melding": "Te veel aanvragen. Probeer het later opnieuw."})
            return
        geschiedenis.append(nu)
        RATE_LIMIT[client_ip] = geschiedenis

        try:
            lengte = int(self.headers.get("Content-Length", "0"))
            if lengte <= 0 or lengte > 20_000:
                self._stuur_json(400, {"ok": False, "melding": "Ongeldige invoergrootte."})
                return
            ruw = self.rfile.read(lengte).decode("utf-8")
            payload = json.loads(ruw)
        except Exception:
            self._stuur_json(400, {"ok": False, "melding": "Ongeldig verzoek."})
            return

        if str(payload.get("website", "")).strip():
            self._stuur_json(200, {"ok": True, "melding": "Bedankt voor uw bericht!"})
            return

        naam = str(payload.get("naam", "")).strip()
        telefoon = str(payload.get("telefoon", "")).strip()
        email = str(payload.get("email", "")).strip()
        onderwerp = str(payload.get("onderwerp", "")).strip()
        bericht = str(payload.get("bericht", "")).strip()

        if len(naam) < 2 or len(bericht) < 5 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            self._stuur_json(422, {"ok": False, "melding": "Vul alstublieft uw naam, een geldig e-mailadres en uw bericht in."})
            return

        record = {
            "datum": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ip": client_ip,
            "naam": naam[:120],
            "telefoon": telefoon[:40],
            "email": email[:120],
            "onderwerp": onderwerp[:80],
            "bericht": bericht[:5000],
        }

        mail_ok = False
        try:
            mail_ok = stuur_email(record)
        except Exception as exc:
            print(f"[FOUT] E-mail verzenden mislukt: {exc}")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO berichten (datum, ip, naam, telefoon, email, onderwerp, bericht, mail_verzonden)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (record["datum"], record["ip"], record["naam"], record["telefoon"],
                 record["email"], record["onderwerp"], record["bericht"], int(mail_ok)),
            )

        self._stuur_json(
            200,
            {"ok": True, "melding": "Bedankt voor uw bericht! We nemen zo spoedig mogelijk contact met u op."},
        )


if __name__ == "__main__":
    laad_env()
    init_db()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), TuinenHandler)
    print(f"Server draait op http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer gestopt.")
