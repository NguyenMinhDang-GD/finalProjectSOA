import concurrent.futures
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BASE_URL = os.environ.get("TEST_GATEWAY_URL", "http://localhost:18080")
WEBHOOK_SECRET = os.environ.get("TEST_WEBHOOK_SECRET", "test-only-webhook-secret-p01")
INTERNAL_KEY = os.environ.get("TEST_INTERNAL_KEY", "test-only-internal-key-p01")
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

RESULTS: list[tuple[str, str, str]] = []


def record(test_id: str, status: str, detail: str) -> None:
    RESULTS.append((test_id, status, detail))
    print(f"[{status}] {test_id}: {detail}", flush=True)


def http_req(
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict | None = None,
    base: str = BASE_URL,
    retry_on_429: bool = True,
) -> tuple[int, dict | list | str, dict[str, str]]:
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    for attempt in range(6):
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                try:
                    return resp.status, json.loads(raw), resp_headers
                except json.JSONDecodeError:
                    return resp.status, raw, resp_headers
        except urllib.error.HTTPError as err:
            if err.code == 429 and retry_on_429 and attempt < 5:
                time.sleep(1.0)
                continue
            raw = err.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in err.headers.items()}
            try:
                return err.code, json.loads(raw), resp_headers
            except json.JSONDecodeError:
                return err.code, raw, resp_headers
    raise AssertionError(f"Rate-limited on {method} {path}")


def sign_webhook(booking_code: str, amount: int, provider_tx_id: str) -> str:
    canonical = f"{booking_code}:{int(round(amount))}:{provider_tx_id}"
    return hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_refund_callback(refund_code: str, provider_refund_id: str, outcome: str) -> str:
    canonical = f"{refund_code}:{provider_refund_id}:{outcome}"
    return hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def login(email: str, password: str) -> str:
    for attempt in range(10):
        code, body, _ = http_req("POST", "/api/auth/login", {"email": email, "password": password})
        if code == 429 and attempt < 9:
            time.sleep(1.5)
            continue
        assert code == 200 and isinstance(body, dict), f"Login failed for {email}: {code} {body}"
        return body["access_token"]
    raise AssertionError(f"Login rate-limited for {email}")


def register_customer(prefix: str) -> tuple[str, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@test.vn"
    for attempt in range(10):
        code, body, _ = http_req(
            "POST",
            "/api/auth/register",
            {
                "email": email,
                "password": "TestPassword123!",
                "full_name": "B02 Test User",
                "phone": "0909123456",
            },
        )
        if code == 429 and attempt < 9:
            time.sleep(1.5)
            continue
        assert code in (200, 201), f"Register failed: {code} {body}"
        return body["access_token"], email
    raise AssertionError(f"Register rate-limited for {email}")


def pick_slot(days_ahead: int = 3, prefer_hour: int | None = None) -> tuple[str, str, int]:
    play_date = (datetime.now(VN_TZ).date() + timedelta(days=days_ahead)).isoformat()
    code, avail, _ = http_req("GET", f"/api/courts/availability?date={play_date}")
    assert code == 200 and isinstance(avail, dict), f"Availability failed: {code} {avail}"
    for court_entry in avail["courts"]:
        court_id = court_entry["court"]["id"]
        for slot in court_entry["slots"]:
            if slot["status"] == "AVAILABLE":
                if prefer_hour is None or slot["start_hour"] == prefer_hour:
                    return court_id, play_date, slot["start_hour"]
    raise AssertionError(f"No available slot found on {play_date}")


def create_booking(token: str | None, days_ahead: int = 3, prefer_hour: int | None = None) -> dict:
    court_id, play_date, hour = pick_slot(days_ahead=days_ahead, prefer_hour=prefer_hour)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    code, body, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": court_id,
            "play_date": play_date,
            "hours": [hour],
            "customer_name": "B02 Customer",
            "customer_phone": "0909111222",
            "customer_email": "b02-customer@test.vn",
        },
        headers=headers,
    )
    assert code == 201 and isinstance(body, dict), f"Create booking failed: {code} {body}"
    return body


