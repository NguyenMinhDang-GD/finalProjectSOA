import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Check, CheckCircle2, Clock, Copy, Mail, ShieldAlert, XCircle, Zap } from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND } from '../api/client';
import { Button } from '../components/ui/Button';
import { AlertBanner, ConfirmDialog, LoadingSkeleton } from '../components/ui/FeedbackStates';
import { QrTicketCard } from '../components/ui/QrTicketCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { AvailabilityResponse, BookingOrder, CancellationQuote, CheckinTicket, PaymentTransaction, RefundTransaction, RescheduleQuote } from '../types';

export const CheckoutPage: React.FC = () => {
  const { user } = useAuth();
  const { bookingCode } = useParams<{ bookingCode: string }>();
  const [booking, setBooking] = useState<BookingOrder | null>(null);
  const [payment, setPayment] = useState<PaymentTransaction | null>(null);
  const [ticket, setTicket] = useState<CheckinTicket | null>(null);
  const [refunds, setRefunds] = useState<RefundTransaction[]>([]);
  const [cancelQuote, setCancelQuote] = useState<CancellationQuote | null>(null);
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [rescheduleAvail, setRescheduleAvail] = useState<AvailabilityResponse | null>(null);
  const [rescheduleCourtId, setRescheduleCourtId] = useState('');
  const [rescheduleHour, setRescheduleHour] = useState<number | null>(null);
  const [rescheduleQuote, setRescheduleQuote] = useState<RescheduleQuote | null>(null);
  const [rescheduling, setRescheduling] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  const [error, setError] = useState('');
  const [pollWarning, setPollWarning] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const paymentInitializedRef = useRef(false);
  const inFlightRef = useRef(false);
  const copyTimerRef = useRef<number | null>(null);

  useEffect(() => {
    paymentInitializedRef.current = false;
    setBooking(null);
    setPayment(null);
    setTicket(null);
    setError('');
    setPollWarning('');
  }, [bookingCode]);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) window.clearTimeout(copyTimerRef.current);
    };
  }, []);

  const loadData = useCallback(async () => {
    if (!bookingCode || inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const b = await apiRequest<BookingOrder>(
        `/api/bookings/lookup/${bookingCode}`,
        {},
        bookingCode
      );
      setBooking(b);
      setPollWarning('');

      if (b.status === 'PENDING_PAYMENT') {
        if (!paymentInitializedRef.current) {
          const p = await apiRequest<PaymentTransaction>(
            '/api/payments/create',
            {
              method: 'POST',
              body: JSON.stringify({ booking_code: bookingCode }),
            },
            bookingCode
          );
          paymentInitializedRef.current = true;
          setPayment(p);
        } else {
          try {
            const p = await apiRequest<PaymentTransaction>(
              `/api/payments/booking/${bookingCode}`,
              {},
              bookingCode
            );
            setPayment(p);
          } catch {
            // Keep existing payment state if transient GET fails
          }
        }
      } else if (b.status === 'PAID') {
        try {
          const p = await apiRequest<PaymentTransaction>(
            `/api/payments/booking/${bookingCode}`,
            {},
            bookingCode
          );
          setPayment(p);
        } catch {
          // Non-critical if payment lookup lags
        }
        try {
          const t = await apiRequest<CheckinTicket>(
            `/api/checkin/ticket/${bookingCode}`,
            {},
            bookingCode
          );
          setTicket(t);
        } catch {
          // Ticket issuance is asynchronous via RabbitMQ
        }
        try {
          const q = await apiRequest<CancellationQuote>(
            `/api/bookings/${bookingCode}/cancellation-quote`,
            {},
            bookingCode
          );
          setCancelQuote(q);
        } catch {
          // Optional
        }
      } else if (b.status === 'CANCELLED' || b.status === 'EXPIRED') {
        try {
          const p = await apiRequest<PaymentTransaction>(
            `/api/payments/booking/${bookingCode}`,
            {},
            bookingCode
          );
          setPayment(p);
        } catch {
          // No payment record exists for this cancelled/expired booking
        }
        try {
          const r = await apiRequest<RefundTransaction[]>(
            `/api/payments/booking/${bookingCode}/refunds`,
            {},
            bookingCode
          );
          setRefunds(r);
        } catch {
          // Optional
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Không tải được thông tin đơn hàng';
      if (!booking) {
        setError(msg);
      } else {
        setPollWarning(`Tạm thời mất kết nối khi cập nhật trạng thái (${msg}). Đang thử lại...`);
      }
    } finally {
      inFlightRef.current = false;
    }
  }, [bookingCode, booking]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll every 2.5s while awaiting payment or ticket issuance
  useEffect(() => {
    if (!booking) return;
    if (booking.status === 'PAID' && ticket) return;
    if (booking.status === 'CANCELLED' || booking.status === 'EXPIRED') return;

    const timer = window.setInterval(() => {
      loadData();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [booking, ticket, loadData]);

  // 15-minute reservation countdown
  useEffect(() => {
    if (!booking || booking.status !== 'PENDING_PAYMENT') return;
    const updateCountdown = () => {
      const diff = Math.max(
        0,
        Math.floor((new Date(booking.expires_at).getTime() - Date.now()) / 1000)
      );
      setSecondsLeft(diff);
    };
    updateCountdown();
    const interval = window.setInterval(updateCountdown, 1000);
    return () => window.clearInterval(interval);
  }, [booking]);

  const handleCopyTransfer = () => {
    const content = payment?.transfer_content || `PKB ${booking?.booking_code || ''}`;
    navigator.clipboard.writeText(content).catch(() => undefined);
    setCopied(true);
    if (copyTimerRef.current) window.clearTimeout(copyTimerRef.current);
    copyTimerRef.current = window.setTimeout(() => setCopied(false), 2000);
  };

  const handleSimulatePayment = async (
    outcome: 'SUCCEEDED' | 'PROCESSING' | 'FAILED' | 'UNDERPAID' | 'OVERPAID' = 'SUCCEEDED'
  ) => {
    if (!bookingCode) return;
    setSimulating(true);
    setError('');
    try {
      await apiRequest(`/api/payments/simulate/${bookingCode}`, {
        method: 'POST',
        body: JSON.stringify({ outcome }),
      });
      window.setTimeout(() => loadData(), 400);
      window.setTimeout(() => loadData(), 1400);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mô phỏng thanh toán');
    } finally {
      setSimulating(false);
    }
  };

  const handleRetryPayment = async () => {
    if (!bookingCode) return;
    setRetrying(true);
    setError('');
    try {
      const updated = await apiRequest<PaymentTransaction>(
        `/api/payments/booking/${bookingCode}/retry`,
        { method: 'POST' },
        bookingCode
      );
      setPayment(updated);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể thử lại thanh toán');
    } finally {
      setRetrying(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!bookingCode) return;
    setCancelling(true);
    setError('');
    try {
      await apiRequest(`/api/bookings/${bookingCode}/cancel`, { method: 'POST' }, bookingCode);
      setConfirmCancelOpen(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hủy đơn thất bại');
    } finally {
      setCancelling(false);
    }
  };

  const loadRescheduleAvailability = async (targetDate: string) => {
    if (!targetDate) return;
    setRescheduleDate(targetDate);
    setRescheduleQuote(null);
    setRescheduleHour(null);
    try {
      const avail = await apiRequest<AvailabilityResponse>(`/api/courts/availability?date=${targetDate}`);
      setRescheduleAvail(avail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được lịch trống');
    }
  };

  const handleSelectRescheduleSlot = async (courtId: string, startHour: number) => {
    if (!bookingCode || !rescheduleDate) return;
    setRescheduleCourtId(courtId);
    setRescheduleHour(startHour);
    try {
      const q = await apiRequest<RescheduleQuote>(
        `/api/bookings/${bookingCode}/reschedule-quote`,
        {
          method: 'POST',
          body: JSON.stringify({ court_id: courtId, play_date: rescheduleDate, hours: [startHour] }),
        },
        bookingCode
      );
      setRescheduleQuote(q);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không kiểm tra được đổi lịch');
    }
  };

  const handleConfirmReschedule = async () => {
    if (!bookingCode || !rescheduleCourtId || !rescheduleDate || rescheduleHour === null) return;
    setRescheduling(true);
    setError('');
    try {
      await apiRequest(
        `/api/bookings/${bookingCode}/reschedule`,
        {
          method: 'POST',
          body: JSON.stringify({
            court_id: rescheduleCourtId,
            play_date: rescheduleDate,
            hours: [rescheduleHour],
            expected_revision: booking?.booking_revision ?? 1,
            idempotency_key: `ui-${bookingCode}-${booking?.booking_revision ?? 1}-${rescheduleDate}-${rescheduleHour}`,
          }),
        },
        bookingCode
      );
      setRescheduleOpen(false);
      setRescheduleQuote(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đổi lịch thất bại');
    } finally {
      setRescheduling(false);
    }
  };

  if (error && !booking) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12 space-y-4">
        <AlertBanner tone="error" title="Không tải được đơn đặt sân" onRetry={loadData}>
          {error}
        </AlertBanner>
        <div className="bg-white rounded-xl border border-[#CFCFC4] p-4 text-xs text-court-muted leading-relaxed">
          Nếu bạn đặt sân với tư cách khách vãng lai, vui lòng mở lại trang từ trình duyệt đã tạo đơn hoặc liên hệ nhân viên/quản trị viên tại sân kèm mã đơn{' '}
          <strong className="font-mono text-charcoal">{bookingCode}</strong> để được hỗ trợ tra cứu.
        </div>
        <div className="text-center">
          <Link to="/book" className="text-sm font-bold text-court hover:underline">
            ← Quay lại trang đặt sân
          </Link>
        </div>
      </div>
    );
  }

  if (!booking) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-10">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0');
  const ss = String(secondsLeft % 60).padStart(2, '0');

  const stepIndex =
    booking.status === 'PAID' && ticket
      ? 4
      : booking.status === 'PAID'
      ? 3
      : payment?.status === 'SUCCEEDED'
      ? 2
      : 1;

  const steps = ['Giữ chỗ', 'Thanh toán giả lập', 'Xác nhận đơn', 'Vé QR sẵn sàng'];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-5">
      {/* Truthful Asynchronous SOA Progress Strip (hidden on terminal cancel/expire) */}
      {booking.status !== 'CANCELLED' && booking.status !== 'EXPIRED' && (
        <nav
          aria-label="Tiến trình xử lý đơn"
          className="bg-white rounded-2xl border border-[#CFCFC4] px-4 py-3 no-print"
        >
          <ol className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            {steps.map((label, idx) => {
              const num = idx + 1;
              const done = stepIndex > num || (num === 4 && stepIndex === 4);
              const active = stepIndex === num && !done;
              return (
                <li
                  key={label}
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border ${
                    done
                      ? 'bg-[#E6F4EC] border-[#A7D7BA] text-[#14532D] font-semibold'
                      : active
                      ? 'bg-court text-white border-court font-semibold'
                      : 'bg-warm-white border-[#E5E5DC] text-court-muted'
                  }`}
                >
                  <span className="font-mono text-[11px] font-bold">0{num}</span>
                  <span className="truncate">{label}</span>
                </li>
              );
            })}
          </ol>
        </nav>
      )}

      {error && <AlertBanner tone="error">{error}</AlertBanner>}
      {pollWarning && <AlertBanner tone="warning">{pollWarning}</AlertBanner>}

      {booking.status === 'PAID' ? (
        <div className="space-y-5">
          <div className="bg-court text-white rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border border-[#23483D]">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-8 h-8 text-ball-lime shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <h1 className="font-display text-xl sm:text-2xl font-extrabold">
                  {ticket
                    ? 'Đặt sân & Thanh toán thành công'
                    : 'Đặt sân đã xác nhận — Đang chuẩn bị vé QR'}
                </h1>
                <p className="text-sm text-[#D1DDD6] mt-1">
                  {ticket ? (
                    <>
                      Vé QR đã được phát hành và gửi tới email <strong>{booking.customer_email}</strong>.
                    </>
                  ) : (
                    'Hệ thống đang phát hành vé QR điện tử, trang sẽ tự động cập nhật trong giây lát.'
                  )}
                </p>
              </div>
            </div>
            <StatusBadge status="PAID" />
          </div>

          <QrTicketCard
            ticket={ticket}
            bookingCode={booking.booking_code}
            branchName={booking.branch_name_snapshot}
            locationName={booking.location_name_snapshot}
            locationAddress={booking.location_address_snapshot}
            courtName={booking.court_name_snapshot}
            playDate={booking.play_date}
            startHour={booking.start_hour}
            endHour={booking.end_hour}
            customerName={booking.customer_name}
            totalAmount={booking.total_amount}
          />

          <div className="rounded-xl bg-white border border-[#CFCFC4] px-4 py-3 text-xs text-court-muted flex flex-wrap items-center justify-between gap-3 no-print">
            <div className="flex items-center gap-2">
              <Mail className="w-4 h-4 text-court shrink-0" aria-hidden="true" />
              <span>
                Phiên bản lịch <strong className="font-mono text-charcoal">v{booking.booking_revision || 1}</strong> • Mã đơn{' '}
                <strong className="font-mono text-charcoal">{booking.booking_code}</strong>.
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {booking.admission_status !== 'ADMITTED' && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    const nextOpen = !rescheduleOpen;
                    setRescheduleOpen(nextOpen);
                    if (nextOpen && !rescheduleDate) {
                      loadRescheduleAvailability(booking.play_date);
                    }
                  }}
                >
                  Đổi lịch chơi
                </Button>
              )}
              {cancelQuote?.eligible && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setConfirmCancelOpen(true)}
                >
                  Hủy đơn ({cancelQuote.refund_percent}% hoàn tiền)
                </Button>
              )}
            </div>
          </div>

          {rescheduleOpen && (
            <div className="bg-white rounded-2xl border border-[#CFCFC4] p-5 space-y-4 no-print">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-display font-bold text-charcoal">Chọn khung giờ mới (Đổi lịch cùng mức giá)</h2>
                <input
                  type="date"
                  value={rescheduleDate}
                  onChange={(e) => loadRescheduleAvailability(e.target.value)}
                  className="rounded-lg border border-[#CFCFC4] px-3 py-1.5 text-sm font-mono"
                />
              </div>
              {rescheduleAvail && (
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {rescheduleAvail.courts.map((c) => (
                    <div key={c.court.id} className="space-y-1.5">
                      <div className="text-xs font-bold text-court">{c.court.name}</div>
                      <div className="flex flex-wrap gap-1.5">
                        {c.slots
                          .filter((s) => s.status === 'AVAILABLE')
                          .map((s) => {
                            const selected = rescheduleCourtId === c.court.id && rescheduleHour === s.start_hour;
                            return (
                              <button
                                key={s.start_hour}
                                type="button"
                                onClick={() => handleSelectRescheduleSlot(c.court.id, s.start_hour)}
                                className={`px-2.5 py-1 rounded-lg text-xs font-mono border ${
                                  selected
                                    ? 'bg-court text-white border-court font-bold'
                                    : 'bg-warm-white border-[#CFCFC4] text-charcoal hover:border-court'
                                }`}
                              >
                                {s.start_hour}:00 ({formatVND(s.price)})
                              </button>
                            );
                          })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {rescheduleQuote && (
                <div className="p-3 rounded-xl bg-warm-white border border-[#DCDCD2] text-xs space-y-2">
                  <div>
                    Giá hiện tại: <strong>{formatVND(rescheduleQuote.current_amount)}</strong> → Giá mới:{' '}
                    <strong>{formatVND(rescheduleQuote.new_amount)}</strong>
                  </div>
                  {!rescheduleQuote.eligible ? (
                    <div className="text-[#B93829] font-semibold">{rescheduleQuote.reason}</div>
                  ) : (
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      loading={rescheduling}
                      onClick={handleConfirmReschedule}
                    >
                      Xác nhận đổi lịch
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}

          {payment && payment.received_amount > payment.expected_amount && (
            <AlertBanner tone="warning" title="Ghi nhận thanh toán dư — Đang chờ đối soát hoàn phần dư">
              Hệ thống đã nhận {formatVND(payment.received_amount)} (vượt {formatVND(payment.received_amount - payment.expected_amount)} so với giá đơn {formatVND(payment.expected_amount)}).
            </AlertBanner>
          )}

          <div className="flex flex-wrap justify-between items-center gap-3 pt-1 no-print">
            <Link to="/book" className="text-sm font-bold text-court hover:underline">
              ← Đặt thêm sân khác
            </Link>
            <Link to="/lookup" className="text-sm font-bold text-charcoal hover:underline">
              Tra cứu vé khác →
            </Link>
          </div>
        </div>
      ) : booking.status === 'CANCELLED' || booking.status === 'EXPIRED' ? (
        <div className="bg-white rounded-2xl border border-[#CFCFC4] p-8 text-center space-y-4">
          <XCircle className="w-12 h-12 text-[#B93829] mx-auto" aria-hidden="true" />
          <div>
            <StatusBadge status={booking.status} />
          </div>
          <h1 className="font-display text-xl sm:text-2xl font-extrabold text-charcoal">
            Đơn đặt sân đã {booking.status === 'EXPIRED' ? 'hết hạn giữ chỗ' : 'bị hủy'}
          </h1>
          <p className="text-sm text-court-muted max-w-md mx-auto">
            {booking.cancel_reason ||
              'Các khung giờ trước đó đã được giải phóng để người chơi khác đặt.'}
          </p>
          {(payment?.reconciliation_status === 'COMPENSATION_REQUIRED' ||
            payment?.status === 'SUCCEEDED') && (
            <div className="max-w-lg mx-auto text-left">
              <AlertBanner
                tone="warning"
                title="Đã ghi nhận khoản thanh toán — Cần đối soát / hoàn tiền"
              >
                <div className="text-xs space-y-1">
                  <p>
                    Hệ thống đã lưu giữ bằng chứng thanh toán{' '}
                    <strong className="font-mono">{payment.provider_tx_id || payment.id}</strong> (
                    {formatVND(payment.amount)}), nhưng đơn đặt sân không thể xác nhận do đã{' '}
                    {booking.status === 'EXPIRED' ? 'hết hạn' : 'bị hủy'}.
                  </p>
                  {payment.reconciliation_note && (
                    <p className="text-amber-900">Ghi chú: {payment.reconciliation_note}</p>
                  )}
                </div>
              </AlertBanner>
            </div>
          )}
          {refunds.length > 0 && (
            <div className="max-w-lg mx-auto text-left space-y-2">
              {refunds.map((rf) => (
                <AlertBanner
                  key={rf.id}
                  tone={rf.status === 'SUCCEEDED' ? 'info' : rf.status === 'FAILED' || rf.status === 'REJECTED' ? 'error' : 'warning'}
                  title={`Hoàn tiền ${rf.refund_code} — ${rf.status}`}
                >
                  <div className="text-xs space-y-1">
                    <p>
                      Số tiền yêu cầu: <strong>{formatVND(rf.requested_amount)}</strong> ({rf.policy_percent}% • {rf.policy_tier})
                    </p>
                    {rf.refunded_amount > 0 && (
                      <p>Đã hoàn: <strong>{formatVND(rf.refunded_amount)}</strong></p>
                    )}
                    {rf.failure_reason && <p>Lý do lỗi: {rf.failure_reason}</p>}
                  </div>
                </AlertBanner>
              ))}
            </div>
          )}
          <Link
            to="/book"
            className="inline-block bg-court hover:bg-court-soft text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-colors"
          >
            Đặt lịch mới
          </Link>
        </div>
      ) : payment?.status === 'SUCCEEDED' ? (
        <div className="bg-white rounded-2xl border border-[#CFCFC4] p-8 text-center space-y-3">
          <Clock className="w-10 h-10 text-court mx-auto animate-pulse" aria-hidden="true" />
          <h1 className="font-display text-xl sm:text-2xl font-extrabold text-charcoal">
            Đã nhận thanh toán — Đang chờ xác nhận đặt sân
          </h1>
          <p className="text-sm text-court-muted max-w-md mx-auto">
            Thanh toán cho đơn{' '}
            <strong className="font-mono text-charcoal">{booking.booking_code}</strong> đã được ghi nhận. Hệ thống đang hoàn tất xác nhận sân và sẽ tự động chuyển sang vé QR.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Pending Payment Card */}
          <div className="bg-white rounded-2xl border border-[#CFCFC4] overflow-hidden shadow-sm">
            <div className="bg-court text-white px-6 py-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-ball-lime font-bold">
                  Chờ thanh toán chuyển khoản
                </div>
                <h1 className="text-lg sm:text-xl font-bold font-mono mt-0.5">
                  {booking.booking_code}
                </h1>
              </div>
              <div className="flex items-center gap-2 bg-court-deep px-3.5 py-2 rounded-xl border border-[#2D584B] text-sm font-mono font-bold tabular-nums">
                <Clock className="w-4 h-4 text-ball-lime" aria-hidden="true" />
                <span>
                  Giữ chỗ còn: {mm}:{ss}
                </span>
              </div>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
              {/* Booking Summary */}
              <div className="space-y-3 text-sm">
                <h2 className="font-display font-bold text-charcoal text-lg pb-2 border-b border-[#ECEBE2]">
                  Chi tiết đơn đặt sân
                </h2>
                {booking.branch_name_snapshot && (
                  <div className="flex justify-between gap-3">
                    <span className="text-court-muted">Chi nhánh:</span>
                    <span className="font-semibold text-court text-right">
                      {booking.branch_name_snapshot}
                    </span>
                  </div>
                )}
                {booking.location_name_snapshot && (
                  <div className="flex justify-between gap-3">
                    <span className="text-court-muted">Địa điểm:</span>
                    <span className="font-semibold text-right">{booking.location_name_snapshot}</span>
                  </div>
                )}
                {booking.location_address_snapshot && (
                  <div className="flex justify-between gap-3">
                    <span className="text-court-muted shrink-0">Địa chỉ:</span>
                    <span className="text-right text-charcoal">
                      {booking.location_address_snapshot}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-court-muted">Sân:</span>
                  <span className="font-bold text-charcoal">{booking.court_name_snapshot}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-court-muted">Ngày chơi:</span>
                  <span className="font-mono font-semibold tabular-nums">
                    {formatDateVN(booking.play_date)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-court-muted">Khung giờ:</span>
                  <span className="font-mono font-semibold tabular-nums">
                    {formatHourRange(booking.start_hour, booking.end_hour)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-court-muted">Khách hàng:</span>
                  <span className="font-semibold">{booking.customer_name}</span>
                </div>
                <div className="flex justify-between pt-3 border-t border-[#ECEBE2] text-base items-baseline">
                  <span className="font-bold text-charcoal">Số tiền cần chuyển:</span>
                  <span className="font-mono font-extrabold text-lg text-court tabular-nums">
                    {formatVND(booking.total_amount)}
                  </span>
                </div>

                <div className="pt-3">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setConfirmCancelOpen(true)}
                  >
                    Hủy giữ chỗ
                  </Button>
                </div>
              </div>

              {/* Simulated Payment QR Panel (Non-financial Demo Only) */}
              <div className="bg-warm-white rounded-2xl border border-[#D4D6CD] p-5 text-center">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 border border-amber-300 text-amber-950 text-[11px] font-bold uppercase tracking-wide mb-2">
                  THANH TOÁN GIẢ LẬP • KHÔNG PHẢI TIỀN THẬT
                </div>
                <h2 className="text-sm font-bold text-charcoal mb-3">
                  Mã QR Mô phỏng Trình diễn (Không kết nối ngân hàng thật)
                </h2>
                {payment?.qr_image_url ? (
                  <div className="bg-white p-3 rounded-xl border border-[#D4D6CD] inline-block shadow-sm">
                    <img
                      src={payment.qr_image_url}
                      alt={`Mã QR thanh toán giả lập đơn ${booking.booking_code}`}
                      className="w-52 h-56 object-contain block"
                    />
                  </div>
                ) : (
                  <div className="h-52 flex items-center justify-center text-sm text-court-muted">
                    Đang tạo phiên thanh toán giả lập...
                  </div>
                )}

                {payment?.status === 'FAILED' && (
                  <div className="mt-4 text-left space-y-2">
                    <AlertBanner tone="error" title="Thanh toán giả lập thất bại">
                      <p className="text-xs">{payment.failure_reason || 'Giao dịch bị từ chối trong chế độ mô phỏng.'}</p>
                    </AlertBanner>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      loading={retrying}
                      onClick={handleRetryPayment}
                      className="w-full"
                    >
                      Thử lại thanh toán
                    </Button>
                  </div>
                )}

                {payment?.status === 'PROCESSING' && (
                  <div className="mt-4 text-left">
                    <AlertBanner tone="info" title="Đang xử lý thanh toán giả lập">
                      <p className="text-xs">Giao dịch đang ở trạng thái PROCESSING, hệ thống đang chờ kết quả cuối.</p>
                    </AlertBanner>
                  </div>
                )}

                <div className="mt-4 bg-white rounded-xl border border-[#D4D6CD] p-3.5 text-left text-xs space-y-2">
                  <div className="text-[11px] text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-2 leading-relaxed">
                    {payment?.simulation_notice ||
                      'THANH TOÁN GIẢ LẬP — Chỉ dùng cho kiểm thử và trình diễn. Không phải mã chuyển khoản ngân hàng thật.'}
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-court-muted">Chế độ cổng:</span>
                    <span className="font-mono font-bold text-charcoal">
                      {payment?.payment_mode || 'MOCK_DEMO'} ({payment?.provider || 'SIMULATED_GATEWAY'})
                    </span>
                  </div>
                  <div className="flex justify-between items-center gap-2 pt-1 border-t border-[#ECEBE2]">
                    <span className="text-court-muted">Mã tham chiếu:</span>
                    <button
                      type="button"
                      onClick={handleCopyTransfer}
                      className="inline-flex items-center gap-1.5 font-mono font-bold text-court bg-[#E9EFEA] hover:bg-[#DCE7DF] px-2.5 py-1 rounded-md transition-colors"
                    >
                      <span>{payment?.transfer_content || `PKB ${booking.booking_code}`}</span>
                      {copied ? (
                        <Check className="w-3.5 h-3.5 text-[#14532D]" aria-hidden="true" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" aria-hidden="true" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Clearly separated Demo/Dev Simulation Panel (STAFF/ADMIN only, disabled when VITE_ENABLE_DEMO_CONTROLS=false) */}
          {(user?.role === 'STAFF' || user?.role === 'ADMIN') &&
            import.meta.env.VITE_ENABLE_DEMO_CONTROLS !== 'false' && (
          <section
            aria-label="Công cụ mô phỏng thanh toán phục vụ demo"
            className="rounded-2xl border border-dashed border-amber-400 bg-amber-50/70 p-4 sm:p-5 space-y-3"
          >
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="w-5 h-5 text-amber-800 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <div className="text-xs font-bold uppercase tracking-wide text-amber-950">
                  Bảng điều khiển Giả lập Thanh toán (STAFF / ADMIN • Không phải tiền thật)
                </div>
                <p className="text-xs text-amber-900 mt-0.5">
                  Kích hoạt các kịch bản thanh toán giả lập để kiểm thử trạng thái PROCESSING, FAILED, thanh toán thiếu, thanh toán dư hoặc thành công.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={simulating}
                onClick={() => handleSimulatePayment('SUCCEEDED')}
              >
                <Zap className="w-4 h-4" aria-hidden="true" />
                Mô phỏng Thành công
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={simulating}
                onClick={() => handleSimulatePayment('PROCESSING')}
              >
                Đang xử lý (PROCESSING)
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={simulating}
                onClick={() => handleSimulatePayment('FAILED')}
              >
                Thất bại (FAILED)
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={simulating}
                onClick={() => handleSimulatePayment('UNDERPAID')}
              >
                Thanh toán thiếu
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={simulating}
                onClick={() => handleSimulatePayment('OVERPAID')}
              >
                Thanh toán dư
              </Button>
            </div>
          </section>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmCancelOpen}
        title="Hủy giữ chỗ đơn đặt sân?"
        description={`Khung giờ của đơn ${booking.booking_code} sẽ được giải phóng ngay lập tức cho người chơi khác.`}
        confirmLabel="Xác nhận hủy đơn"
        loading={cancelling}
        onConfirm={handleConfirmCancel}
        onCancel={() => setConfirmCancelOpen(false)}
      />
    </div>
  );
};
