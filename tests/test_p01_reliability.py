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
RMQ_MGMT_URL = os.environ.get("TEST_RMQ_MGMT_URL", "http://localhost:25672")
WEBHOOK_SECRET = os.environ.get("TEST_WEBHOOK_SECRET", "test-only-webhook-secret-p01")
COMPOSE_PROJECT = os.environ.get("TEST_COMPOSE_PROJECT", "pkb-test")
COMPOSE_FILE = os.environ.get("TEST_COMPOSE_FILE", "docker-compose.test.yml")

RESULTS: list[tuple[str, str, str]] = []


def record(test_id: str, status: str, detail: str) -> None:
    RESULTS.append((test_id, status, detail))
    print(f"[{status}] {test_id}: {detail}", flush=True)


def http_json(method: str, path: str, body: dict | None = None, headers: dict | None = None, base: str = BASE_URL) -> tuple[int, dict | list | str]:
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            return err.code, json.loads(raw)
        except json.JSONDecodeError:
            return err.code, raw


def rmq_api_get(path: str) -> dict:
    import base64
    auth = base64.b64encode(b"guest:guest").decode("ascii")
    status, data = http_json("GET", path, headers={"Authorization": f"Basic {auth}"}, base=RMQ_MGMT_URL)
    assert status == 200, f"RMQ API {path} returned {status}: {data}"
    assert isinstance(data, dict)
    return data


def psql(db: str, sql: str) -> str:
    cmd = [
        "docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE,
        "exec", "-T", "postgres-test",
        "psql", "-U", "pkb_test_user", "-d", db, "-t", "-A", "-c", sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def compose_cmd(*args: str) -> None:
    cmd = ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, *args]
    subprocess.run(cmd, check=True)


def publish_rmq_raw(routing_key: str, raw_body: str) -> None:
    py = (
        "import asyncio, aio_pika\n"
        "async def main():\n"
        "  conn = await aio_pika.connect_robust('amqp://guest:guest@rabbitmq-test:5672/')\n"
        "  ch = await conn.channel()\n"
        "  ex = await ch.declare_exchange('pickleball.events', aio_pika.ExchangeType.TOPIC, durable=True)\n"
        f"  await ex.publish(aio_pika.Message(body={raw_body.encode('utf-8')!r}, content_type='application/json'), routing_key={routing_key!r})\n"
        "  await conn.close()\n"
        "asyncio.run(main())"
    )
    subprocess.run(
        ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, "exec", "-T", "payment-service", "python", "-c", py],
        check=True,
    )