def wait_booking_status(booking_code: str, expected: str, headers: dict, timeout: float = 12.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        code, body, _ = http_req("GET", f"/api/bookings/lookup/{booking_code}", headers=headers)
        if code == 200 and isinstance(body, dict):
            last = body
            if body.get("status") == expected:
                return body
        time.sleep(0.4)
    raise AssertionError(f"Booking {booking_code} did not reach {expected}; last={last}")


def wait_ticket(booking_code: str, headers: dict, timeout: float = 12.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, body, _ = http_req("GET", f"/api/checkin/ticket/{booking_code}", headers=headers)
        if code == 200 and isinstance(body, dict):
            return body
        time.sleep(0.4)
    raise AssertionError(f"Ticket for {booking_code} was not issued in time")


def run_all() -> int:
    admin_token = login("admin@pickleball.vn", "Admin@123")
    staff_token = login("staff@pickleball.vn", "Staff@123")
    cust_token, _ = register_customer("b02cust")

    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    staff_hdr = {"Authorization": f"Bearer {staff_token}"}
    cust_hdr = {"Authorization": f"Bearer {cust_token}"}

    # P01-P04: Non-financial Simulated QR & Mode metadata
    b1 = create_booking(cust_token, days_ahead=4)
    c, p1, _ = http_req("POST", "/api/payments/create", {"booking_code": b1["booking_code"]}, headers=cust_hdr)
    assert c == 201 and p1["qr_image_url"].startswith("data:image/svg+xml;base64,"), p1
    assert "vietqr.io" not in p1["qr_image_url"].lower(), p1["qr_image_url"]
    assert p1["bank_bin"] == "SIMULATED" and p1["bank_account_no"] == "DEMO-ONLY", p1
    assert "GIẢ LẬP" in p1["simulation_notice"], p1
    assert p1["expected_amount"] == int(round(b1["total_amount"])), p1
    record("P01-P04", "PASS", "Simulated non-financial SVG QR, SIMULATED provider, and MOCK_TEST mode verified")

    # P05-P07: State machine PROCESSING -> FAILED -> retry -> SUCCEEDED + attempt tracking + exact integer VND
    c, bad_dec, _ = http_req(
        "POST",
        "/api/payments/webhook",
        {"booking_code": b1["booking_code"], "amount": 100000.5, "provider_tx_id": "DEC-BAD-1"},
    )
    assert c == 422, f"Expected 422 for fractional VND, got {c} {bad_dec}"

    c, proc, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b1['booking_code']}",
        {"outcome": "PROCESSING"},
        headers=staff_hdr,
    )
    assert c == 200 and proc["status"] == "PROCESSING", proc

    c, fail, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b1['booking_code']}",
        {"outcome": "FAILED", "failure_reason": "Simulated card decline"},
        headers=staff_hdr,
    )
    assert c == 200 and fail["status"] == "FAILED", fail

    c, retried, _ = http_req("POST", f"/api/payments/booking/{b1['booking_code']}/retry", headers=cust_hdr)
    assert c == 200 and retried["status"] == "PENDING", retried

    c, succ, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b1['booking_code']}",
        {"outcome": "SUCCEEDED"},
        headers=staff_hdr,
    )
    assert c == 200 and succ["status"] == "SUCCEEDED", succ
    c, attempts, _ = http_req("GET", f"/api/payments/booking/{b1['booking_code']}/attempts", headers=cust_hdr)
    assert c == 200 and len(attempts) >= 3, attempts
    wait_booking_status(b1["booking_code"], "PAID", cust_hdr)
    record("P05-P07", "PASS", "Payment state machine PROCESSING->FAILED->retry->SUCCEEDED, integer VND & attempts verified")

    # P08: Underpayment does NOT confirm booking and opens UNDERPAYMENT reconciliation
    b2 = create_booking(cust_token, days_ahead=4)
    http_req("POST", "/api/payments/create", {"booking_code": b2["booking_code"]}, headers=cust_hdr)
    c, under, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b2['booking_code']}",
        {"outcome": "UNDERPAID"},
        headers=staff_hdr,
    )
    assert c == 200 and under["status"] == "FAILED" and under["reconciliation_status"] == "OPEN", under
    _, b2_after, _ = http_req("GET", f"/api/bookings/lookup/{b2['booking_code']}", headers=cust_hdr)
    assert b2_after["status"] == "PENDING_PAYMENT", b2_after
    record("P08", "PASS", "Underpayment kept payment FAILED, booking PENDING_PAYMENT, and opened reconciliation")

    # P09-P10: Overpayment confirms booking & opens OVERPAYMENT; Duplicate distinct tx opens DUPLICATE_PAYMENT
    b3 = create_booking(cust_token, days_ahead=4)
    http_req("POST", "/api/payments/create", {"booking_code": b3["booking_code"]}, headers=cust_hdr)
    c, over, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b3['booking_code']}",
        {"outcome": "OVERPAID", "provider_tx_id": f"OVR-{uuid.uuid4().hex[:6]}"},
        headers=staff_hdr,
    )
    assert c == 200 and over["status"] == "SUCCEEDED" and over["received_amount"] > over["expected_amount"], over
    c, dup, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b3['booking_code']}",
        {"outcome": "DUPLICATE", "provider_tx_id": f"DUP-{uuid.uuid4().hex[:6]}"},
        headers=staff_hdr,
    )
    assert c == 200 and dup["status"] == "SUCCEEDED" and dup["reconciliation_status"] == "OPEN", dup
    record("P09-P10", "PASS", "Overpayment and distinct duplicate payment reconciliation cases verified")

    # P11-P13: Late payment on cancelled booking + Admin reconciliation workflow OPEN -> IN_REVIEW -> RESOLVED
    b4 = create_booking(cust_token, days_ahead=4)
    http_req("POST", "/api/payments/create", {"booking_code": b4["booking_code"]}, headers=cust_hdr)
    c, _, _ = http_req("POST", f"/api/bookings/{b4['booking_code']}/cancel", {"reason": "Cancel before late"}, headers=cust_hdr)
    assert c == 200
    c, late, _ = http_req(
        "POST",
        f"/api/payments/simulate/{b4['booking_code']}",
        {"outcome": "LATE", "provider_tx_id": f"LATE-{uuid.uuid4().hex[:6]}"},
        headers=staff_hdr,
    )
    assert c == 200 and late["reconciliation_status"] == "COMPENSATION_REQUIRED", late

    c, cases, _ = http_req("GET", "/api/payments/admin/reconciliation", headers=admin_hdr)
    assert c == 200 and len(cases) >= 3, cases
    target_case = next(rc for rc in cases if rc["booking_code"] == b3["booking_code"])
    c, in_rev, _ = http_req(
        "POST",
        f"/api/payments/admin/reconciliation/{target_case['id']}",
        {"status": "IN_REVIEW", "resolution_note": "Reviewing discrepancy"},
        headers=admin_hdr,
    )
    assert c == 200 and in_rev["status"] == "IN_REVIEW", in_rev
    c, resolved, _ = http_req(
        "POST",
        f"/api/payments/admin/reconciliation/{target_case['id']}",
        {"status": "RESOLVED", "resolution_action": "MANUAL_WRITE_OFF", "resolution_note": "Resolved in B02 test with manual write-off justification"},
        headers=admin_hdr,
    )
    assert c == 200 and resolved["status"] == "RESOLVED", resolved
    record("P11-P13", "PASS", "Late payment compensation and Admin reconciliation OPEN->IN_REVIEW->RESOLVED verified")

    # P14-P15: Signed webhook HMAC & RBAC on simulator
    c, _, _ = http_req("POST", f"/api/payments/simulate/{b2['booking_code']}", {"outcome": "SUCCEEDED"}, headers=cust_hdr)
    assert c == 403, f"Customer should be forbidden from simulator, got {c}"
    b5 = create_booking(cust_token, days_ahead=5)
    http_req("POST", "/api/payments/create", {"booking_code": b5["booking_code"]}, headers=cust_hdr)
    amt5 = int(round(b5["total_amount"]))
    tx5 = f"WH-{uuid.uuid4().hex[:6]}"
    c, _, _ = http_req(
        "POST",
        "/api/payments/webhook",
        {"booking_code": b5["booking_code"], "amount": amt5, "provider_tx_id": tx5},
        headers={"X-Webhook-Signature": "bad-sig"},
    )
    assert c == 401
    c, wh_ok, _ = http_req(
        "POST",
        "/api/payments/webhook",
        {"booking_code": b5["booking_code"], "amount": amt5, "provider_tx_id": tx5},
        headers={"X-Webhook-Signature": sign_webhook(b5["booking_code"], amt5, tx5)},
    )
    assert c == 200 and wh_ok["status"] == "SUCCEEDED"
    wait_booking_status(b5["booking_code"], "PAID", cust_hdr)
    record("P14-P15", "PASS", "RBAC simulator guard and signed webhook HMAC verification verified")

    # F01-F08: Cancellation Policy (>=24h 100%, 2..24h 50%, <2h 0% unless Admin exception)
    c, q_24h, _ = http_req("GET", f"/api/bookings/{b5['booking_code']}/cancellation-quote", headers=cust_hdr)
    assert c == 200 and q_24h["policy_tier"] == "FULL_24H" and q_24h["refund_percent"] == 100, q_24h

    # Cancel b5 (>=24h) -> 100% refund REQUESTED
    c, b5_cancelled, _ = http_req(
        "POST",
        f"/api/bookings/{b5['booking_code']}/cancel",
        {"reason": "Customer cancels >=24h"},
        headers=cust_hdr,
    )
    assert c == 200 and b5_cancelled["status"] == "CANCELLED", b5_cancelled
    b5_refunds = []
    for _ in range(15):
        c, b5_refunds, _ = http_req("GET", f"/api/payments/booking/{b5['booking_code']}/refunds", headers=cust_hdr)
        if c == 200 and len(b5_refunds) == 1:
            break
        time.sleep(0.4)
    assert c == 200 and len(b5_refunds) == 1 and b5_refunds[0]["status"] == "REQUESTED", b5_refunds
    assert b5_refunds[0]["requested_amount"] == int(round(b5["total_amount"])), b5_refunds[0]

    # Try 2h..24h booking (tomorrow at 21:00 if >2h away, else check quote tier)
    b6 = create_booking(cust_token, days_ahead=1, prefer_hour=21)
    http_req("POST", "/api/payments/create", {"booking_code": b6["booking_code"]}, headers=cust_hdr)
    http_req("POST", f"/api/payments/simulate/{b6['booking_code']}", {"outcome": "SUCCEEDED"}, headers=staff_hdr)
    wait_booking_status(b6["booking_code"], "PAID", cust_hdr)
    c, q_6, _ = http_req("GET", f"/api/bookings/{b6['booking_code']}/cancellation-quote", headers=cust_hdr)
    assert c == 200 and q_6["eligible"] is True, q_6

    # Admin exception requires reason
    c, _, _ = http_req(
        "POST",
        f"/api/bookings/admin/{b6['booking_code']}/cancel",
        {"reason": "no", "admin_exception": True, "override_refund_percent": 100},
        headers=admin_hdr,
    )
    assert c == 400
    c, b6_cancelled, _ = http_req(
        "POST",
        f"/api/bookings/admin/{b6['booking_code']}/cancel",
        {"reason": "Rainout court exception", "admin_exception": True, "override_refund_percent": 100},
        headers=admin_hdr,
    )
    assert c == 200 and b6_cancelled["status"] == "CANCELLED", b6_cancelled
    record("F01-F08", "PASS", "Deterministic cancellation policy tiers & admin exception reason enforcement verified")

    # F09-F16: Refund State Machine (Approve -> Execute FAILED -> Retry -> PROCESSING -> Callback SUCCEEDED; Reject; Over-refund race)
    rf_id = b5_refunds[0]["id"]
    c, rf_app, _ = http_req("POST", f"/api/payments/admin/refunds/{rf_id}/approve", {"note": "Approved"}, headers=admin_hdr)
    assert c == 200 and rf_app["status"] == "APPROVED", rf_app

    c, rf_fail, _ = http_req(
        "POST",
        f"/api/payments/admin/refunds/{rf_id}/execute",
        {"outcome": "FAILED", "failure_reason": "Bank simulator timeout"},
        headers=admin_hdr,
    )
    assert c == 200 and rf_fail["status"] == "FAILED", rf_fail

    c, rf_proc, _ = http_req(
        "POST",
        f"/api/payments/admin/refunds/{rf_id}/execute",
        {"outcome": "PROCESSING"},
        headers=admin_hdr,
    )
    assert c == 200 and rf_proc["status"] == "PROCESSING" and rf_proc["retry_count"] == 1, rf_proc

    cb_sig = sign_refund_callback(rf_proc["refund_code"], rf_proc["provider_refund_id"], "SUCCEEDED")
    c, rf_done, _ = http_req(
        "POST",
        "/api/payments/refunds/callback",
        {
            "refund_code": rf_proc["refund_code"],
            "provider_refund_id": rf_proc["provider_refund_id"],
            "outcome": "SUCCEEDED",
        },
        headers={"X-Webhook-Signature": cb_sig},
    )
    assert c == 200 and rf_done["status"] == "SUCCEEDED", rf_done

    # Concurrency-safe over-refund protection on b6
    b6_refunds = []
    for _ in range(15):
        c, b6_refunds, _ = http_req("GET", f"/api/payments/booking/{b6['booking_code']}/refunds", headers=cust_hdr)
        if c == 200 and len(b6_refunds) == 1:
            break
        time.sleep(0.4)
    assert c == 200 and len(b6_refunds) == 1, b6_refunds
    rf6_id = b6_refunds[0]["id"]
    c, rf6_rej, _ = http_req(
        "POST",
        f"/api/payments/admin/refunds/{rf6_id}/reject",
        {"rejection_reason": "Testing rejection then parallel over-refund"},
        headers=admin_hdr,
    )
    assert c == 200 and rf6_rej["status"] == "REJECTED"

    half_plus = int(round(b6["total_amount"] * 0.6))
    def _try_refund(_):
        return http_req(
            "POST",
            "/api/payments/admin/refunds",
            {
                "booking_code": b6["booking_code"],
                "requested_amount": half_plus,
                "policy_tier": "ADMIN_EXCEPTION",
                "policy_percent": 60,
                "reason": "Concurrent refund race test",
                "admin_override_reason": "Concurrent test",
            },
            headers=admin_hdr,
        )[0]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        statuses = list(ex.map(_try_refund, range(4)))
    assert statuses.count(201) == 1 and statuses.count(409) == 3, f"Expected 1x201 and 3x409, got {statuses}"
    record("F09-F16", "PASS", "Refund state machine, retry, callback, rejection, and concurrent over-refund protection verified")

    # F17-F20: Cancelled booking cannot check in + Checked-in booking cannot be cancelled
    b7 = create_booking(cust_token, days_ahead=4)
    http_req("POST", "/api/payments/create", {"booking_code": b7["booking_code"]}, headers=cust_hdr)
    http_req("POST", f"/api/payments/simulate/{b7['booking_code']}", {"outcome": "SUCCEEDED"}, headers=staff_hdr)
    wait_booking_status(b7["booking_code"], "PAID", cust_hdr)
    t7 = wait_ticket(b7["booking_code"], cust_hdr)

    # Cancel b7 and immediately attempt check-in (even before/during async revocation)
    c, _, _ = http_req("POST", f"/api/bookings/{b7['booking_code']}/cancel", {"reason": "Race checkin test"}, headers=cust_hdr)
    assert c == 200
    c, scan_cancelled, _ = http_req(
        "POST",
        "/api/checkin/scan",
        {"qr_data": t7["qr_payload"], "bypass_time_check": True},
        headers=staff_hdr,
    )
    assert c == 400, f"Cancelled booking check-in must fail, got {c} {scan_cancelled}"

    # Check in b1 (already PAID) then attempt cancel -> must be blocked 409
    t1 = wait_ticket(b1["booking_code"], cust_hdr)
    c, scan1, _ = http_req(
        "POST",
        "/api/checkin/scan",
        {"qr_data": t1["qr_payload"], "bypass_time_check": True},
        headers=staff_hdr,
    )
    assert c == 200 and scan1["valid"] is True, scan1
    c, cancel_checkedin, _ = http_req(
        "POST",
        f"/api/bookings/{b1['booking_code']}/cancel",
        {"reason": "Cancel after checkin"},
        headers=cust_hdr,
    )
    assert c == 409, f"Checked-in booking cancellation must be rejected (409), got {c} {cancel_checkedin}"
    record("F17-F20", "PASS", "Cancelled booking check-in guard and checked-in booking cancellation block verified")

    # F21-F22: Financial audit logs & Prometheus metrics
    c, audits, _ = http_req("GET", "/api/payments/admin/audit-logs", headers=admin_hdr)
    assert c == 200 and len(audits) >= 5, audits
    c, metrics_txt, _ = http_req("GET", "/metrics", base="http://localhost:18003")
    assert c == 200 and "pickleball_payments_confirmed_total" in str(metrics_txt)
    assert "pickleball_refunds_total" in str(metrics_txt)
    assert "pickleball_payment_reconciliation_cases_total" in str(metrics_txt)
    record("F21-F22", "PASS", "Financial audit logs and B02 Prometheus metrics verified")

    print("\n=== B02 FINANCIAL LIFECYCLE TEST SUMMARY ===")
    failed = [r for r in RESULTS if r[1] != "PASS"]
    for tid, st, msg in RESULTS:
        print(f"  {tid:10s} {st:4s} - {msg}")
    print(f"Total groups: {len(RESULTS)}, Passed: {len(RESULTS) - len(failed)}, Failed: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run_all())
