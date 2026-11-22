"""Two-step verification: a 6-digit email code at sign-up and at every sign-in (teacher feedback)."""
import pytest

from app import create_app
from app.api import auth as auth_module
from app.config import TestConfig
from app.extensions import db
from app.services import otp
from app.services.index import clear_cache

PASSWORD = "Passw0rd!"
EMAIL = "alex@example.com"


@pytest.fixture
def client(tmp_path):
    app = create_app(TestConfig, LOCAL_STORAGE_DIR=str(tmp_path / "uploads"), TWO_FACTOR_ENABLED=True)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()
    clear_cache()
    otp.clear()
    auth_module._failures.clear()


def start_register(client):
    return client.post("/api/auth/register", json={"name": "Alex Chen", "email": EMAIL, "password": PASSWORD})


def register_and_verify(client):
    code = start_register(client).get_json()["demo_code"]
    return client.post("/api/auth/register/verify", json={"email": EMAIL, "code": code})


def test_register_sends_a_code_and_creates_the_account_only_after_verification(client):
    res = start_register(client)
    assert res.status_code == 202
    body = res.get_json()
    assert body["verification_required"] is True and body["purpose"] == "register"
    assert len(body["demo_code"]) == 6  # demo mode: no email server in tests
    assert body["sent_to"] == "al**@example.com"

    # Not created yet, so signing in fails
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 401

    res = client.post("/api/auth/register/verify", json={"email": EMAIL, "code": body["demo_code"]})
    assert res.status_code == 201
    assert res.get_json()["access_token"]  # signed straight in
    assert res.get_json()["user"]["email"] == EMAIL


def test_login_needs_the_emailed_code(client):
    register_and_verify(client)
    res = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert res.status_code == 202 and "access_token" not in res.get_json()
    code = res.get_json()["demo_code"]

    wrong = "000000" if code != "000000" else "111111"
    bad = client.post("/api/auth/login/verify", json={"email": EMAIL, "code": wrong})
    assert bad.status_code == 400 and bad.get_json()["error"]["code"] == "WRONG_CODE"

    ok = client.post("/api/auth/login/verify", json={"email": EMAIL, "code": code})
    assert ok.status_code == 200
    token = ok.get_json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    # A code works only once
    assert client.post("/api/auth/login/verify", json={"email": EMAIL, "code": code}).status_code == 400


def test_wrong_password_never_sends_a_code(client):
    register_and_verify(client)
    res = client.post("/api/auth/login", json={"email": EMAIL, "password": "Wrong123!"})
    assert res.status_code == 401
    assert client.post("/api/auth/resend-code", json={"email": EMAIL, "purpose": "login"}).status_code == 400


def test_code_stops_working_after_too_many_wrong_tries(client):
    register_and_verify(client)
    code = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).get_json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    statuses = [client.post("/api/auth/login/verify", json={"email": EMAIL, "code": wrong}).status_code
                for _ in range(5)]
    assert statuses[-1] == 429
    # even the right code is now refused: the user must sign in again
    assert client.post("/api/auth/login/verify", json={"email": EMAIL, "code": code}).status_code in (400, 429)


def test_resend_code_replaces_the_old_one(client):
    register_and_verify(client)
    first = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).get_json()["demo_code"]
    second = client.post("/api/auth/resend-code", json={"email": EMAIL, "purpose": "login"}).get_json()["demo_code"]
    if first != second:
        assert client.post("/api/auth/login/verify", json={"email": EMAIL, "code": first}).status_code == 400
    assert client.post("/api/auth/login/verify", json={"email": EMAIL, "code": second}).status_code == 200


def test_expired_code_is_refused(client, monkeypatch):
    register_and_verify(client)
    code = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).get_json()["demo_code"]
    real_time = otp.time.time
    monkeypatch.setattr(otp.time, "time", lambda: real_time() + 11 * 60)
    res = client.post("/api/auth/login/verify", json={"email": EMAIL, "code": code})
    assert res.get_json()["error"]["code"] == "CODE_EXPIRED"


def test_health_reports_two_factor_settings(client):
    data = client.get("/api/health").get_json()
    assert data["two_factor_enabled"] is True and data["email_configured"] is False


# ---------------------------------------------------------------- real email sending (SMTP is faked)
class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.ssl, self.steps = host, port, context is not None, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.steps.append("starttls")

    def login(self, username, password):
        self.steps.append(f"login:{username}")

    def send_message(self, message):
        FakeSMTP.sent.append((self, message))


@pytest.fixture
def fake_smtp(monkeypatch):
    from app.services import mailer

    FakeSMTP.sent = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


@pytest.mark.parametrize("use_ssl, steps", [(True, ["login:me@example.com"]),
                                            (False, ["starttls", "login:me@example.com"])])
def test_code_is_emailed_over_ssl_or_starttls(client, fake_smtp, use_ssl, steps):
    client.application.config.update(SMTP_HOST="smtp.example.com", SMTP_PORT=465 if use_ssl else 587,
                                     SMTP_USE_SSL=use_ssl, SMTP_USE_TLS=True, SMTP_USERNAME="me@example.com",
                                     SMTP_PASSWORD="secret", MAIL_FROM="FileAI <me@example.com>")
    body = start_register(client).get_json()
    assert "demo_code" not in body  # a real email was sent, so the code is not shown on screen
    (smtp, message), = fake_smtp.sent
    assert (smtp.host, smtp.ssl, smtp.steps) == ("smtp.example.com", use_ssl, steps)
    assert message["To"] == EMAIL and message["From"] == "FileAI <me@example.com>"
    assert message["Message-ID"].endswith("@example.com>")
    code = next(word for word in message.get_content().split() if word.isdigit() and len(word) == 6)
    res = client.post("/api/auth/register/verify", json={"email": EMAIL, "code": code})
    assert res.status_code == 201


def test_email_failure_is_reported_to_the_user(client, monkeypatch):
    from app.services import mailer

    def broken(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", broken)
    client.application.config.update(SMTP_HOST="smtp.example.com", SMTP_PORT=465, SMTP_USE_SSL=True)
    res = start_register(client)
    assert res.status_code == 502 and res.get_json()["error"]["code"] == "EMAIL_FAILED"



def test_without_an_email_server_or_demo_mode_the_code_is_never_shown(client, fake_smtp):
    """EMAIL_DEMO_MODE=false (a real server): no email server means an error, never a code on screen."""
    client.application.config.update(SMTP_HOST="", EMAIL_DEMO_MODE=False)
    res = start_register(client)
    assert res.status_code == 503 and res.get_json()["error"]["code"] == "EMAIL_NOT_SET_UP"
    assert "demo_code" not in res.get_json() and fake_smtp.sent == []


def test_demo_mode_never_shows_the_code_once_email_is_set_up(client, fake_smtp):
    client.application.config.update(SMTP_HOST="smtp.example.com", SMTP_PORT=465, SMTP_USE_SSL=True,
                                     EMAIL_DEMO_MODE=True)
    assert "demo_code" not in start_register(client).get_json()
    assert len(fake_smtp.sent) == 1
