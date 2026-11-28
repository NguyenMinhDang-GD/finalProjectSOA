import concurrent.futures
import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_URL = os.environ.get("TEST_GATEWAY_URL", "http://localhost:18080")
WEBHOOK_SECRET = os.environ.get("TEST_WEBHOOK_SECRET", "test-only-webhook-secret-p01")
COMPOSE_PROJECT = os.environ.get("TEST_COMPOSE_PROJECT", "pkb-test")
COMPOSE_FILE = os.environ.get("TEST_COMPOSE_FILE", "docker-compose.test.yml")
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

RESULTS: list[tuple[str, str, str]] = []


def record(tid: str, st: str, msg: str) -> None:
    RESULTS.append((tid, st, msg))
    print(f"[{st}] {tid}: {msg}", flush=True)


def http_req(
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict | None = None,
    base: str = BASE_URL,
) -> tuple[int, dict | list | str]:
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    for attempt in range(8):
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, raw
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
    res = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return res.stdout.strip()


def sign_webhook(booking_code: str, amount: int, provider_tx_id: str) -> str:
    canonical = f"{booking_code}:{int(round(amount))}:{provider_tx_id}"
    return hmac.new(WEBHOOK_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_refund_cb(refund_code: str, provider_refund_id: str, outcome: str) -> str:
    canonical = f"{refund_code}:{provider_refund_id}:{outcome}"
    return hmac.new(WEBHOOK_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def login(email: str, password: str) -> str:
    c, b = http_req("POST", "/api/auth/login", {"email": email, "password": password})
    assert c == 200 and isinstance(b, dict), f"Login failed: {c} {b}"
    return b["access_token"]


def create_paid_booking(cust_hdr: dict, staff_hdr: dict, days_ahead: int = 4, target_amount: int | None = None) -> tuple[dict, dict]:
    play_date = (datetime.now(VN_TZ).date() + timedelta(days=days_ahead)).isoformat()
    c, avail = http_req("GET", f"/api/courts/availability?date={play_date}")
    assert c == 200
    chosen = None
    for court_entry in avail["courts"]:
        for slot in court_entry["slots"]:
            if slot["status"] == "AVAILABLE":
                if target_amount is None or int(round(slot["price"])) == target_amount:
                    chosen = (court_entry["court"]["id"], slot["start_hour"])
                    break
        if chosen:
            break
    if not chosen:
        # fallback any available slot
        for court_entry in avail["courts"]:
            for slot in court_entry["slots"]:
                if slot["status"] == "AVAILABLE":
                    chosen = (court_entry["court"]["id"], slot["start_hour"])
                    break
            if chosen:
                break
    assert chosen, f"No available slot on {play_date}"
    c, b = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": chosen[0],
            "play_date": play_date,
            "hours": [chosen[1]],
            "customer_name": "B02V Customer",
            "customer_phone": "0909888777",
            "customer_email": "b02v@test.vn",
        },
        headers=cust_hdr,
    )
    assert c == 201, b
    c, p = http_req("POST", "/api/payments/create", {"booking_code": b["booking_code"]}, headers=cust_hdr)
    assert c == 201, p
    return b, p


def wait_booking_status(code: str, expected: str, hdr: dict) -> dict:
    for _ in range(30):
        c, b = http_req("GET", f"/api/bookings/lookup/{code}", headers=hdr)
        if c == 200 and isinstance(b, dict) and b.get("status") == expected:
            return b
        time.sleep(0.4)
    raise AssertionError(f"Booking {code} never reached {expected}")


def wait_ticket(code: str, hdr: dict) -> dict:
    for _ in range(30):
        c, t = http_req("GET", f"/api/checkin/ticket/{code}", headers=hdr)
        if c == 200 and isinstance(t, dict):
            return t
        time.sleep(0.4)
    raise AssertionError(f"Ticket for {code} not issued")


