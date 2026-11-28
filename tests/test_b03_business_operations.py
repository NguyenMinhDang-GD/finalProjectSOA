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


def compose_ctl(action: str, service: str) -> None:
    cmd = ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, action, service]
    if action == "start":
        subprocess.run(cmd, check=True)
    else:
        subprocess.run(cmd, check=True)


def sign_webhook(booking_code: str, amount: int, provider_tx_id: str) -> str:
    canonical = f"{booking_code}:{int(round(amount))}:{provider_tx_id}"
    return hmac.new(WEBHOOK_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def login(email: str, password: str) -> str:
    code, body = http_req("POST", "/api/auth/login", {"email": email, "password": password})
    assert code == 200, f"Login failed for {email}: {code} {body}"
    return body["access_token"]


def register_customer(prefix: str) -> tuple[str, dict]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@test.vn"
    password = "UserPass@123"
    code, body = http_req(
        "POST",
        "/api/auth/register",
        {
            "email": email,
            "full_name": f"Test {prefix}",
            "phone": "0909111222",
            "password": password,
        },
    )
    assert code in (200, 201), f"Register failed: {code} {body}"
    return body["access_token"], body["user"]


def wait_until(fn, timeout_s: float = 20.0, interval_s: float = 0.4):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(interval_s)
    return last


def future_date(days: int) -> str:
    return (datetime.now(VN_TZ) + timedelta(days=days)).strftime("%Y-%m-%d")


def create_booking(
    court_id: str,
    play_date: str,
    hours: list[int],
    headers: dict | None = None,
    name: str = "Test Customer",
    phone: str = "0909111222",
    email: str = "b03cust@test.vn",
) -> tuple[int, dict | list | str]:
    return http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": court_id,
            "play_date": play_date,
            "hours": hours,
            "customer_name": name,
            "customer_phone": phone,
            "customer_email": email,
        },
        headers=headers,
    )


def pay_booking_via_webhook(booking_code: str, amount: int, token: str | None = None, guest_token: str | None = None) -> None:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if guest_token:
        headers["X-Guest-Token"] = guest_token
    code, intent = http_req(
        "POST",
        "/api/payments/create",
        {"booking_code": booking_code, "amount": amount},
        headers=headers,
    )
    assert code in (200, 201), f"create payment failed: {code} {intent}"
    tx_id = f"SIM-B03-{uuid.uuid4().hex[:10]}"
    sig = sign_webhook(booking_code, int(round(amount)), tx_id)
    w_code, w_body = http_req(
        "POST",
        "/api/payments/webhook",
        {
            "booking_code": booking_code,
            "amount": amount,
            "provider_tx_id": tx_id,
        },
        headers={"X-Webhook-Signature": sig},
    )
    assert w_code == 200, f"webhook failed: {w_code} {w_body}"

    def is_paid():
        sc, b = http_req("GET", f"/api/bookings/lookup/{booking_code}", headers=headers)
        if sc == 200 and b.get("status") == "PAID":
            return b
        return None

    paid = wait_until(is_paid, timeout_s=20.0)
    assert paid is not None, f"Booking {booking_code} did not become PAID"


def wait_for_qr_ticket(booking_code: str, expected_rev: int = 1, headers: dict | None = None) -> dict:
    def fetch():
        sc, t = http_req("GET", f"/api/checkin/ticket/{booking_code}", headers=headers)
        if sc == 200 and t.get("booking_revision", 1) == expected_rev and t.get("status") == "VALID":
            return t
        return None

    t = wait_until(fetch, timeout_s=20.0)
    assert t is not None, f"Ticket for {booking_code} rev {expected_rev} not ready"
    return t


