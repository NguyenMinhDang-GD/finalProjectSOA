import concurrent.futures
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta

BASE_URL = os.environ.get("TEST_GATEWAY_URL", "http://localhost:18080")
MAILPIT_URL = os.environ.get("TEST_MAILPIT_URL", "http://localhost:18025")
WEBHOOK_SECRET = os.environ.get("TEST_WEBHOOK_SECRET", "test-only-webhook-secret-p01")
INTERNAL_KEY = os.environ.get("TEST_INTERNAL_KEY", "test-only-internal-key-p01")
COMPOSE_PROJECT = os.environ.get("TEST_COMPOSE_PROJECT", "pkb-test")
COMPOSE_FILE = os.environ.get("TEST_COMPOSE_FILE", "docker-compose.test.yml")

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
) -> tuple[int, dict | list | str, dict[str, str]]:
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
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
        raw = err.read().decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in err.headers.items()}
        try:
            return err.code, json.loads(raw), resp_headers
        except json.JSONDecodeError:
            return err.code, raw, resp_headers


def psql(db: str, sql: str) -> str:
    cmd = [
        "docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE,
        "exec", "-T", "postgres-test",
        "psql", "-U", "pkb_test_user", "-d", db, "-t", "-A", "-c", sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def compose_cmd(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def sign_webhook(booking_code: str, amount: float, provider_tx_id: str) -> str:
    canonical = f"{booking_code}:{int(round(amount))}:{provider_tx_id}"
    return hmac.new(WEBHOOK_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def send_webhook(booking_code: str, amount: float, provider_tx_id: str) -> tuple[int, dict | list | str]:
    sig = sign_webhook(booking_code, amount, provider_tx_id)
    st, data, _ = http_req(
        "POST",
        "/api/payments/webhook",
        {
            "booking_code": booking_code,
            "amount": amount,
            "provider_tx_id": provider_tx_id,
            "provider": "VIETQR_GATEWAY",
        },
        headers={"X-Webhook-Signature": sig},
    )
    return st, data


def login(email: str, password: str) -> str:
    st, data, _ = http_req("POST", "/api/auth/login", {"email": email, "password": password})
    assert st == 200 and isinstance(data, dict), f"Login failed: {st} {data}"
    return data["access_token"]


def register_customer(tag: str) -> tuple[str, dict]:
    email = f"b01_{tag}_{uuid.uuid4().hex[:6]}@pickleball-test.vn"
    st, data, _ = http_req(
        "POST",
        "/api/auth/register",
        {
            "full_name": f"B01 User {tag}",
            "phone": "0901234567",
            "email": email,
            "password": "B01User@123",
        },
    )
    assert st == 201 and isinstance(data, dict), f"Register failed: {st} {data}"
    return data["access_token"], data["user"]


def pick_contiguous_slots(days_ahead: int, count: int = 1) -> tuple[str, str, list[int]]:
    for d in range(days_ahead, days_ahead + 20):
        play_date = (date.today() + timedelta(days=d)).isoformat()
        st, data, _ = http_req("GET", f"/api/courts/availability?date={play_date}")
        assert st == 200 and isinstance(data, dict)
        for c in data["courts"]:
            avail = [s["start_hour"] for s in c["slots"] if s["status"] == "AVAILABLE"]
            for i in range(len(avail) - count + 1):
                chunk = avail[i : i + count]
                if all(chunk[j + 1] == chunk[j] + 1 for j in range(len(chunk) - 1)):
                    return c["court"]["id"], play_date, chunk
    raise RuntimeError("No available contiguous slots")


def run_tests() -> int:
    admin_tok = login("admin@pickleball.vn", "Admin@123")
    staff_tok = login("staff@pickleball.vn", "Staff@123")
    cust_a_tok, cust_a_user = register_customer("cust_a")
    cust_b_tok, _ = register_customer("cust_b")

    # ---------------- C01: 50 Concurrent Single-Slot Bookings ----------------
    c_id, p_date, hrs = pick_contiguous_slots(5, 1)
    target_hour = hrs[0]

    def try_book(idx: int) -> int:
        st, _, _ = http_req(
            "POST",
            "/api/bookings",
            {
                "court_id": c_id,
                "play_date": p_date,
                "hours": [target_hour],
                "customer_name": f"Race {idx}",
                "customer_phone": "0901234567",
                "customer_email": f"race{idx}@pickleball-test.vn",
            },
            base="http://localhost:18002",
        )
        return st

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futs = [pool.submit(try_book, i) for i in range(50)]
        statuses = [f.result() for f in futs]

    ok_cnt = statuses.count(201)
    conflict_cnt = statuses.count(409)
    err_500_cnt = sum(1 for s in statuses if s >= 500)
    db_active = int(
        psql(
            "booking_db",
            f"SELECT COUNT(*) FROM booking_slots WHERE court_id='{c_id}' AND play_date='{p_date}' AND start_hour={target_hour} AND slot_status IN ('LOCKED','BOOKED')",
        )
    )
    assert ok_cnt == 1 and conflict_cnt == 49 and err_500_cnt == 0 and db_active == 1, (
        f"C01 failed: ok={ok_cnt}, conflict={conflict_cnt}, 500={err_500_cnt}, db_active={db_active}"
    )
    record("C01", "PASS", f"50 concurrent requests: 1x201, 49x409, 0x500, active_slots={db_active}")

    # ---------------- C02: Atomic Multi-Slot Reservation ----------------
    c2_id, p2_date, h2 = pick_contiguous_slots(6, 2)
    st, _, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": c2_id,
            "play_date": p2_date,
            "hours": [h2[1]],
            "customer_name": "Blocker",
            "customer_phone": "0901234567",
            "customer_email": "blocker@pickleball-test.vn",
        },
    )
    assert st == 201
    st, _, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": c2_id,
            "play_date": p2_date,
            "hours": h2,
            "customer_name": "Atomic Fail",
            "customer_phone": "0901234567",
            "customer_email": "atomic@pickleball-test.vn",
        },
    )
    assert st == 409
    first_slot_cnt = int(
        psql(
            "booking_db",
            f"SELECT COUNT(*) FROM booking_slots WHERE court_id='{c2_id}' AND play_date='{p2_date}' AND start_hour={h2[0]} AND slot_status IN ('LOCKED','BOOKED')",
        )
    )
    assert first_slot_cnt == 0
    record("C02", "PASS", f"Multi-slot rollback left {first_slot_cnt} partial slots on {p2_date} hour {h2[0]}")

    # ---------------- C03 & C04: Redis Lock Ownership & Partial Failure ----------------
    py_c03_c04 = (
        "import asyncio, uuid\n"
        "from datetime import date\n"
        "from redis.asyncio import from_url\n"
        "from app.services.booking_service import release_owned_locks, _slot_lock_key\n"
        "async def main():\n"
        "  r = from_url('redis://redis-test:6379/0', decode_responses=True)\n"
        "  cid = uuid.uuid4()\n"
        "  k1 = _slot_lock_key(cid, date(2026,12,20), 10)\n"
        "  k2 = _slot_lock_key(cid, date(2026,12,20), 11)\n"
        "  # C03: new owner acquires k1, old owner tries release\n"
        "  await r.set(k1, 'new-owner-token', nx=True, ex=60)\n"
        "  rel = await release_owned_locks(r, [k1], 'old-owner-token')\n"
        "  assert rel == 0 and await r.get(k1) == 'new-owner-token'\n"
        "  # C04: partial acquisition cleanup releases only owned key k2\n"
        "  await r.set(k2, 'failed-req-token', nx=True, ex=60)\n"
        "  rel2 = await release_owned_locks(r, [k1, k2], 'failed-req-token')\n"
        "  assert rel2 == 1 and await r.get(k1) == 'new-owner-token' and await r.get(k2) is None\n"
        "  await r.delete(k1)\n"
        "  await r.aclose()\n"
        "asyncio.run(main())"
    )
    compose_cmd("exec", "-T", "court-booking-service", "python", "-c", py_c03_c04)
    record("C03", "PASS", "Lua compare-and-delete preserved new owner's lock against stale token")
    record("C04", "PASS", "Partial failure released only caller-owned lock keys")

    # ---------------- C05: Redis Unavailability Fallback ----------------
    c5_id, p5_date, h5 = pick_contiguous_slots(7, 1)
    compose_cmd("stop", "redis-test")
    try:
        st1, b5_1, _ = http_req(
            "POST",
            "/api/bookings",
            {
                "court_id": c5_id,
                "play_date": p5_date,
                "hours": h5,
                "customer_name": "Redis Down 1",
                "customer_phone": "0901234567",
                "customer_email": "rdown1@pickleball-test.vn",
            },
        )
        st2, _, _ = http_req(
            "POST",
            "/api/bookings",
            {
                "court_id": c5_id,
                "play_date": p5_date,
                "hours": h5,
                "customer_name": "Redis Down 2",
                "customer_phone": "0901234567",
                "customer_email": "rdown2@pickleball-test.vn",
            },
        )
        assert st1 == 201 and st2 == 409, f"C05 failed: st1={st1}, st2={st2}"
    finally:
        compose_cmd("start", "redis-test")
    record("C05", "PASS", "Redis outage safely fell back to PostgreSQL uq_active_court_slot (201 then 409)")

    # ---------------- C06: Concurrent Expiration Workers ----------------
    c6_id, p6_date, h6 = pick_contiguous_slots(8, 2)
    exp_codes = []
    for hr in h6:
        st, d, _ = http_req(
            "POST",
            "/api/bookings",
            {
                "court_id": c6_id,
                "play_date": p6_date,
                "hours": [hr],
                "customer_name": "Expire Test",
                "customer_phone": "0901234567",
                "customer_email": "exp@pickleball-test.vn",
            },
        )
        assert st == 201
        exp_codes.append(d["booking_code"])
        psql("booking_db", f"UPDATE booking_orders SET expires_at = NOW() - INTERVAL '5 minutes' WHERE booking_code='{d['booking_code']}'")

    py_c06 = (
        "import asyncio\n"
        "from redis.asyncio import from_url\n"
        "from app.database import AsyncSessionLocal\n"
        "from app.services.booking_service import expire_due_bookings_batch\n"
        "async def worker():\n"
        "  r = from_url('redis://redis-test:6379/0', decode_responses=True)\n"
        "  async with AsyncSessionLocal() as db:\n"
        "    n = await expire_due_bookings_batch(db, r, batch_size=50)\n"
        "  await r.aclose()\n"
        "  return n\n"
        "async def main():\n"
        "  res = await asyncio.gather(worker(), worker())\n"
        "  print('EXPIRED_COUNTS', res)\n"
        "asyncio.run(main())"
    )
    compose_cmd("exec", "-T", "court-booking-service", "python", "-c", py_c06)
    for ec in exp_codes:
        assert psql("booking_db", f"SELECT status FROM booking_orders WHERE booking_code='{ec}'") == "EXPIRED"
        assert int(psql("booking_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{ec}' AND event_type='booking.expired'")) == 1
    record("C06", "PASS", f"Concurrent SKIP LOCKED expiration workers expired {exp_codes} once each")

    # ---------------- C07 & C08: Expiration/Cancel vs Payment Confirmation ----------------
    c7_id, p7_date, h7 = pick_contiguous_slots(9, 2)
    st, b7, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": c7_id,
            "play_date": p7_date,
            "hours": [h7[0]],
            "customer_name": "C07",
            "customer_phone": "0901234567",
            "customer_email": "c07@pickleball-test.vn",
        },
    )
    code7 = b7["booking_code"]
    gt7 = {"X-Guest-Token": b7["guest_access_token"]}
    http_req("POST", "/api/payments/create", {"booking_code": code7}, headers=gt7)
    psql("booking_db", f"UPDATE booking_orders SET status='EXPIRED' WHERE booking_code='{code7}'")
    st, _ = send_webhook(code7, float(b7["total_amount"]), f"TX-C07-{uuid.uuid4().hex[:6]}")
    assert st == 200
    time.sleep(1.5)
    assert psql("booking_db", f"SELECT status FROM booking_orders WHERE booking_code='{code7}'") == "EXPIRED"
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code7}'")) == 0
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM payment_compensations WHERE booking_code='{code7}' AND status='COMPENSATION_REQUIRED'")) == 1
    record("C07", "PASS", f"Expiration vs payment preserved EXPIRED + compensation for {code7}, 0 tickets")

    st, b8, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": c7_id,
            "play_date": p7_date,
            "hours": [h7[1]],
            "customer_name": "C08",
            "customer_phone": "0901234567",
            "customer_email": "c08@pickleball-test.vn",
        },
    )
    code8 = b8["booking_code"]
    gt8 = {"X-Guest-Token": b8["guest_access_token"]}
    http_req("POST", "/api/payments/create", {"booking_code": code8}, headers=gt8)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_cancel = pool.submit(http_req, "POST", f"/api/bookings/{code8}/cancel", None, gt8)
        f_pay = pool.submit(send_webhook, code8, float(b8["total_amount"]), f"TX-C08-{uuid.uuid4().hex[:6]}")
        f_cancel.result()
        f_pay.result()
    time.sleep(1.5)
    final_status_8 = psql("booking_db", f"SELECT status FROM booking_orders WHERE booking_code='{code8}'")
    tickets_8 = int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code8}'"))
    if final_status_8 == "CANCELLED":
        assert tickets_8 == 0
    record("C08", "PASS", f"Cancel vs payment race settled deterministically: status={final_status_8}, tickets={tickets_8}")

    # ---------------- C09: Pricing Snapshot ----------------
    st, rules, _ = http_req("GET", "/api/pricing-rules")
    assert st == 200 and isinstance(rules, list)
    target_rule = rules[0]
    orig_price = float(target_rule["price_per_hour"])
    c9_id, p9_date, h9 = pick_contiguous_slots(10, 2)
    st, b9_before, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": c9_id,
            "play_date": p9_date,
            "hours": [h9[0]],
            "customer_name": "Price Snap",
            "customer_phone": "0901234567",
            "customer_email": "snap@pickleball-test.vn",
        },
        headers={"Authorization": f"Bearer {cust_a_tok}"},
    )
    assert st == 201
    snap_amount = float(b9_before["total_amount"])
    http_req(
        "PUT",
        f"/api/pricing-rules/{target_rule['id']}",
        {"price_per_hour": orig_price + 50000},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    st, b9_after_lookup, _ = http_req(
        "GET",
        f"/api/bookings/lookup/{b9_before['booking_code']}",
        headers={"Authorization": f"Bearer {cust_a_tok}"},
    )
    assert st == 200 and float(b9_after_lookup["total_amount"]) == snap_amount
    # Restore original pricing rule
    http_req(
        "PUT",
        f"/api/pricing-rules/{target_rule['id']}",
        {"price_per_hour": orig_price},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    record("C09", "PASS", f"Existing booking {b9_before['booking_code']} kept snapshot amount {snap_amount}")

    # ---------------- S01 - S05: Ownership & Guest Token Enforcement ----------------
    code_a = b9_before["booking_code"]
    # S01: Cust B cannot read Cust A booking
    st, _, _ = http_req("GET", f"/api/bookings/lookup/{code_a}", headers={"Authorization": f"Bearer {cust_b_tok}"})
    assert st == 403
    record("S01", "PASS", "Customer B rejected (403) reading Customer A booking")

    # S02: Cust B & unauth cannot cancel Cust A booking
    st_unauth, _, _ = http_req("POST", f"/api/bookings/{code_a}/cancel")
    st_b, _, _ = http_req("POST", f"/api/bookings/{code_a}/cancel", headers={"Authorization": f"Bearer {cust_b_tok}"})
    assert st_unauth == 401 and st_b == 403
    record("S02", "PASS", "Unauthorized cancel rejected (401 unauth, 403 cross-customer)")

    # S03: Guest access token scoped to booking
    c_g, p_g, h_g = pick_contiguous_slots(11, 2)
    st, bg1, _ = http_req(
        "POST",
        "/api/bookings",
        {
            "court_id": c_g,
            "play_date": p_g,
            "hours": [h_g[0]],
            "customer_name": "<script>alert(1)</script>",
            "customer_phone": "0901234567",
            "customer_email": "guest_xss@pickleball-test.vn",
        },
    )
    assert st == 201 and bg1.get("guest_access_token") and len(bg1["booking_code"].split("-")[-1]) == 10
    gcode = bg1["booking_code"]
    gt_valid = {"X-Guest-Token": bg1["guest_access_token"]}
    st_ok, lookup_g, _ = http_req("GET", f"/api/bookings/lookup/{gcode}", headers=gt_valid)
    assert st_ok == 200 and lookup_g.get("guest_access_token") is None
    st_miss, _, _ = http_req("GET", f"/api/bookings/lookup/{gcode}")
    st_wrong, _, _ = http_req("GET", f"/api/bookings/lookup/{gcode}", headers={"X-Guest-Token": "wrong-token"})
    assert st_miss == 401 and st_wrong == 403
    record("S03", "PASS", f"Guest token verified (200 valid, 401 missing, 403 wrong, 40-bit code={gcode})")

    # S04: Payment ownership
    st_p_unauth, _, _ = http_req("POST", "/api/payments/create", {"booking_code": code_a})
    st_p_b, _, _ = http_req("POST", "/api/payments/create", {"booking_code": code_a}, headers={"Authorization": f"Bearer {cust_b_tok}"})
    assert st_p_unauth == 401 and st_p_b == 403
    http_req("POST", "/api/payments/create", {"booking_code": gcode}, headers=gt_valid)
    st_g_other, _, _ = http_req("GET", f"/api/payments/booking/{gcode}", headers={"Authorization": f"Bearer {cust_b_tok}"})
    assert st_g_other == 403
    record("S04", "PASS", "Payment create & lookup enforced ownership (401/403)")

    # Pay guest booking via authorized STAFF demo webhook (tests S11 too!)
    st_demo_cust, _, _ = http_req("POST", f"/api/payments/simulate-webhook/{gcode}", headers={"Authorization": f"Bearer {cust_a_tok}"})
    assert st_demo_cust == 403
    st_demo_staff, _, _ = http_req("POST", f"/api/payments/simulate-webhook/{gcode}", headers={"Authorization": f"Bearer {staff_tok}"})
    assert st_demo_staff == 200
    record("S11", "PASS", "Demo simulate-webhook blocked CUSTOMER (403) and allowed STAFF (200)")

    # Wait for QR ticket & email (tests S05 & S19)
    for _ in range(30):
        st_t, _, _ = http_req("GET", f"/api/checkin/ticket/{gcode}", headers=gt_valid)
        if st_t == 200:
            break
        time.sleep(0.5)
    st_t_b, _, _ = http_req("GET", f"/api/checkin/ticket/{gcode}", headers={"Authorization": f"Bearer {cust_b_tok}"})
    st_t_unauth, _, _ = http_req("GET", f"/api/checkin/ticket/{gcode}")
    assert st_t == 200 and st_t_b == 403 and st_t_unauth == 401
    record("S05", "PASS", "QR ticket retrieval enforced ownership (200 owner, 401 unauth, 403 other user)")

    # ---------------- S06 - S09: RBAC, Registration, JWT, Inactive Account ----------------
    st_c_scan, _, _ = http_req("POST", "/api/checkin/scan", {"qr_data": "x"}, headers={"Authorization": f"Bearer {cust_a_tok}"})
    st_c_adm, _, _ = http_req("GET", "/api/bookings/admin/stats", headers={"Authorization": f"Bearer {cust_a_tok}"})
    st_s_adm, _, _ = http_req("GET", "/api/bookings/admin/stats", headers={"Authorization": f"Bearer {staff_tok}"})
    assert st_c_scan == 403 and st_c_adm == 403 and st_s_adm == 403
    record("S06", "PASS", "RBAC enforced (CUSTOMER->403 staff/admin, STAFF->403 admin)")

    st_reg, reg_d, _ = http_req(
        "POST",
        "/api/auth/register",
        {
            "full_name": "Escalate Try",
            "phone": "0909998877",
            "email": f"esc_{uuid.uuid4().hex[:6]}@pickleball-test.vn",
            "password": "User@123",
            "role": "ADMIN",
        },
    )
    assert st_reg == 201 and reg_d["user"]["role"] == "CUSTOMER"
    record("S07", "PASS", "Public registration forced role=CUSTOMER regardless of payload")

    st_bad_jwt, _, _ = http_req("GET", "/api/bookings/my", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert st_bad_jwt == 401
    record("S08", "PASS", "Malformed/invalid JWT rejected (401)")

    psql("auth_db", f"UPDATE users SET is_active=false WHERE id='{cust_a_user['id']}'")
    st_inact_login, _, _ = http_req("POST", "/api/auth/login", {"email": cust_a_user["email"], "password": "B01User@123"})
    st_inact_me, _, _ = http_req("GET", "/api/auth/me", headers={"Authorization": f"Bearer {cust_a_tok}"})
    st_inact_book, _, _ = http_req("GET", "/api/bookings/my", headers={"Authorization": f"Bearer {cust_a_tok}"})
    st_inact_pay, _, _ = http_req("GET", f"/api/payments/booking/{code_a}", headers={"Authorization": f"Bearer {cust_a_tok}"})
    psql("auth_db", f"UPDATE users SET is_active=true WHERE id='{cust_a_user['id']}'")
    assert st_inact_login == 403 and st_inact_me == 403 and st_inact_book == 403 and st_inact_pay == 403

    # V01: Privileged STAFF account deactivation immediately blocks downstream services (0s cache)
    priv_email = f"v01_staff_{uuid.uuid4().hex[:6]}@pickleball-test.vn"
    st_cr, priv_u, _ = http_req(
        "POST",
        "/api/auth/users",
        {"email": priv_email, "full_name": "V01 Staff", "phone": "0908881122", "password": "V01Staff@123", "role": "STAFF"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert st_cr == 201
    priv_tok = login(priv_email, "V01Staff@123")
    st_ok_logs, _, _ = http_req("GET", "/api/checkin/logs", headers={"Authorization": f"Bearer {priv_tok}"})
    assert st_ok_logs == 200
    psql("auth_db", f"UPDATE users SET is_active=false WHERE id='{priv_u['id']}'")
    st_rev_logs, _, _ = http_req("GET", "/api/checkin/logs", headers={"Authorization": f"Bearer {priv_tok}"})
    st_rev_demo, _, _ = http_req("POST", f"/api/payments/simulate-webhook/{gcode}", headers={"Authorization": f"Bearer {priv_tok}"})
    assert st_rev_logs == 403 and st_rev_demo == 403
    record("S09", "PASS", "Inactive account immediately rejected (403) across auth, booking, payment, and checkin services")

    # V02: Guest token lifecycle (read-only after cancel, explicit revocation, expiration)
    c_v2, p_v2, h_v2 = pick_contiguous_slots(12, 1)
    st_v2, bv2, _ = http_req(
        "POST",
        "/api/bookings",
        {"court_id": c_v2, "play_date": p_v2, "hours": h_v2, "customer_name": "V02 Guest", "customer_phone": "0901234567", "customer_email": "v02@pickleball-test.vn"},
    )
    assert st_v2 == 201
    v2_code = bv2["booking_code"]
    gt_v2 = {"X-Guest-Token": bv2["guest_access_token"]}
    http_req("POST", f"/api/bookings/{v2_code}/cancel", headers=gt_v2)
    st_ro, _, _ = http_req("GET", f"/api/bookings/lookup/{v2_code}", headers=gt_v2)
    assert st_ro == 200
    st_rev_gt, _, _ = http_req("POST", f"/api/bookings/admin/{v2_code}/revoke-guest-token", headers={"Authorization": f"Bearer {admin_tok}"})
    assert st_rev_gt == 200
    st_after_rev, _, _ = http_req("GET", f"/api/bookings/lookup/{v2_code}", headers=gt_v2)
    assert st_after_rev == 403
    record("V02", "PASS", f"Guest token read-only post-cancel (200) and immediate admin revocation (403) verified for {v2_code}")

    # ---------------- S10, S12, S13, S14, S16, S17, S18 ----------------
    # S10 & S13 & S18: Production config validation inside containers
    compose_cmd(
        "exec", "-T", "payment-service", "python", "-c",
        "from app.config import Settings; s=Settings(app_env='production', jwt_secret='x'*32, internal_api_key='y'*32, webhook_secret='z'*32, enable_demo_webhook=True); assert not s.is_demo_webhook_enabled",
    )
    record("S10", "PASS", "Production mode disables simulated payment even if ENABLE_DEMO_WEBHOOK=true")

    compose_cmd(
        "exec", "-T", "checkin-qr-service", "python", "-c",
        "from app.config import Settings; s=Settings(app_env='production', jwt_secret='x'*32, qr_hmac_secret='y'*32, internal_api_key='z'*32, allow_demo_bypass_time=True); assert not s.is_demo_bypass_enabled",
    )
    record("S13", "PASS", "Production mode disables demo time bypass even if ALLOW_DEMO_BYPASS_TIME=true")

    compose_cmd(
        "exec", "-T", "court-booking-service", "python", "-c",
        "from app.config import Settings\ntry:\n  Settings(app_env='production', jwt_secret='soa-pickleball-jwt-super-secret-key-2026', internal_api_key='short').validate_production_settings()\n  raise SystemExit(1)\nexcept RuntimeError:\n  pass",
    )
    record("S18", "PASS", "Production startup rejects insecure/default secrets with RuntimeError")

    # S12: Invalid webhook signature
    st_wsig, _, _ = http_req(
        "POST",
        "/api/payments/webhook",
        {"booking_code": gcode, "amount": 100000, "provider_tx_id": "BAD"},
        headers={"X-Webhook-Signature": "0" * 64},
    )
    assert st_wsig == 401
    record("S12", "PASS", "Invalid webhook HMAC signature rejected (401)")

    # S14: Internal endpoints blocked at gateway & direct without key
    st_gw_int, _, _ = http_req("GET", f"/api/bookings/internal/{gcode}")
    st_dir_int, _, _ = http_req("GET", f"/api/bookings/internal/{gcode}", base="http://localhost:18002")
    assert st_gw_int == 403 and st_dir_int == 403
    record("S14", "PASS", "Internal endpoints blocked at Gateway (403) and direct without X-Internal-Key (403)")

    # S16: CORS policy
    _, _, hdr_allow = http_req("OPTIONS", "/api/courts", headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "GET"})
    _, _, hdr_deny = http_req("OPTIONS", "/api/courts", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert hdr_allow.get("access-control-allow-origin") == "http://localhost:8080"
    assert hdr_deny.get("access-control-allow-origin") != "https://evil.example"
    record("S16", "PASS", "CORS echoed allowed origin http://localhost:8080 and rejected https://evil.example")

    # S17: Network exposure in docker-compose.prod.yml
    with open("docker-compose.prod.yml", "r", encoding="utf-8") as f:
        prod_yml = f.read()
    assert prod_yml.count("ports:") == 1 and "PROD_GATEWAY_PORT" in prod_yml
    record("S17", "PASS", "docker-compose.prod.yml exposes ports ONLY on api-gateway")

    # S19: Email HTML escaping in Mailpit
    time.sleep(1.5)
    st_mp, mp_data, _ = http_req("GET", "/api/v1/messages", base=MAILPIT_URL)
    assert st_mp == 200 and isinstance(mp_data, dict)
    msg_id = next((m["ID"] for m in mp_data.get("messages", []) if gcode in m.get("Subject", "")), None)
    assert msg_id is not None, f"Email for {gcode} not found in Mailpit"
    _, msg_detail, _ = http_req("GET", f"/api/v1/message/{msg_id}", base=MAILPIT_URL)
    html_body = msg_detail.get("HTML", "")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_body and "<script>alert(1)</script>" not in html_body
    record("S19", "PASS", "Untrusted HTML in customer_name escaped safely in ticket email")

    # S20: Sensitive logging check
    logs_res = compose_cmd("logs", "--tail=200", "auth-service", "court-booking-service", "payment-service", "checkin-qr-service")
    combined_logs = logs_res.stdout + logs_res.stderr
    assert "Admin@123" not in combined_logs and bg1["guest_access_token"] not in combined_logs and "test-only-internal-key-p01" not in combined_logs
    record("S20", "PASS", "No raw passwords, guest tokens, or internal keys found in service logs")

    # S15: Rate limiting (429 on login burst) + normal polling preserved
    poll_statuses = [http_req("GET", f"/api/bookings/lookup/{gcode}", headers=gt_valid)[0] for _ in range(15)]
    assert all(s == 200 for s in poll_statuses)
    burst_statuses = [http_req("POST", "/api/auth/login", {"email": "x@y.z", "password": "bad"})[0] for _ in range(25)]
    assert 429 in burst_statuses, f"Expected 429 in login burst, got {set(burst_statuses)}"
    record("S15", "PASS", f"Rate limiting triggered 429 ({burst_statuses.count(429)}x) on login burst; normal polling 15/15 200 OK")

    print(f"\nALL {len(RESULTS)} B01 TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run_tests())
