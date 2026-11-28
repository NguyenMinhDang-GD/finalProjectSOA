import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_URL = os.environ.get("TEST_GATEWAY_URL", "http://localhost:18080")
COMPOSE_PROJECT = os.environ.get("TEST_COMPOSE_PROJECT", "pkb-test")
COMPOSE_FILE = os.environ.get("TEST_COMPOSE_FILE", "docker-compose.test.yml")
INTERNAL_KEY = os.environ.get("TEST_INTERNAL_KEY", "test-only-internal-key-p01")
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def http_req(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    for attempt in range(8):
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 7:
                time.sleep(1.2)
                continue
            raw = err.read().decode("utf-8", errors="replace")
            try:
                return err.code, json.loads(raw)
            except json.JSONDecodeError:
                return err.code, raw
    raise AssertionError(f"Rate-limited on {method} {path}")


def psql(db: str, sql: str) -> str:
    cmd = [
        "docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE,
        "exec", "-T", "postgres-test",
        "psql", "-U", "pkb_test_user", "-d", db, "-tAc", sql,
    ]
    return subprocess.run(cmd, text=True, capture_output=True, check=True).stdout.strip()


def compose_ctl(action: str, service: str) -> None:
    subprocess.run(["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, action, service], check=True)


def wait_until(fn, timeout_s: float = 40.0, interval_s: float = 0.5):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        res = fn()
        if res:
            return res
        time.sleep(interval_s)
    return None


def login(email: str, password: str) -> str:
    sc, body = http_req("POST", "/api/auth/login", {"email": email, "password": password})
    assert sc == 200, f"Login failed: {sc} {body}"
    return body["access_token"]


def run_all() -> int:
    staff_tok = login("staff@pickleball.vn", "Staff@123")
    staff_hdr = {"Authorization": f"Bearer {staff_tok}"}
    email = f"b03v-{uuid.uuid4().hex[:6]}@test.vn"
    sc, reg = http_req("POST", "/api/auth/register", {
        "email": email, "full_name": "B03V User", "phone": "0909555666", "password": "UserPass@123"
    })
    assert sc in (200, 201), reg
    cust_hdr = {"Authorization": f"Bearer {reg['access_token']}"}

    sc, courts = http_req("GET", "/api/courts")
    assert sc == 200 and len(courts) >= 1
    court_a = courts[0]["id"]
    d_target = (datetime.now(VN_TZ) + timedelta(days=20)).strftime("%Y-%m-%d")

    # V01: Unpaid reschedule while payment-service is DOWN -> durable convergence via Outbox/Inbox + stale rev guard
    sc, b1 = http_req("POST", "/api/bookings", {
        "court_id": court_a, "play_date": d_target, "hours": [18],
        "customer_name": "V01 User", "customer_phone": "0909555666", "customer_email": email,
    }, headers=cust_hdr)
    assert sc in (200, 201), b1
    code1 = b1["booking_code"]
    sc, p1 = http_req("POST", "/api/payments/create", {"booking_code": code1}, headers=cust_hdr)
    assert sc in (200, 201), p1

    compose_ctl("stop", "payment-service")
    try:
        sc, r1 = http_req("POST", f"/api/bookings/{code1}/reschedule", {
            "court_id": court_a, "play_date": d_target, "hours": [9], "reason": "V01 payment outage test"
        }, headers=cust_hdr)
        assert sc == 200 and r1["booking_revision"] == 2, f"V01 reschedule failed while payment down: {sc} {r1}"
        new_amt = int(round(float(r1["total_amount"])))
    finally:
        compose_ctl("start", "payment-service")

    def payment_converged():
        row = psql("payment_db", f"SELECT expected_amount || ':' || booking_revision FROM payment_transactions WHERE booking_code='{code1}'")
        return row == f"{new_amt}:2"

    assert wait_until(payment_converged, timeout_s=45.0), "V01 payment_transactions did not durably converge to v2"
    # Verify stale revision sync (v1) from internal network cannot revert v2
    stale_out = subprocess.run(
        [
            "docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE,
            "exec", "-T", "court-booking-service", "python", "-c",
            (
                "import urllib.request, json; "
                f"req = urllib.request.Request('http://payment-service:8003/api/payments/internal/{code1}/sync-revision', "
                "data=json.dumps({'expected_amount': 999999, 'booking_revision': 1}).encode(), "
                f"headers={{'Content-Type': 'application/json', 'X-Internal-Key': '{INTERNAL_KEY}'}}, method='POST'); "
                "print(urllib.request.urlopen(req).read().decode())"
            ),
        ],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    stale_res = json.loads(stale_out)
    assert stale_res.get("updated") is False and stale_res.get("stale") is True, stale_res
    row_after = psql("payment_db", f"SELECT expected_amount || ':' || booking_revision FROM payment_transactions WHERE booking_code='{code1}'")
    assert row_after == f"{new_amt}:2", f"V01 stale sync corrupted payment row: {row_after}"
    print(f"[PASS] V01: Payment revision durably converged across outage ({row_after}) and rejected stale rev-1 sync")

    # V03: Paid reschedule while checkin-qr-service is DOWN -> durable ticket convergence & old QR rejection
    sc, cash_res = http_req("POST", "/api/payments/staff/cash-collect", {
        "booking_code": code1, "amount": new_amt, "idempotency_key": f"V03-CASH-{uuid.uuid4().hex[:6]}"
    }, headers=staff_hdr)
    assert sc == 200 and cash_res["status"] == "SUCCEEDED", cash_res

    t_v2 = wait_until(lambda: (lambda r: r[1] if r[0] == 200 and r[1].get("booking_revision") == 2 else None)(http_req("GET", f"/api/checkin/ticket/{code1}", headers=cust_hdr)), timeout_s=30.0)
    assert t_v2 is not None, "V03 initial v2 ticket not issued"
    old_qr_v2 = t_v2["qr_payload"]

    compose_ctl("stop", "checkin-qr-service")
    try:
        sc, r2 = http_req("POST", f"/api/bookings/{code1}/reschedule", {
            "court_id": court_a, "play_date": d_target, "hours": [10], "reason": "V03 checkin outage test"
        }, headers=cust_hdr)
        assert sc == 200 and r2["booking_revision"] == 3, f"V03 reschedule failed: {sc} {r2}"
    finally:
        compose_ctl("start", "checkin-qr-service")

    t_v3 = wait_until(lambda: (lambda r: r[1] if r[0] == 200 and r[1].get("booking_revision") == 3 else None)(http_req("GET", f"/api/checkin/ticket/{code1}", headers=cust_hdr)), timeout_s=45.0)
    assert t_v3 is not None and ".r3." in t_v3["qr_payload"], f"V03 ticket did not converge to v3: {t_v3}"
    sc_old, _ = http_req("POST", "/api/checkin/scan", {"qr_data": old_qr_v2, "bypass_time_check": True}, headers=staff_hdr)
    assert sc_old == 400, f"V03 old v2 QR must be rejected: {sc_old}"
    sc_new, scan_v3 = http_req("POST", "/api/checkin/scan", {"qr_data": t_v3["qr_payload"], "bypass_time_check": True}, headers=staff_hdr)
    assert sc_new == 200 and scan_v3["valid"] is True, f"V03 new v3 QR must succeed: {sc_new} {scan_v3}"
    print("[PASS] V03: Checkin ticket durably converged across service outage (v2->v3), old QR rejected, new QR admitted")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