def sign_webhook(booking_code: str, amount: float, provider_tx_id: str) -> str:
    canonical = f"{booking_code}:{int(round(amount))}:{provider_tx_id}"
    return hmac.new(WEBHOOK_SECRET.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def login(email: str, password: str) -> str:
    code, data = http_json("POST", "/api/auth/login", {"email": email, "password": password})
    assert code == 200 and isinstance(data, dict), f"Login failed: {code} {data}"
    return data["access_token"]


def pick_available_slot(hour_offset: int = 0) -> tuple[str, str, int]:
    for day_add in range(2 + (hour_offset // 12), 14):
        play_date = (date.today() + timedelta(days=day_add)).isoformat()
        code, data = http_json("GET", f"/api/courts/availability?date={play_date}")
        assert code == 200 and isinstance(data, dict), f"Availability failed: {code} {data}"
        for court_item in data["courts"]:
            for slot in court_item["slots"]:
                if slot["status"] == "AVAILABLE":
                    return court_item["court"]["id"], play_date, slot["start_hour"]
    raise RuntimeError(f"No available slot for offset={hour_offset}")


def create_booking(hour_offset: int) -> dict:
    court_id, play_date, hour = pick_available_slot(hour_offset)
    code, data = http_json(
        "POST",
        "/api/bookings",
        {
            "court_id": court_id,
            "play_date": play_date,
            "hours": [hour],
            "customer_name": f"Test User {hour_offset}",
            "customer_phone": "0901234567",
            "customer_email": f"test{hour_offset}@pickleball-test.vn",
        },
    )
    assert code == 201 and isinstance(data, dict), f"Create booking failed: {code} {data}"
    return data


def send_webhook(booking_code: str, amount: float, provider_tx_id: str) -> tuple[int, dict | list | str]:
    sig = sign_webhook(booking_code, amount, provider_tx_id)
    return http_json(
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


def wait_until(predicate, timeout: float = 20.0, interval: float = 0.5, msg: str = "condition"):
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            res = predicate()
            if res:
                return res
        except Exception as exc:
            last_err = exc
        time.sleep(interval)
    raise AssertionError(f"Timeout waiting for {msg} (last_err={last_err})")


def run_tests() -> int:
    # T01: Happy Path
    b1 = create_booking(0)
    code1 = b1["booking_code"]
    gt1 = {"X-Guest-Token": b1["guest_access_token"]}
    amt1 = float(b1["total_amount"])
    st, _ = http_json("POST", "/api/payments/create", {"booking_code": code1}, headers=gt1)
    assert st == 201
    tx1 = f"TX-T01-{uuid.uuid4().hex[:8]}"
    st, _ = send_webhook(code1, amt1, tx1)
    assert st == 200

    wait_until(
        lambda: http_json("GET", f"/api/bookings/lookup/{code1}", headers=gt1)[1].get("status") == "PAID",
        msg="T01 booking PAID",
    )
    ticket1 = wait_until(
        lambda: http_json("GET", f"/api/checkin/ticket/{code1}", headers=gt1)[0] == 200
        and http_json("GET", f"/api/checkin/ticket/{code1}", headers=gt1)[1],
        msg="T01 ticket issued",
    )
    assert ticket1["status"] == "VALID"
    wait_until(
        lambda: int(psql("notification_db", f"SELECT COUNT(*) FROM notification_logs WHERE booking_code='{code1}' AND status='SENT'")) == 1,
        msg="T01 email SENT",
    )
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code1}' AND status='PUBLISHED'")) == 1
    assert int(psql("booking_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='booking.confirmed' AND status='PUBLISHED'")) == 1
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='ticket.issued' AND status='PUBLISHED'")) == 1
    record("T01", "PASS", f"Happy path verified for {code1}")

    # T02: Duplicate Payment Callback
    for _ in range(3):
        st, _ = send_webhook(code1, amt1, tx1)
        assert st == 200
    time.sleep(1.5)
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM payment_transactions WHERE booking_code='{code1}' AND status='SUCCEEDED'")) == 1
    assert int(psql("booking_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='booking.confirmed'")) == 1
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code1}'")) == 1
    record("T02", "PASS", f"Duplicate callbacks idempotent for {code1}")

    # T03: Concurrent Payment Callbacks
    b3 = create_booking(1)
    code3 = b3["booking_code"]
    amt3 = float(b3["total_amount"])
    tx3 = f"TX-T03-{uuid.uuid4().hex[:8]}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(send_webhook, code3, amt3, tx3) for _ in range(5)]
        statuses = [f.result()[0] for f in futs]
    assert all(s == 200 for s in statuses), f"T03 statuses: {statuses}"
    wait_until(lambda: int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code3}'")) == 1, msg="T03 ticket")
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM payment_transactions WHERE booking_code='{code3}' AND status='SUCCEEDED'")) == 1
    assert int(psql("booking_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code3}' AND event_type='booking.confirmed'")) == 1
    record("T03", "PASS", f"5 concurrent callbacks produced 1 payment, 1 confirmation, 1 ticket for {code3}")

    # T04: Duplicate Booking Confirmation Event
    confirmed_payload = psql("booking_db", f"SELECT payload::text FROM outbox_events WHERE aggregate_id='{code3}' AND event_type='booking.confirmed' LIMIT 1")
    publish_rmq_raw("booking.confirmed", confirmed_payload)
    publish_rmq_raw("booking.confirmed", confirmed_payload)
    time.sleep(1.5)
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code3}'")) == 1
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code3}' AND event_type='ticket.issued'")) == 1
    record("T04", "PASS", f"Duplicate booking.confirmed produced 1 ticket for {code3}")

    # T05: Payment Success Without Booking Confirmation
    b5 = create_booking(2)
    code5 = b5["booking_code"]
    gt5 = {"X-Guest-Token": b5["guest_access_token"]}
    amt5 = float(b5["total_amount"])
    http_json("POST", "/api/payments/create", {"booking_code": code5}, headers=gt5)
    psql("booking_db", f"UPDATE booking_orders SET status='CANCELLED' WHERE booking_code='{code5}'")
    tx5 = f"TX-T05-{uuid.uuid4().hex[:8]}"
    st, _ = send_webhook(code5, amt5, tx5)
    assert st == 200
    wait_until(
        lambda: int(psql("payment_db", f"SELECT COUNT(*) FROM payment_compensations WHERE booking_code='{code5}' AND status='COMPENSATION_REQUIRED'")) == 1,
        msg="T05 payment compensation",
    )
    assert psql("booking_db", f"SELECT status FROM booking_orders WHERE booking_code='{code5}'") == "CANCELLED"
    assert int(psql("booking_db", f"SELECT COUNT(*) FROM booking_compensations WHERE booking_code='{code5}' AND status='COMPENSATION_REQUIRED'")) == 1
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code5}'")) == 0
    record("T05", "PASS", f"Confirmation failure preserved funds & flagged compensation without ticket for {code5}")

    # T06: RabbitMQ Unavailable During Payment Persistence
    b6 = create_booking(3)
    code6 = b6["booking_code"]
    gt6 = {"X-Guest-Token": b6["guest_access_token"]}
    amt6 = float(b6["total_amount"])
    http_json("POST", "/api/payments/create", {"booking_code": code6}, headers=gt6)
    compose_cmd("stop", "rabbitmq-test")
    tx6 = f"TX-T06-{uuid.uuid4().hex[:8]}"
    st, _ = send_webhook(code6, amt6, tx6)
    assert st == 200
    assert psql("payment_db", f"SELECT status FROM payment_transactions WHERE booking_code='{code6}'") == "SUCCEEDED"
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code6}' AND status='PENDING'")) == 1
    compose_cmd("start", "rabbitmq-test")
    wait_until(
        lambda: http_json("GET", f"/api/checkin/ticket/{code6}", headers=gt6)[0] == 200,
        timeout=75.0,
        msg="T06 recovery after RMQ restore",
    )
    assert psql("payment_db", f"SELECT status FROM outbox_events WHERE aggregate_id='{code6}'") == "PUBLISHED"
    record("T06", "PASS", f"Outbox persisted during RMQ outage and recovered for {code6}")

    # T07: Outbox Dispatcher Restart
    b7 = create_booking(4)
    code7 = b7["booking_code"]
    gt7 = {"X-Guest-Token": b7["guest_access_token"]}
    amt7 = float(b7["total_amount"])
    http_json("POST", "/api/payments/create", {"booking_code": code7}, headers=gt7)
    compose_cmd("stop", "rabbitmq-test")
    tx7 = f"TX-T07-{uuid.uuid4().hex[:8]}"
    st, _ = send_webhook(code7, amt7, tx7)
    assert st == 200
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code7}' AND status='PENDING'")) == 1
    compose_cmd("restart", "payment-service")
    compose_cmd("start", "rabbitmq-test")
    wait_until(
        lambda: http_json("GET", f"/api/checkin/ticket/{code7}", headers=gt7)[0] == 200,
        timeout=75.0,
        msg="T07 recovery after payment-service restart",
    )
    record("T07", "PASS", f"Pending outbox event survived service restart for {code7}")

    # T08: Consumer Duplicate Delivery
    pay_payload = psql("payment_db", f"SELECT payload::text FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='payment.succeeded' LIMIT 1")
    before_count = int(psql("booking_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='booking.confirmed'"))
    publish_rmq_raw("payment.succeeded", pay_payload)
    time.sleep(1.5)
    after_count = int(psql("booking_db", f"SELECT COUNT(*) FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='booking.confirmed'"))
    assert before_count == after_count == 1
    record("T08", "PASS", f"Duplicate payment.succeeded skipped via inbox for {code1}")

    # T09: Transient Consumer Failure
    b9 = create_booking(5)
    code9 = b9["booking_code"]
    gt9 = {"X-Guest-Token": b9["guest_access_token"]}
    amt9 = float(b9["total_amount"])
    http_json("POST", "/api/payments/create", {"booking_code": code9}, headers=gt9)
    tx9 = f"TX-T09-{uuid.uuid4().hex[:8]}"
    st, _ = send_webhook(code9, amt9, tx9)
    assert st == 200
    # Wait for payment.succeeded to be in flight or test transient DB pause on booking
    b9_2 = create_booking(6)
    code9_2 = b9_2["booking_code"]
    gt9_2 = {"X-Guest-Token": b9_2["guest_access_token"]}
    amt9_2 = float(b9_2["total_amount"])
    http_json("POST", "/api/payments/create", {"booking_code": code9_2}, headers=gt9_2)
    compose_cmd("pause", "postgres-test")
    time.sleep(1.0)
    compose_cmd("unpause", "postgres-test")
    tx9_2 = f"TX-T09B-{uuid.uuid4().hex[:8]}"
    st, _ = send_webhook(code9_2, amt9_2, tx9_2)
    assert st == 200
    wait_until(lambda: http_json("GET", f"/api/checkin/ticket/{code9_2}", headers=gt9_2)[0] == 200, timeout=30.0, msg="T09 recovery")
    record("T09", "PASS", f"Transient DB pause recovered cleanly for {code9_2}")

    # T10: Permanent Consumer Failure -> DLQ
    dlq_before = rmq_api_get("/api/queues/%2F/pickleball.dlq").get("messages", 0)
    publish_rmq_raw("payment.succeeded", "{invalid-json")
    publish_rmq_raw("booking.confirmed", json.dumps({"event": "booking.confirmed", "booking_code": "BAD"}))
    publish_rmq_raw("ticket.issued", json.dumps({"event": "ticket.issued", "booking_code": "BAD"}))
    wait_until(
        lambda: rmq_api_get("/api/queues/%2F/pickleball.dlq").get("messages", 0) >= dlq_before + 3,
        timeout=15.0,
        msg="T10 DLQ messages",
    )
    dlq_after = rmq_api_get("/api/queues/%2F/pickleball.dlq").get("messages", 0)
    record("T10", "PASS", f"Invalid events routed to pickleball.dlq ({dlq_before} -> {dlq_after})")

    # T11: Expired or Cancelled Booking With Received Payment
    b11 = create_booking(7)
    code11 = b11["booking_code"]
    gt11 = {"X-Guest-Token": b11["guest_access_token"]}
    amt11 = float(b11["total_amount"])
    http_json("POST", "/api/payments/create", {"booking_code": code11}, headers=gt11)
    psql("booking_db", f"UPDATE booking_orders SET status='EXPIRED' WHERE booking_code='{code11}'")
    psql("payment_db", f"UPDATE payment_transactions SET status='EXPIRED' WHERE booking_code='{code11}'")
    tx11 = f"TX-T11-{uuid.uuid4().hex[:8]}"
    st, resp11 = send_webhook(code11, amt11, tx11)
    assert st == 200 and isinstance(resp11, dict)
    assert resp11["reconciliation_status"] == "COMPENSATION_REQUIRED"
    assert psql("booking_db", f"SELECT status FROM booking_orders WHERE booking_code='{code11}'") == "EXPIRED"
    assert int(psql("checkin_db", f"SELECT COUNT(*) FROM checkin_tickets WHERE booking_code='{code11}'")) == 0
    assert int(psql("payment_db", f"SELECT COUNT(*) FROM payment_compensations WHERE booking_code='{code11}' AND status='COMPENSATION_REQUIRED'")) == 1
    record("T11", "PASS", f"Expired booking {code11} preserved payment evidence with COMPENSATION_REQUIRED and 0 tickets")

    # T12: Ticket Revocation Regression
    admin_tok = login("admin@pickleball.vn", "Admin@123")
    st, _ = http_json(
        "POST",
        f"/api/bookings/admin/{code1}/cancel",
        {"reason": "T12 regression cancel"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert st == 200
    wait_until(
        lambda: http_json("GET", f"/api/checkin/ticket/{code1}", headers=gt1)[1].get("status") == "REVOKED",
        msg="T12 ticket REVOKED",
    )
    confirmed1 = psql("booking_db", f"SELECT payload::text FROM outbox_events WHERE aggregate_id='{code1}' AND event_type='booking.confirmed' LIMIT 1")
    publish_rmq_raw("booking.confirmed", confirmed1)
    time.sleep(1.5)
    assert psql("checkin_db", f"SELECT status FROM checkin_tickets WHERE booking_code='{code1}'") == "REVOKED"
    staff_tok = login("staff@pickleball.vn", "Staff@123")
    st, _ = http_json(
        "POST",
        "/api/checkin/scan",
        {"qr_data": ticket1["qr_payload"], "bypass_time_check": True},
        headers={"Authorization": f"Bearer {staff_tok}"},
    )
    assert st == 400
    record("T12", "PASS", f"Revoked ticket for {code1} blocked scan and ignored delayed confirmation")

    # T13: Atomic Single-Use Check-in Regression
    st_t3, t3 = http_json("GET", f"/api/checkin/ticket/{code3}", headers={"X-Guest-Token": b3["guest_access_token"]})
    assert st_t3 == 200 and isinstance(t3, dict)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futs = [
            pool.submit(
                http_json,
                "POST",
                "/api/checkin/scan",
                {"qr_data": t3["qr_payload"], "bypass_time_check": True},
                {"Authorization": f"Bearer {staff_tok}"},
            )
            for _ in range(5)
        ]
        scan_codes = [f.result()[0] for f in futs]
    assert scan_codes.count(200) == 1 and scan_codes.count(409) == 4, f"T13 scan codes: {scan_codes}"
    record("T13", "PASS", f"Concurrent check-in yielded 1x 200 and 4x 409 for {code3}")

    # T14: Concurrent Outbox Workers (SKIP LOCKED)
    worker_py = (
        "import asyncio\n"
        "from app.database import AsyncSessionLocal\n"
        "from app.events.rabbitmq import rmq_client\n"
        "from app.events.outbox import enqueue_outbox_event, dispatch_pending_outbox_once\n"
        "async def main():\n"
        "  await rmq_client.connect()\n"
        "  try:\n"
        "    async with AsyncSessionLocal() as db:\n"
        "      for i in range(10):\n"
        "        enqueue_outbox_event(db, 'booking.expired', f'T14-{i}', {'booking_code': f'T14-{i}', 'status': 'EXPIRED'})\n"
        "      await db.commit()\n"
        "    r1, r2 = await asyncio.gather(dispatch_pending_outbox_once(), dispatch_pending_outbox_once())\n"
        "    print(f'dispatched={r1}+{r2}')\n"
        "    assert r1 + r2 == 10\n"
        "  finally:\n"
        "    await rmq_client.close()\n"
        "asyncio.run(main())"
    )
    res14 = subprocess.run(
        ["docker", "compose", "-p", COMPOSE_PROJECT, "-f", COMPOSE_FILE, "exec", "-T", "court-booking-service", "python", "-c", worker_py],
        capture_output=True, text=True, check=True,
    )
    pending_t14 = int(psql("booking_db", "SELECT COUNT(*) FROM outbox_events WHERE aggregate_id LIKE 'T14-%' AND status='PENDING'"))
    pub_t14 = int(psql("booking_db", "SELECT COUNT(*) FROM outbox_events WHERE aggregate_id LIKE 'T14-%' AND status='PUBLISHED'"))
    assert pending_t14 == 0 and pub_t14 == 10
    record("T14", "PASS", f"Concurrent SKIP LOCKED workers published 10/10 events ({res14.stdout.strip()})")

    print("\n=== SUMMARY ===")
    for tid, st, msg in RESULTS:
        print(f"{tid}: {st} - {msg}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run_tests())
    except Exception as exc:
        print(f"TEST SUITE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
