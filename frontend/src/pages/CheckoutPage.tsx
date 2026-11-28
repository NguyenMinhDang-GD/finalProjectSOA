import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Check, CheckCircle2, Clock, Copy, Mail, ShieldAlert, XCircle, Zap } from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND } from '../api/client';
import { Button } from '../components/ui/Button';
import { AlertBanner, ConfirmDialog, LoadingSkeleton } from '../components/ui/FeedbackStates';
import { QrTicketCard } from '../components/ui/QrTicketCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { BookingOrder, CheckinTicket, PaymentTransaction } from '../types';

export const CheckoutPage: React.FC = () => {
  const { bookingCode } = useParams<{ bookingCode: string }>();
  const [booking, setBooking] = useState<BookingOrder | null>(null);
  const [payment, setPayment] = useState<PaymentTransaction | null>(null);
  const [ticket, setTicket] = useState<CheckinTicket | null>(null);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  const [error, setError] = useState('');
  const [pollWarning, setPollWarning] = useState('');
  const [simulating, setSimulating] = useState(false);
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
      const b = await apiRequest<BookingOrder>(`/api/bookings/lookup/${bookingCode}`);
      setBooking(b);
      setPollWarning('');

      if (b.status === 'PENDING_PAYMENT') {
        if (!paymentInitializedRef.current) {
          const p = await apiRequest<PaymentTransaction>('/api/payments/create', {
            method: 'POST',
            body: JSON.stringify({ booking_code: bookingCode }),
          });
          paymentInitializedRef.current = true;
          setPayment(p);
        } else {
          try {
            const p = await apiRequest<PaymentTransaction>(`/api/payments/booking/${bookingCode}`);
            setPayment(p);
          } catch {
            // Keep existing payment state if transient GET fails
          }
        }
      } else if (b.status === 'PAID') {
        try {
          const p = await apiRequest<PaymentTransaction>(`/api/payments/booking/${bookingCode}`);
          setPayment(p);
        } catch {
          // Non-critical if payment lookup lags
        }
        try {
          const t = await apiRequest<CheckinTicket>(`/api/checkin/ticket/${bookingCode}`);
          setTicket(t);
        } catch {
          // Ticket issuance is asynchronous via RabbitMQ
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

  const handleSimulatePayment = async () => {
    if (!bookingCode) return;
    setSimulating(true);
    setError('');
    try {
      await apiRequest(`/api/payments/simulate-webhook/${bookingCode}`, { method: 'POST' });
      window.setTimeout(() => loadData(), 600);
      window.setTimeout(() => loadData(), 1600);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mô phỏng thanh toán');
    } finally {
      setSimulating(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!bookingCode) return;
    setCancelling(true);
    setError('');
    try {
      await apiRequest(`/api/bookings/${bookingCode}/cancel`, { method: 'POST' });
      setConfirmCancelOpen(false);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hủy đơn thất bại');
    } finally {
      setCancelling(false);
    }
  };

  if (error && !booking) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12">
        <AlertBanner tone="error" title="Không tải được đơn đặt sân" onRetry={loadData}>
          {error}
        </AlertBanner>
        <div className="mt-4 text-center">
          <Link to="/" className="text-sm font-bold text-court hover:underline">
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

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-5">
      {error && <AlertBanner tone="error">{error}</AlertBanner>}
      {pollWarning && <AlertBanner tone="warning">{pollWarning}</AlertBanner>}

      {booking.status === 'PAID' ? (
        <div className="space-y-5">
          <div className="bg-court text-white rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-8 h-8 text-ball-lime shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <h1 className="text-xl sm:text-2xl font-bold">Đặt sân &amp; Thanh toán thành công</h1>
                <p className="text-sm text-[#C7D6CD] mt-1">
                  Vé QR đã được phát hành và gửi tới email <strong>{booking.customer_email}</strong>.
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

          <div className="rounded-xl bg-white border border-[#D4D6CD] px-4 py-3 text-xs text-court-muted flex items-center gap-2 no-print">
            <Mail className="w-4 h-4 text-court shrink-0" aria-hidden="true" />
            <span>
              Nếu chưa thấy email trong hộp thư chính, vui lòng kiểm tra hộp thư thử nghiệm hoặc tra cứu lại bằng mã{' '}
              <strong className="font-mono text-charcoal">{booking.booking_code}</strong>.
            </span>
          </div>

          <div className="flex flex-wrap justify-between items-center gap-3 pt-1 no-print">
            <Link to="/" className="text-sm font-bold text-court hover:underline">
              ← Đặt thêm sân khác
            </Link>
            <Link to="/lookup" className="text-sm font-bold text-charcoal hover:underline">
              Tra cứu vé khác →
            </Link>
          </div>
        </div>
      ) : booking.status === 'CANCELLED' || booking.status === 'EXPIRED' ? (
        <div className="bg-white rounded-2xl border border-[#D4D6CD] p-8 text-center">
          <XCircle className="w-12 h-12 text-[#B93829] mx-auto mb-3" aria-hidden="true" />
          <div className="mb-2">
            <StatusBadge status={booking.status} />
          </div>
          <h1 className="text-xl font-bold text-charcoal">
            Đơn đặt sân đã {booking.status === 'EXPIRED' ? 'hết hạn giữ chỗ' : 'bị hủy'}
          </h1>
          <p className="text-sm text-court-muted mt-1.5 max-w-md mx-auto">
            {booking.cancel_reason || 'Các khung giờ trước đó đã được giải phóng để người chơi khác đặt.'}
          </p>
          <Link
            to="/"
            className="inline-block mt-6 bg-court hover:bg-court-soft text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
          >
            Đặt lịch mới
          </Link>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Pending Payment Header */}
          <div className="bg-white rounded-2xl border border-[#D4D6CD] overflow-hidden">
            <div className="bg-court text-white px-6 py-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-wider text-[#B7C9BE] font-semibold">
                  Chờ thanh toán chuyển khoản
                </div>
                <h1 className="text-lg sm:text-xl font-bold font-mono mt-0.5">{booking.booking_code}</h1>
              </div>
              <div className="flex items-center gap-2 bg-court-deep px-3.5 py-2 rounded-xl border border-court-soft text-sm font-mono font-bold tabular-nums">
                <Clock className="w-4 h-4 text-ball-lime" aria-hidden="true" />
                <span>
                  Giữ chỗ còn: {mm}:{ss}
                </span>
              </div>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
              {/* Booking Summary */}
              <div className="space-y-3 text-sm">
                <h2 className="font-bold text-charcoal text-base pb-2 border-b border-[#ECEBE2]">
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
                    <span className="text-right text-charcoal">{booking.location_address_snapshot}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-court-muted">Sân:</span>
                  <span className="font-bold text-charcoal">{booking.court_name_snapshot}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-court-muted">Ngày chơi:</span>
                  <span className="font-semibold tabular-nums">{formatDateVN(booking.play_date)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-court-muted">Khung giờ:</span>
                  <span className="font-semibold tabular-nums">
                    {formatHourRange(booking.start_hour, booking.end_hour)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-court-muted">Khách hàng:</span>
                  <span className="font-semibold">{booking.customer_name}</span>
                </div>
                <div className="flex justify-between pt-3 border-t border-[#ECEBE2] text-base">
                  <span className="font-bold text-charcoal">Số tiền cần chuyển:</span>
                  <span className="font-bold text-court tabular-nums">{formatVND(booking.total_amount)}</span>
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

              {/* VietQR Transfer Panel */}
              <div className="bg-warm-white rounded-2xl border border-[#D4D6CD] p-5 text-center">
                <h2 className="text-sm font-bold text-charcoal mb-3">
                  Quét mã VietQR bằng ứng dụng Ngân hàng
                </h2>
                {payment?.qr_image_url ? (
                  <div className="bg-white p-3 rounded-xl border border-[#D4D6CD] inline-block shadow-sm">
                    <img
                      src={payment.qr_image_url}
                      alt={`Mã VietQR thanh toán đơn ${booking.booking_code}`}
                      className="w-52 h-52 object-contain block"
                    />
                  </div>
                ) : (
                  <div className="h-52 flex items-center justify-center text-sm text-court-muted">
                    Đang tạo mã VietQR...
                  </div>
                )}

                <div className="mt-4 bg-white rounded-xl border border-[#D4D6CD] p-3.5 text-left text-xs space-y-2">
                  <div className="flex justify-between gap-2">
                    <span className="text-court-muted">Chủ tài khoản:</span>
                    <span className="font-bold text-charcoal">
                      {payment?.bank_account_name || 'SAN PICKLEBALL SOA'}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-court-muted">Số tài khoản:</span>
                    <span className="font-mono font-bold text-charcoal tabular-nums">
                      {payment?.bank_account_no || '0123456789'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center gap-2 pt-1 border-t border-[#ECEBE2]">
                    <span className="text-court-muted">Nội dung CK:</span>
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

          {/* Clearly separated Demo/Dev Simulation Panel */}
          <section
            aria-label="Công cụ mô phỏng thanh toán phục vụ demo"
            className="rounded-2xl border border-dashed border-amber-400 bg-amber-50/70 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
          >
            <div className="flex items-start gap-2.5">
              <ShieldAlert className="w-5 h-5 text-amber-800 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <div className="text-xs font-bold uppercase tracking-wide text-amber-950">
                  Chế độ Mô phỏng (Phục vụ Demo / Kiểm thử)
                </div>
                <p className="text-xs text-amber-900 mt-0.5">
                  Đây là nút giả lập webhook ngân hàng cho môi trường phát triển, không phải xác nhận giao dịch ngân hàng thật.
                </p>
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="md"
              loading={simulating}
              onClick={handleSimulatePayment}
              className="shrink-0 border-amber-400 bg-white hover:bg-amber-100 text-amber-950"
            >
              <Zap className="w-4 h-4 text-amber-700" aria-hidden="true" />
              {simulating ? 'Đang gửi webhook mẫu...' : 'Mô phỏng Webhook Thanh toán'}
            </Button>
          </section>
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