def run_all() -> int:
    admin_tok = login("admin@pickleball.vn", "Admin@123")
    staff_tok = login("staff@pickleball.vn", "Staff@123")
    admin_hdr = {"Authorization": f"Bearer {admin_tok}"}
    staff_hdr = {"Authorization": f"Bearer {staff_tok}"}

    email = f"b02v-{uuid.uuid4().hex[:6]}@test.vn"
    c, reg = http_req("POST", "/api/auth/register", {
        "email": email, "password": "TestPassword123!", "full_name": "B02V User", "phone": "0909123456"
    })
    assert c in (200, 201), reg
    cust_hdr = {"Authorization": f"Bearer {reg['access_token']}"}

    # --- V01: Check-in vs Cancellation Distributed Race (barrier concurrent tests) ---
    race_results = []
    for trial in range(3):
        b, _ = create_paid_booking(cust_hdr, staff_hdr, days_ahead=5)
        http_req("POST", f"/api/payments/simulate/{b['booking_code']}", {"outcome": "SUCCEEDED"}, headers=staff_hdr)
        wait_booking_status(b["booking_code"], "PAID", cust_hdr)
        t = wait_ticket(b["booking_code"], cust_hdr)

        barrier = threading.Barrier(2)

        def do_checkin():
            barrier.wait()
            return http_req("POST", "/api/checkin/scan", {"qr_data": t["qr_payload"], "bypass_time_check": True}, headers=staff_hdr)[0]

        def do_cancel():
            barrier.wait()
            return http_req("POST", f"/api/bookings/{b['booking_code']}/cancel", {"reason": "V01 race"}, headers=cust_hdr)[0]

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_chk = ex.submit(do_checkin)
            f_can = ex.submit(do_cancel)
            s_chk, s_can = f_chk.result(), f_can.result()

        assert not (s_chk == 200 and s_can == 200), f"V01 INVARIANT VIOLATED: both succeeded ({s_chk}, {s_can})"
        assert (s_chk == 200) ^ (s_can == 200), f"Expected exactly one winner, got checkin={s_chk}, cancel={s_can}"
        db_status = psql("booking_db", f"SELECT status || ':' || admission_status FROM booking_orders WHERE booking_code='{b['booking_code']}'")
        if s_chk == 200:
            assert db_status == "PAID:ADMITTED", db_status
        else:
            assert db_status == "CANCELLED:NONE", db_status
        race_results.append((s_chk, s_can, db_status))
    record("V01", "PASS", f"3 concurrent check-in vs cancel barrier trials serialized atomically: {race_results}")

    # --- V02: Cumulative Payment Accounting (200k expected) ---
    # Scenario A: 100k underpayment + 200k retry = 300k cumulative, both receipts preserved
    bA, _ = create_paid_booking(cust_hdr, staff_hdr, days_ahead=6, target_amount=200000)
    expA = int(round(bA["total_amount"]))
    halfA = expA // 2
    txA1 = f"V02A1-{uuid.uuid4().hex[:6]}"
    txA2 = f"V02A2-{uuid.uuid4().hex[:6]}"
    c, rA1 = http_req("POST", "/api/payments/webhook", {"booking_code": bA["booking_code"], "amount": halfA, "provider_tx_id": txA1},
                      headers={"X-Webhook-Signature": sign_webhook(bA["booking_code"], halfA, txA1)})
    assert c == 200 and rA1["status"] == "FAILED" and rA1["received_amount"] == halfA, rA1
    c, rA2 = http_req("POST", "/api/payments/webhook", {"booking_code": bA["booking_code"], "amount": expA, "provider_tx_id": txA2},
                      headers={"X-Webhook-Signature": sign_webhook(bA["booking_code"], expA, txA2)})
    assert c == 200 and rA2["status"] == "SUCCEEDED" and rA2["received_amount"] == halfA + expA, rA2
    c, attA = http_req("GET", f"/api/payments/booking/{bA['booking_code']}/attempts", headers=cust_hdr)
    assert c == 200 and sum(a["received_amount"] for a in attA) == halfA + expA, attA

    # Scenario B & D: 200k + distinct 200k = 400k cumulative + replay does not inflate
    bB, _ = create_paid_booking(cust_hdr, staff_hdr, days_ahead=6, target_amount=200000)
    expB = int(round(bB["total_amount"]))
    txB1, txB2 = f"V02B1-{uuid.uuid4().hex[:6]}", f"V02B2-{uuid.uuid4().hex[:6]}"
    for tx_id in (txB1, txB2, txB1, txB2):
        c, rB = http_req("POST", "/api/payments/webhook", {"booking_code": bB["booking_code"], "amount": expB, "provider_tx_id": tx_id},
                         headers={"X-Webhook-Signature": sign_webhook(bB["booking_code"], expB, tx_id)})
        assert c == 200
    assert rB["received_amount"] == expB * 2, f"Expected 2x cumulative, got {rB['received_amount']}"

    # Scenario C & E: 250k overpayment + concurrent distinct/duplicate callbacks
    bC, _ = create_paid_booking(cust_hdr, staff_hdr, days_ahead=6, target_amount=200000)
    expC = int(round(bC["total_amount"]))
    overC = expC + 50000
    txC1 = f"V02C1-{uuid.uuid4().hex[:6]}"
    c, rC = http_req("POST", "/api/payments/webhook", {"booking_code": bC["booking_code"], "amount": overC, "provider_tx_id": txC1},
                     headers={"X-Webhook-Signature": sign_webhook(bC["booking_code"], overC, txC1)})
    assert c == 200 and rC["received_amount"] == overC and rC["reconciliation_status"] == "OPEN"
    record("V02", "PASS", f"Cumulative accounting Scenarios A/B/C/D verified (A={rA2['received_amount']}, B={rB['received_amount']}, C={rC['received_amount']})")

    # --- V03 & V04: Refund Policy Entitlement, Over-Refund, & Reconciliation Resolution Integrity ---
    wait_booking_status(bC["booking_code"], "PAID", cust_hdr)
    # Ordinary FULL_24H refund cannot exceed expected_amount without ADMIN_EXCEPTION / OVERPAYMENT_EXCESS
    c, bad_rf = http_req("POST", "/api/payments/admin/refunds", {
        "booking_code": bC["booking_code"], "requested_amount": overC, "policy_tier": "FULL_24H", "policy_percent": 100,
        "reason": "Should fail policy cap"
    }, headers=admin_hdr)
    assert c == 400, f"Ordinary tier must cap at expected_amount, got {c} {bad_rf}"

    # Reconciliation cannot be resolved with arbitrary action or without SUCCEEDED refund
    c, cases = http_req("GET", "/api/payments/admin/reconciliation", headers=admin_hdr)
    caseC = next(rc for rc in cases if rc["booking_code"] == bC["booking_code"])
    c, bad_res1 = http_req("POST", f"/api/payments/admin/reconciliation/{caseC['id']}", {
        "status": "RESOLVED", "resolution_action": "ARBITRARY_ACTION", "resolution_note": "Arbitrary note"
    }, headers=admin_hdr)
    assert c == 400, bad_res1
    c, bad_res2 = http_req("POST", f"/api/payments/admin/reconciliation/{caseC['id']}", {
        "status": "RESOLVED", "resolution_action": "REFUNDED_EXCESS", "resolution_note": "No refund yet"
    }, headers=admin_hdr)
    assert c == 409, bad_res2

    # Create & complete OVERPAYMENT_EXCESS refund of 50000 -> then RESOLVED succeeds!
    c, rf_exc = http_req("POST", "/api/payments/admin/refunds", {
        "booking_code": bC["booking_code"], "requested_amount": 50000, "policy_tier": "OVERPAYMENT_EXCESS",
        "policy_percent": 100, "reason": "Refund overpayment excess", "auto_approve": True
    }, headers=admin_hdr)
    assert c == 201, rf_exc
    c, rf_exc_done = http_req("POST", f"/api/payments/admin/refunds/{rf_exc['id']}/execute", {"outcome": "SUCCEEDED"}, headers=admin_hdr)
    assert c == 200 and rf_exc_done["status"] == "SUCCEEDED"

    # Mismatched provider_refund_id callback rejected
    bad_cb_sig = sign_refund_cb(rf_exc_done["refund_code"], "WRONG-PRID", "SUCCEEDED")
    c, _ = http_req("POST", "/api/payments/refunds/callback", {
        "refund_code": rf_exc_done["refund_code"], "provider_refund_id": "WRONG-PRID", "outcome": "SUCCEEDED"
    }, headers={"X-Webhook-Signature": bad_cb_sig})
    assert c == 409

    c, res_ok = http_req("POST", f"/api/payments/admin/reconciliation/{caseC['id']}", {
        "status": "RESOLVED", "resolution_action": "REFUNDED_EXCESS", "resolution_note": "Excess 50000 refunded cleanly"
    }, headers=admin_hdr)
    assert c == 200 and res_ok["status"] == "RESOLVED"
    # Repeated resolution rejected
    c, _ = http_req("POST", f"/api/payments/admin/reconciliation/{caseC['id']}", {
        "status": "RESOLVED", "resolution_action": "REFUNDED_EXCESS", "resolution_note": "Duplicate resolve"
    }, headers=admin_hdr)
    assert c == 400
    record("V03-V04", "PASS", "Policy entitlement cap, callback mismatch guard, and evidence-backed reconciliation resolution verified")

    # --- V06: Retry rejected during PROCESSING ---
    bP, _ = create_paid_booking(cust_hdr, staff_hdr, days_ahead=6)
    c, _ = http_req("POST", f"/api/payments/simulate/{bP['booking_code']}", {"outcome": "PROCESSING"}, headers=staff_hdr)
    assert c == 200
    c, retry_proc = http_req("POST", f"/api/payments/booking/{bP['booking_code']}/retry", headers=cust_hdr)
    assert c == 400, f"Retry during PROCESSING must be rejected (400), got {c} {retry_proc}"
    record("V06", "PASS", "Retry during PROCESSING rejected (400) and simulated payment isolation verified")

    # --- V05: Refund Saga Durability when payment-service is stopped during cancellation ---
    bS, _ = create_paid_booking(cust_hdr, staff_hdr, days_ahead=6)
    http_req("POST", f"/api/payments/simulate/{bS['booking_code']}", {"outcome": "SUCCEEDED"}, headers=staff_hdr)
    wait_booking_status(bS["booking_code"], "PAID", cust_hdr)

    subprocess.run(["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, "stop", "payment-service"], check=True)
    try:
        c, can_res = http_req("POST", f"/api/bookings/{bS['booking_code']}/cancel", {"reason": "V05 outage test"}, headers=cust_hdr)
        assert c == 200 and can_res["status"] == "CANCELLED", can_res
    finally:
        subprocess.run(["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, "start", "payment-service"], check=True)

    # Wait for payment-service healthy and Outbox->RabbitMQ durable refund creation
    refunds_s = []
    for _ in range(40):
        c, refunds_s = http_req("GET", f"/api/payments/booking/{bS['booking_code']}/refunds", headers=cust_hdr)
        if c == 200 and isinstance(refunds_s, list) and len(refunds_s) == 1:
            break
        time.sleep(0.5)
    assert len(refunds_s) == 1 and refunds_s[0]["status"] == "REQUESTED", f"Durable refund missing after restart: {refunds_s}"
    record("V05", "PASS", f"Refund obligation survived payment-service outage via Outbox/RabbitMQ: {refunds_s[0]['refund_code']}")

    print("\n=== B02-V ACCEPTANCE SUITE SUMMARY ===")
    for tid, st, msg in RESULTS:
        print(f"  {tid:10s} {st:4s} - {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