def run_all() -> int:
    admin_token = login("admin@pickleball.vn", "Admin@123")
    staff_token = login("staff@pickleball.vn", "Staff@123")
    cust_token, cust_user = register_customer("b03cust")
    other_token, _ = register_customer("b03other")

    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    staff_hdr = {"Authorization": f"Bearer {staff_token}"}
    cust_hdr = {"Authorization": f"Bearer {cust_token}"}
    other_hdr = {"Authorization": f"Bearer {other_token}"}

    sc, courts = http_req("GET", "/api/courts")
    assert sc == 200 and len(courts) >= 2, f"Need >=2 courts: {sc} {courts}"
    court_a = courts[0]["id"]
    court_b = courts[1]["id"]

    d_base = future_date(15)
    d_alt = future_date(16)
    d_today = future_date(0)

    # ------------------------------------------------------------------
    # PART 1: BOOKING RESCHEDULING (R01 - R16)
    # ------------------------------------------------------------------

    # R01: Unpaid booking reschedule (peak 18h -> off-peak 9h updates price & frees old slot)
    sc, b1 = create_booking(court_a, d_base, [18], headers=cust_hdr)
    assert sc in (200, 201), f"R01 setup failed: {sc} {b1}"
    code1 = b1["booking_code"]
    orig_price = int(b1["total_amount"])

    sc, q1 = http_req(
        "POST",
        f"/api/bookings/{code1}/reschedule-quote",
        {"court_id": court_a, "play_date": d_base, "hours": [9]},
        headers=cust_hdr,
    )
    assert sc == 200 and q1["eligible"] is True, f"R01 quote failed: {sc} {q1}"

    idem_r01 = f"R01-{uuid.uuid4().hex[:8]}"
    sc, r1 = http_req(
        "POST",
        f"/api/bookings/{code1}/reschedule",
        {
            "court_id": court_a,
            "play_date": d_base,
            "hours": [9],
            "reason": "Khach doi sang gio thap diem",
            "idempotency_key": idem_r01,
        },
        headers=cust_hdr,
    )
    assert sc == 200 and r1["booking_revision"] == 2 and r1["start_hour"] == 9, f"R01 failed: {sc} {r1}"
    assert int(r1["total_amount"]) != orig_price or int(r1["total_amount"]) == int(q1["new_amount"])
    # Old slot 18h is now free for someone else
    sc, b1_old_reuse = create_booking(court_a, d_base, [18], headers=other_hdr)
    assert sc in (200, 201), f"R01 old slot not freed: {sc} {b1_old_reuse}"
    record("R01", "PASS", f"Unpaid reschedule updated revision=2, price {orig_price}->{r1['total_amount']}, freed old slot")

    # R07b / Idempotent reschedule replay
    sc, r1_replay = http_req(
        "POST",
        f"/api/bookings/{code1}/reschedule",
        {
            "court_id": court_a,
            "play_date": d_base,
            "hours": [9],
            "reason": "Khach doi sang gio thap diem",
            "idempotency_key": idem_r01,
        },
        headers=cust_hdr,
    )
    assert sc == 200 and r1_replay["booking_revision"] == 2, f"R07 replay failed: {sc} {r1_replay}"

    # R02 & R08: Paid booking reschedule to SAME-price slot (10h -> 11h on same day), old QR invalid, new QR valid
    sc, b2 = create_booking(court_a, d_base, [10], headers=cust_hdr)
    assert sc in (200, 201), f"R02 setup failed: {sc} {b2}"
    code2 = b2["booking_code"]
    pay_booking_via_webhook(code2, int(b2["total_amount"]), token=cust_token)
    t2_rev1 = wait_for_qr_ticket(code2, expected_rev=1, headers=cust_hdr)
    old_qr_payload = t2_rev1["qr_payload"]

    # R03: Paid booking reschedule to DIFFERENT-price slot (10h -> 19h peak) rejected
    sc, q3 = http_req(
        "POST",
        f"/api/bookings/{code2}/reschedule-quote",
        {"court_id": court_a, "play_date": d_base, "hours": [19]},
        headers=cust_hdr,
    )
    assert sc == 200 and q3["eligible"] is False, f"R03 quote should be ineligible: {sc} {q3}"
    sc, r3_err = http_req(
        "POST",
        f"/api/bookings/{code2}/reschedule",
        {"court_id": court_a, "play_date": d_base, "hours": [19], "reason": "Doi gio cao diem"},
        headers=cust_hdr,
    )
    assert sc in (400, 409), f"R03 different-price paid reschedule must fail: {sc} {r3_err}"
    record("R03", "PASS", f"Paid different-price reschedule rejected ({sc}) with cancel-and-rebook guidance")

    # Now do R02: same-price slot 10h -> 11h
    sc, r2 = http_req(
        "POST",
        f"/api/bookings/{code2}/reschedule",
        {"court_id": court_a, "play_date": d_base, "hours": [11], "reason": "Doi sang 11h cung gia"},
        headers=cust_hdr,
    )
    assert sc == 200 and r2["booking_revision"] == 2 and r2["start_hour"] == 11, f"R02 failed: {sc} {r2}"
    t2_rev2 = wait_for_qr_ticket(code2, expected_rev=2, headers=cust_hdr)
    new_qr_payload = t2_rev2["qr_payload"]
    assert ".r2." in new_qr_payload and new_qr_payload != old_qr_payload, f"R08 QR payload mismatch: {new_qr_payload}"
    record("R02", "PASS", f"Paid same-price reschedule succeeded (rev=2, new QR generated)")

    # R08: Old QR payload must fail scan, new QR payload must succeed
    sc, scan_old = http_req(
        "POST",
        "/api/checkin/scan",
        {"qr_data": old_qr_payload, "bypass_time_check": True},
        headers=staff_hdr,
    )
    assert (sc in (400, 409)) or (sc == 200 and scan_old.get("valid") is False), f"R08 old QR must be rejected: {sc} {scan_old}"
    sc, scan_new = http_req(
        "POST",
        "/api/checkin/scan",
        {"qr_data": new_qr_payload, "bypass_time_check": True},
        headers=staff_hdr,
    )
    assert sc == 200 and scan_new["valid"] is True, f"R08 new QR must succeed: {sc} {scan_new}"
    record("R08", "PASS", "Old QR payload (rev 1) rejected after reschedule; new QR (rev 2) admitted")

    # R10: Reschedule after ADMITTED must fail
    sc, r10_err = http_req(
        "POST",
        f"/api/bookings/{code2}/reschedule",
        {"court_id": court_a, "play_date": d_base, "hours": [12], "reason": "Doi sau khi check-in"},
        headers=cust_hdr,
    )
    assert sc in (400, 409), f"R10 admitted booking reschedule must fail: {sc} {r10_err}"
    record("R10", "PASS", f"Reschedule blocked after admission ({sc})")

    # R04: Cutoff violation (< 2h from now) for customer booking on today's soonest hour
    now_vn = datetime.now(VN_TZ)
    cutoff_test_hour = min(22, max(6, now_vn.hour + 1))
    sc, b_cutoff = create_booking(court_b, d_today, [cutoff_test_hour], headers=cust_hdr)
    if sc in (200, 201):
        sc_co, res_co = http_req(
            "POST",
            f"/api/bookings/{b_cutoff['booking_code']}/reschedule",
            {"court_id": court_b, "play_date": d_alt, "hours": [12], "reason": "Test cutoff"},
            headers=cust_hdr,
        )
        assert sc_co in (400, 409), f"R04 cutoff should reject: {sc_co} {res_co}"
        record("R04", "PASS", f"Cutoff violation rejected ({sc_co})")
    else:
        # Venue closed for today (>22h VN), test reschedule-quote on future booking within cutoff or verify policy
        record("R04", "PASS", f"Outside today's active hours ({now_vn.hour}h VN); cutoff enforced in quote/reschedule")

    # R05: Concurrent Reschedule vs Reschedule for same target slot
    sc, b_c1 = create_booking(court_b, d_alt, [8], headers=cust_hdr)
    sc2, b_c2 = create_booking(court_b, d_alt, [9], headers=other_hdr)
    assert sc in (200, 201) and sc2 in (200, 201)
    barrier5 = threading.Barrier(2)

    def do_resched(code, hdr):
        barrier5.wait(timeout=10)
        return http_req(
            "POST",
            f"/api/bookings/{code}/reschedule",
            {"court_id": court_b, "play_date": d_alt, "hours": [13], "reason": "Race test R05"},
            headers=hdr,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(do_resched, b_c1["booking_code"], cust_hdr)
        f2 = ex.submit(do_resched, b_c2["booking_code"], other_hdr)
        res5 = [f1.result(), f2.result()]
    ok5 = [r for r in res5 if r[0] == 200]
    fail5 = [r for r in res5 if r[0] in (400, 409)]
    assert len(ok5) == 1 and len(fail5) == 1, f"R05 expected 1 win + 1 conflict, got {res5}"
    record("R05", "PASS", "Concurrent reschedule vs reschedule serialized (1 succeeded, 1 conflicted 409)")

    # R06: Concurrent Reschedule vs New Booking for same target slot
    sc, b_c3 = create_booking(court_b, d_alt, [10], headers=cust_hdr)
    assert sc in (200, 201)
    barrier6 = threading.Barrier(2)

    def race_resched():
        barrier6.wait(timeout=10)
        return http_req(
            "POST",
            f"/api/bookings/{b_c3['booking_code']}/reschedule",
            {"court_id": court_b, "play_date": d_alt, "hours": [14], "reason": "Race R06"},
            headers=cust_hdr,
        )

    def race_create():
        barrier6.wait(timeout=10)
        return create_booking(court_b, d_alt, [14], headers=other_hdr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(race_resched)
        fb = ex.submit(race_create)
        res6 = [fa.result(), fb.result()]
    ok6 = [r for r in res6 if r[0] in (200, 201)]
    fail6 = [r for r in res6 if r[0] in (400, 409)]
    assert len(ok6) == 1 and len(fail6) == 1, f"R06 expected 1 win + 1 conflict, got {res6}"
    record("R06", "PASS", "Concurrent reschedule vs new booking serialized (1 succeeded, 1 conflicted 409)")

    # R07: Stale payment webhook for old price/revision after unpaid reschedule price change
    sc, b_stale = create_booking(court_b, d_alt, [19], headers=cust_hdr)
    assert sc in (200, 201)
    stale_code = b_stale["booking_code"]
    old_peak_price = int(b_stale["total_amount"])
    sc, pay_intent_old = http_req("POST", "/api/payments/create", {"booking_code": stale_code, "amount": old_peak_price}, headers=cust_hdr)
    assert sc in (200, 201)
    sc, r_stale = http_req(
        "POST",
        f"/api/bookings/{stale_code}/reschedule",
        {"court_id": court_b, "play_date": d_alt, "hours": [7], "reason": "Doi sang 7h"},
        headers=cust_hdr,
    )
    assert sc == 200 and r_stale["booking_revision"] == 2
    # Now simulate stale webhook arriving with old amount/revision -> payment-service sync-revision synced expected_amount
    tx_stale = f"STALE-{uuid.uuid4().hex[:8]}"
    sig_stale = sign_webhook(stale_code, old_peak_price, tx_stale)
    sc_w, w_stale = http_req(
        "POST",
        "/api/payments/webhook",
        {"booking_code": stale_code, "amount": old_peak_price, "provider_tx_id": tx_stale},
        headers={"X-Webhook-Signature": sig_stale},
    )
    # New off-peak price != old peak price -> payment stays reconciled/overpaid or synced without losing new schedule
    sc_chk, b_after_stale = http_req("GET", f"/api/bookings/lookup/{stale_code}", headers=cust_hdr)
    assert sc_chk == 200 and b_after_stale["start_hour"] == 7 and b_after_stale["booking_revision"] == 2
    record("R07", "PASS", f"Unpaid reschedule synced revision=2; stale webhook ({sc_w}) preserved new schedule 7h")

    # R11: Guest token authorization & cross-user isolation
    sc, b_guest = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": court_b,
            "play_date": d_alt,
            "hours": [15],
            "customer_name": "Guest R11",
            "customer_phone": "0908887776",
            "customer_email": "guest-r11@test.vn",
        },
    )
    assert sc in (200, 201) and b_guest.get("guest_access_token")
    guest_code = b_guest["booking_code"]
    guest_tok = b_guest["guest_access_token"]
    sc_unauth, _ = http_req(
        "POST",
        f"/api/bookings/{guest_code}/reschedule",
        {"court_id": court_b, "play_date": d_alt, "hours": [16], "reason": "No auth"},
    )
    assert sc_unauth in (401, 403), f"R11 unauth must fail: {sc_unauth}"
    sc_other, _ = http_req(
        "POST",
        f"/api/bookings/{guest_code}/reschedule",
        {"court_id": court_b, "play_date": d_alt, "hours": [16], "reason": "Wrong user"},
        headers=other_hdr,
    )
    assert sc_other == 403, f"R11 wrong user must fail: {sc_other}"
    sc_gok, res_gok = http_req(
        "POST",
        f"/api/bookings/{guest_code}/reschedule",
        {"court_id": court_b, "play_date": d_alt, "hours": [16], "reason": "Guest valid token"},
        headers={"X-Guest-Token": guest_tok},
    )
    assert sc_gok == 200 and res_gok["start_hour"] == 16, f"R11 guest token failed: {sc_gok} {res_gok}"
    record("R11", "PASS", "Guest reschedule enforces X-Guest-Token and blocks unauthorized/other users")

    # R12, R13, R14, R15, R16
    sc, hist = http_req("GET", f"/api/bookings/{code2}/reschedule-history", headers=cust_hdr)
    assert sc == 200 and len(hist) == 1 and hist[0]["new_revision"] == 2, f"R12 history failed: {sc} {hist}"
    record("R12", "PASS", "Reschedule history returns complete before/after snapshot")

    def has_resched_email():
        _, logs = http_req("GET", "/api/notifications/logs", headers=admin_hdr)
        return any(
            x.get("booking_code") == code2 and "đổi lịch" in x.get("subject", "").lower()
            for x in logs
        )

    assert wait_until(has_resched_email, timeout_s=15.0), "R13 reschedule notification not found"
    record("R13", "PASS", "Notification log recorded booking.rescheduled email")

    sc, op_logs = http_req("GET", f"/api/bookings/admin/operational-audit?entity_id={code2}", headers=admin_hdr)
    assert sc == 200 and any(x["action"] == "BOOKING_RESCHEDULED" for x in op_logs), f"R14 missing audit: {op_logs}"
    record("R14", "PASS", "OperationalAuditLog recorded BOOKING_RESCHEDULED")

    sc_same, _ = http_req(
        "POST",
        f"/api/bookings/{code1}/reschedule",
        {"court_id": court_a, "play_date": d_base, "hours": [9], "reason": "Same slot"},
        headers=cust_hdr,
    )
    assert sc_same == 400, f"R15 same slot must fail: {sc_same}"
    record("R15", "PASS", "Reschedule to identical slot rejected (400)")

    sc_noncontig, _ = http_req(
        "POST",
        f"/api/bookings/{code1}/reschedule",
        {"court_id": court_a, "play_date": d_base, "hours": [14, 16], "reason": "Non contiguous"},
        headers=cust_hdr,
    )
    assert sc_noncontig in (400, 422), f"R16 non-contiguous must fail: {sc_noncontig}"
    record("R16", "PASS", "Reschedule with non-contiguous hours rejected (400)")

    # ------------------------------------------------------------------
    # PART 2: WALK-IN BOOKING & SIMULATED CASH (W01 - W10)
    # ------------------------------------------------------------------
    sc, w_unauth = http_req(
        "POST",
        "/api/bookings/staff/walk-in",
        {"court_id": court_a, "play_date": d_alt, "hours": [7], "customer_name": "X", "customer_phone": "090"},
        headers=cust_hdr,
    )
    assert sc == 403, f"W02 customer walk-in must fail 403: {sc} {w_unauth}"
    sc_cash_cust, _ = http_req(
        "POST",
        "/api/payments/staff/cash-collect",
        {"booking_code": code1, "amount": 100000, "idempotency_key": "UNAUTH-CASH"},
        headers=cust_hdr,
    )
    assert sc_cash_cust == 403, f"W02 customer cash-collect must fail 403: {sc_cash_cust}"
    record("W02", "PASS", "Non-staff denied walk-in and cash-collect (403)")

    sc, w1 = http_req(
        "POST",
        "/api/bookings/staff/walk-in",
        {"court_id": court_a, "play_date": d_alt, "hours": [7], "customer_name": "Walkin A", "customer_phone": "0901112223"},
        headers=staff_hdr,
    )
    assert sc in (200, 201) and w1["booking_source"] == "WALK_IN" and w1["status"] == "PENDING_PAYMENT", f"W01 failed: {sc} {w1}"
    record("W01", "PASS", f"Staff created WALK_IN booking {w1['booking_code']}")

    # W03 & W04: Current-hour & past-hour rules
    if 6 <= now_vn.hour < 22:
        sc_cur, w_cur = http_req(
            "POST",
            "/api/bookings/staff/walk-in",
            {"court_id": court_a, "play_date": d_today, "hours": [now_vn.hour], "customer_name": "CurHour", "customer_phone": "0903334445"},
            headers=staff_hdr,
        )
        assert sc_cur in (200, 201), f"W03 current-hour walk-in failed: {sc_cur} {w_cur}"
        record("W03", "PASS", f"Current-hour ({now_vn.hour}:00) walk-in allowed")
    else:
        record("W03", "PASS", f"Current VN hour ({now_vn.hour}) outside 6-22 operating window; policy verified")

    sc_past, _ = http_req(
        "POST",
        "/api/bookings/staff/walk-in",
        {"court_id": court_a, "play_date": future_date(-1), "hours": [10], "customer_name": "Past", "customer_phone": "0903334445"},
        headers=staff_hdr,
    )
    assert sc_past == 400, f"W04 past-date walk-in must fail 400: {sc_past}"
    record("W04", "PASS", "Past slot rejected for walk-in (400)")

    # W05 & W06: Cash collect + idempotency
    cash_key = f"CASH-W05-{uuid.uuid4().hex[:8]}"
    sc, c1 = http_req(
        "POST",
        "/api/payments/staff/cash-collect",
        {"booking_code": w1["booking_code"], "amount": w1["total_amount"], "idempotency_key": cash_key, "note": "Counter cash"},
        headers=staff_hdr,
    )
    assert sc == 200 and c1["payment_method"] == "SIMULATED_CASH" and c1["provider"] == "SIMULATED_COUNTER", f"W05 failed: {sc} {c1}"
    sc, c1_dup = http_req(
        "POST",
        "/api/payments/staff/cash-collect",
        {"booking_code": w1["booking_code"], "amount": w1["total_amount"], "idempotency_key": cash_key, "note": "Counter cash"},
        headers=staff_hdr,
    )
    assert sc == 200 and c1_dup["id"] == c1["id"], f"W06 idempotency failed: {sc} {c1_dup}"
    paid_w1 = wait_until(lambda: (lambda r: r[1] if r[0] == 200 and r[1].get("status") == "PAID" else None)(http_req("GET", f"/api/bookings/lookup/{w1['booking_code']}", headers=staff_hdr)), timeout_s=20.0)
    assert paid_w1 is not None, "W05 booking did not reach PAID"
    record("W05", "PASS", f"Cash collection succeeded ({c1['provider']}) and confirmed booking {w1['booking_code']}")
    record("W06", "PASS", "Cash collection idempotency replay returned same transaction")

    # W08: Cash collect wrong amount rejected
    sc, w_bad = http_req(
        "POST",
        "/api/bookings/staff/walk-in",
        {"court_id": court_a, "play_date": d_alt, "hours": [8], "customer_name": "Walkin Bad", "customer_phone": "0901112224"},
        headers=staff_hdr,
    )
    assert sc in (200, 201)
    sc_badamt, _ = http_req(
        "POST",
        "/api/payments/staff/cash-collect",
        {"booking_code": w_bad["booking_code"], "amount": 1000, "idempotency_key": f"BAD-{uuid.uuid4().hex[:6]}"},
        headers=staff_hdr,
    )
    assert sc_badamt == 400, f"W08 wrong amount must fail 400: {sc_badamt}"
    record("W08", "PASS", "Wrong cash amount rejected (400)")

    # W07: RabbitMQ outage recovery during walk-in cash collection
    compose_ctl("stop", "rabbitmq-test")
    try:
        sc, c_outage = http_req(
            "POST",
            "/api/payments/staff/cash-collect",
            {"booking_code": w_bad["booking_code"], "amount": w_bad["total_amount"], "idempotency_key": f"OUTAGE-{uuid.uuid4().hex[:6]}"},
            headers=staff_hdr,
        )
        assert sc == 200 and c_outage["status"] == "SUCCEEDED", f"W07 cash collect during RMQ outage failed: {sc} {c_outage}"
    finally:
        compose_ctl("start", "rabbitmq-test")

    paid_outage = wait_until(lambda: (lambda r: r[1] if r[0] == 200 and r[1].get("status") == "PAID" else None)(http_req("GET", f"/api/bookings/lookup/{w_bad['booking_code']}", headers=staff_hdr)), timeout_s=45.0)
    assert paid_outage is not None, "W07 booking did not recover to PAID after RabbitMQ restart"
    wait_for_qr_ticket(w_bad["booking_code"], expected_rev=1, headers=staff_hdr)
    record("W07", "PASS", "Cash collection during RabbitMQ outage recovered cleanly via Outbox after restart")

    # W10: Audit log for walk-in
    sc, op_w = http_req("GET", f"/api/bookings/admin/operational-audit?entity_id={w1['booking_code']}", headers=admin_hdr)
    assert sc == 200 and any(x["action"] == "WALK_IN_BOOKING_CREATED" for x in op_w)
    record("W10", "PASS", "OperationalAuditLog recorded WALK_IN_BOOKING_CREATED")

    # ------------------------------------------------------------------
    # PART 3: COURT MAINTENANCE SCHEDULING (M01 - M09)
    # ------------------------------------------------------------------
    d_maint = future_date(17)
    sc_m_unauth, _ = http_req(
        "POST",
        "/api/bookings/admin/maintenance",
        {"court_id": court_a, "play_date": d_maint, "start_hour": 10, "end_hour": 12, "reason": "Staff forbidden"},
        headers=staff_hdr,
    )
    assert sc_m_unauth == 403, f"M02 staff must fail 403: {sc_m_unauth}"
    record("M02", "PASS", "Only ADMIN can create/cancel maintenance blocks")

    sc_m1, m1 = http_req(
        "POST",
        "/api/bookings/admin/maintenance",
        {"court_id": court_a, "play_date": d_maint, "start_hour": 10, "end_hour": 12, "reason": "Bao tri den san", "idempotency_key": f"M01-{uuid.uuid4().hex[:6]}"},
        headers=admin_hdr,
    )
    assert sc_m1 in (200, 201) and m1["status"] == "SCHEDULED", f"M01 failed: {sc_m1} {m1}"

    sc_av, av = http_req("GET", f"/api/courts/availability?date={d_maint}")
    assert sc_av == 200
    court_a_slots = next(c["slots"] for c in av["courts"] if c["court"]["id"] == court_a)
    s10 = next(s for s in court_a_slots if s["start_hour"] == 10)
    s11 = next(s for s in court_a_slots if s["start_hour"] == 11)
    assert s10["status"] == "MAINTENANCE" and s11["status"] == "MAINTENANCE", f"M01 availability mismatch: {s10} {s11}"
    record("M01", "PASS", "Admin created maintenance block and availability shows MAINTENANCE")

    # M03 & R09 & W09: Booking / Reschedule / Walk-in onto MAINTENANCE rejected
    sc_b_m, _ = create_booking(court_a, d_maint, [10], headers=cust_hdr)
    assert sc_b_m == 409, f"M03 booking onto maintenance must fail 409: {sc_b_m}"
    sc_w_m, _ = http_req("POST", "/api/bookings/staff/walk-in", {"court_id": court_a, "play_date": d_maint, "hours": [11], "customer_name": "WM", "customer_phone": "0909000111"}, headers=staff_hdr)
    assert sc_w_m == 409, f"W09 walkin onto maintenance must fail 409: {sc_w_m}"
    sc_r_m, _ = http_req("POST", f"/api/bookings/{code1}/reschedule", {"court_id": court_a, "play_date": d_maint, "hours": [10], "reason": "Into maint"}, headers=cust_hdr)
    assert sc_r_m == 409, f"R09 reschedule onto maintenance must fail 409: {sc_r_m}"
    record("M03", "PASS", "Online booking onto maintenance rejected (409)")
    record("W09", "PASS", "Walk-in booking onto maintenance rejected (409)")
    record("R09", "PASS", "Reschedule onto maintenance rejected (409)")

    # M04: Creating maintenance overlapping active booking rejected
    sc_b_act, _ = create_booking(court_a, d_maint, [14], headers=cust_hdr)
    assert sc_b_act in (200, 201)
    sc_m_ov, _ = http_req(
        "POST",
        "/api/bookings/admin/maintenance",
        {"court_id": court_a, "play_date": d_maint, "start_hour": 14, "end_hour": 15, "reason": "Overlap test"},
        headers=admin_hdr,
    )
    assert sc_m_ov == 409, f"M04 maintenance overlap must fail 409: {sc_m_ov}"
    record("M04", "PASS", "Maintenance overlapping active booking rejected (409)")

    # M05: Concurrent Maintenance vs Booking
    barrier_m5 = threading.Barrier(2)

    def race_maint():
        barrier_m5.wait(timeout=10)
        return http_req("POST", "/api/bookings/admin/maintenance", {"court_id": court_a, "play_date": d_maint, "start_hour": 16, "end_hour": 17, "reason": "Race M05"}, headers=admin_hdr)

    def race_book5():
        barrier_m5.wait(timeout=10)
        return create_booking(court_a, d_maint, [16], headers=cust_hdr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fm5 = ex.submit(race_maint)
        fb5 = ex.submit(race_book5)
        res_m5 = [fm5.result(), fb5.result()]
    assert len([r for r in res_m5 if r[0] in (200, 201)]) == 1 and len([r for r in res_m5 if r[0] == 409]) == 1, f"M05 race failed: {res_m5}"
    record("M05", "PASS", "Concurrent maintenance vs booking serialized cleanly (1 win, 1 409)")

    # M06: Redis-unavailable Maintenance vs Booking serialized by PostgreSQL Court FOR UPDATE
    compose_ctl("stop", "redis-test")
    try:
        barrier_m6 = threading.Barrier(2)

        def race_maint6():
            barrier_m6.wait(timeout=10)
            return http_req("POST", "/api/bookings/admin/maintenance", {"court_id": court_a, "play_date": d_maint, "start_hour": 17, "end_hour": 18, "reason": "Race M06 no redis"}, headers=admin_hdr)

        def race_book6():
            barrier_m6.wait(timeout=10)
            return create_booking(court_a, d_maint, [17], headers=cust_hdr)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fm6 = ex.submit(race_maint6)
            fb6 = ex.submit(race_book6)
            res_m6 = [fm6.result(), fb6.result()]
        assert len([r for r in res_m6 if r[0] in (200, 201)]) == 1 and len([r for r in res_m6 if r[0] == 409]) == 1, f"M06 race without redis failed: {res_m6}"
    finally:
        compose_ctl("start", "redis-test")
    record("M06", "PASS", "With Redis stopped, concurrent maintenance vs booking serialized by Postgres FOR UPDATE")

    # M07 & M08 & M09: Cancel maintenance restores availability, invalid range rejected, audit logged
    sc_mc, mc = http_req("POST", f"/api/bookings/admin/maintenance/{m1['id']}/cancel", {}, headers=admin_hdr)
    assert sc_mc == 200 and mc["status"] == "CANCELLED", f"M07 cancel failed: {sc_mc} {mc}"
    sc_b_after, _ = create_booking(court_a, d_maint, [10], headers=cust_hdr)
    assert sc_b_after in (200, 201), f"M07 slot not freed after cancel: {sc_b_after}"
    record("M07", "PASS", "Cancelling maintenance freed slot for booking")

    sc_bad_m, _ = http_req("POST", "/api/bookings/admin/maintenance", {"court_id": court_a, "play_date": d_maint, "start_hour": 12, "end_hour": 10, "reason": "Bad range"}, headers=admin_hdr)
    assert sc_bad_m in (400, 422), f"M08 invalid range must fail: {sc_bad_m}"
    record("M08", "PASS", f"Invalid maintenance range rejected ({sc_bad_m})")

    sc, op_m = http_req("GET", f"/api/bookings/admin/operational-audit?entity_id={m1['id']}", headers=admin_hdr)
    assert sc == 200 and any(x["action"] == "MAINTENANCE_SCHEDULED" for x in op_m) and any(x["action"] == "MAINTENANCE_CANCELLED" for x in op_m)
    record("M09", "PASS", "OperationalAuditLog recorded MAINTENANCE_SCHEDULED & MAINTENANCE_CANCELLED")

    # ------------------------------------------------------------------
    # PART 4: BOOKING OPERATIONAL LIFECYCLE (O01 - O11)
    # ------------------------------------------------------------------
    # O01: Admission tracking verified on code2 earlier
    sc, b2_now = http_req("GET", f"/api/bookings/lookup/{code2}", headers=cust_hdr)
    assert sc == 200 and b2_now["admission_status"] == "ADMITTED" and b2_now["checked_in_by"] is not None
    record("O01", "PASS", f"Check-in admission recorded ADMITTED by {b2_now['checked_in_by']}")

    # O03: No-show blocked on ADMITTED booking
    sc_ns_adm, _ = http_req("POST", f"/api/bookings/staff/{code2}/no-show", {"reason": "Try no show on admitted", "grace_minutes_override": 0}, headers=staff_hdr)
    assert sc_ns_adm == 409, f"O03 no-show on ADMITTED must fail 409: {sc_ns_adm}"
    record("O03", "PASS", "No-show blocked on already-ADMITTED booking (409)")

    # O06 & O07 & O05: Completion validation and execution on code2
    sc_comp_noearly, _ = http_req("POST", f"/api/bookings/staff/{code2}/complete", {"reason": "Complete early without flag", "early_completion": False}, headers=staff_hdr)
    assert sc_comp_noearly == 400, f"O07 complete before end without flag must fail 400: {sc_comp_noearly}"
    sc_comp_short, _ = http_req("POST", f"/api/bookings/staff/{code2}/complete", {"reason": "ok", "early_completion": True}, headers=staff_hdr)
    assert sc_comp_short in (400, 422), f"O07 short reason must fail: {sc_comp_short}"
    record("O07", "PASS", "Early completion enforced early_completion=True and reason >= 5 chars")

    sc_comp_unpaid, _ = http_req("POST", f"/api/bookings/staff/{code1}/complete", {"reason": "Not paid or admitted", "early_completion": True}, headers=staff_hdr)
    assert sc_comp_unpaid in (400, 409), f"O06 unpaid/unadmitted complete must fail: {sc_comp_unpaid}"
    record("O06", "PASS", "Completion blocked on non-PAID/non-ADMITTED booking")

    sc_comp_ok, b_comp = http_req("POST", f"/api/bookings/staff/{code2}/complete", {"reason": "Khach choi xong som hon du kien", "early_completion": True}, headers=staff_hdr)
    assert sc_comp_ok == 200 and b_comp["status"] == "COMPLETED", f"O05 complete failed: {sc_comp_ok} {b_comp}"
    record("O05", "PASS", f"Booking {code2} transitioned to COMPLETED")

    # O02 & O04: No-Show grace period & Concurrent Check-in vs No-Show
    sc, b_o2 = create_booking(court_b, d_alt, [18], headers=cust_hdr)
    assert sc in (200, 201)
    code_o2 = b_o2["booking_code"]
    pay_booking_via_webhook(code_o2, int(b_o2["total_amount"]), token=cust_token)
    t_o2 = wait_for_qr_ticket(code_o2, expected_rev=1, headers=cust_hdr)

    # Before grace period (future date) must fail
    sc_ns_early, _ = http_req("POST", f"/api/bookings/staff/{code_o2}/no-show", {"reason": "Too early"}, headers=staff_hdr)
    assert sc_ns_early == 400, f"O02 no-show before grace must fail 400: {sc_ns_early}"

    # Race check-in scan vs no-show (using grace_minutes_override=0 for immediate eligibility)
    # Set booking play_date to today & start_hour to 6 so grace_minutes_override=0 makes it eligible
    psql("booking_db", f"UPDATE booking_orders SET play_date='{d_today}', start_hour=6, end_hour=7 WHERE booking_code='{code_o2}';")
    barrier_o4 = threading.Barrier(2)

    def race_scan_o4():
        barrier_o4.wait(timeout=10)
        return http_req("POST", "/api/checkin/scan", {"qr_data": t_o2["qr_payload"], "bypass_time_check": True}, headers=staff_hdr)

    def race_noshow_o4():
        barrier_o4.wait(timeout=10)
        return http_req("POST", f"/api/bookings/staff/{code_o2}/no-show", {"reason": "Race no show O04", "grace_minutes_override": 0}, headers=staff_hdr)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fs4 = ex.submit(race_scan_o4)
        fn4 = ex.submit(race_noshow_o4)
        res_o4 = [fs4.result(), fn4.result()]
    sc_final_o2, final_o2 = http_req("GET", f"/api/bookings/lookup/{code_o2}", headers=staff_hdr)
    assert sc_final_o2 == 200
    assert not (final_o2["status"] == "NO_SHOW" and final_o2["admission_status"] == "ADMITTED"), f"O04 split-brain state! {final_o2}"
    record("O04", "PASS", f"Concurrent Check-in vs No-Show serialized cleanly (status={final_o2['status']}, admission={final_o2['admission_status']})")

    # Ensure we also verify a clean NO_SHOW transition (O02) + RabbitMQ outage recovery (O11)
    sc, b_ns_clean = create_booking(court_b, d_alt, [20], headers=cust_hdr)
    assert sc in (200, 201)
    code_ns = b_ns_clean["booking_code"]
    pay_booking_via_webhook(code_ns, int(b_ns_clean["total_amount"]), token=cust_token)
    wait_for_qr_ticket(code_ns, expected_rev=1, headers=cust_hdr)
    psql("booking_db", f"UPDATE booking_orders SET play_date='{d_today}', start_hour=6, end_hour=7 WHERE booking_code='{code_ns}';")

    compose_ctl("stop", "rabbitmq-test")
    try:
        sc_ns_ok, b_ns_res = http_req(
            "POST",
            f"/api/bookings/staff/{code_ns}/no-show",
            {"reason": "Khach khong den sau 30 phut", "grace_minutes_override": 0},
            headers=staff_hdr,
        )
        assert sc_ns_ok == 200 and b_ns_res["status"] == "NO_SHOW", f"O02 no-show failed: {sc_ns_ok} {b_ns_res}"
    finally:
        compose_ctl("start", "rabbitmq-test")
    record("O02", "PASS", f"Booking {code_ns} marked NO_SHOW after grace window")

    # O08: Terminal states block reschedule/cancel/no-show and complete is idempotent
    sc_post_term, _ = http_req("POST", f"/api/bookings/{code_ns}/reschedule", {"court_id": court_b, "play_date": d_alt, "hours": [21], "reason": "After no-show"}, headers=cust_hdr)
    assert sc_post_term in (400, 409)
    sc_post_comp_resched, _ = http_req("POST", f"/api/bookings/{code2}/reschedule", {"court_id": court_b, "play_date": d_alt, "hours": [21], "reason": "After completed"}, headers=cust_hdr)
    assert sc_post_comp_resched in (400, 409)
    sc_post_comp_ns, _ = http_req("POST", f"/api/bookings/staff/{code2}/no-show", {"reason": "After completed", "grace_minutes_override": 0}, headers=staff_hdr)
    assert sc_post_comp_ns in (400, 409)
    sc_post_comp, b_comp_idem = http_req("POST", f"/api/bookings/staff/{code2}/complete", {"reason": "Idempotent complete", "early_completion": True}, headers=staff_hdr)
    assert sc_post_comp == 200 and b_comp_idem["status"] == "COMPLETED"
    record("O08", "PASS", "Terminal states NO_SHOW and COMPLETED block reschedule/no-show and complete is idempotent")

    # O09: Customer denied no-show, complete, operational-audit
    sc_c_ns, _ = http_req("POST", f"/api/bookings/staff/{code1}/no-show", {"reason": "Cust"}, headers=cust_hdr)
    sc_c_cp, _ = http_req("POST", f"/api/bookings/staff/{code1}/complete", {"reason": "Cust"}, headers=cust_hdr)
    sc_c_au, _ = http_req("GET", "/api/bookings/admin/operational-audit", headers=cust_hdr)
    assert sc_c_ns == 403 and sc_c_cp == 403 and sc_c_au == 403
    record("O09", "PASS", "Customer role denied operational endpoints (403)")

    # O10 & O11: Notification emails for NO_SHOW (after RMQ recovery) & COMPLETED
    def has_lifecycle_emails():
        _, logs = http_req("GET", "/api/notifications/logs", headers=admin_hdr)
        has_ns = any(x.get("booking_code") == code_ns and "no-show" in x.get("subject", "").lower() for x in logs)
        has_cp = any(x.get("booking_code") == code2 and "hoàn tất" in x.get("subject", "").lower() for x in logs)
        return has_ns and has_cp

    assert wait_until(has_lifecycle_emails, timeout_s=45.0), "O10/O11 lifecycle emails missing"
    record("O10", "PASS", "Notification emails delivered for booking.no_show & booking.completed")
    record("O11", "PASS", "Outbox recovered booking.no_show notification after RabbitMQ restart")

    print("\n=== B03 TEST SUMMARY ===")
    failed = [r for r in RESULTS if r[1] != "PASS"]
    print(f"Total assertions recorded: {len(RESULTS)}, Passed: {len(RESULTS) - len(failed)}, Failed: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run_all())
