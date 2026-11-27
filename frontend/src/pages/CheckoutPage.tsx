import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CheckCircle2, Clock, Copy, Mail, QrCode, XCircle, Zap } from 'lucide-react';
import { apiRequest, formatVND } from '../api/client';
import { BookingOrder, CheckinTicket, PaymentTransaction } from '../types';

export const CheckoutPage: React.FC = () => {
  const { bookingCode } = useParams<{ bookingCode: string }>();
  const [booking, setBooking] = useState<BookingOrder | null>(null);
  const [payment, setPayment] = useState<PaymentTransaction | null>(null);
  const [ticket, setTicket] = useState<CheckinTicket | null>(null);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  const [error, setError] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadData = useCallback(async () => {
    if (!bookingCode) return;
    try {
      const b = await apiRequest<BookingOrder>(`/api/bookings/lookup/${bookingCode}`);
      setBooking(b);

      if (b.status === 'PENDING_PAYMENT') {
        const p = await apiRequest<PaymentTransaction>('/api/payments/create', {
          method: 'POST',
          body: JSON.stringify({ booking_code: bookingCode }),
        });
        setPayment(p);
      } else if (b.status === 'PAID') {
        try {
          const p = await apiRequest<PaymentTransaction>(`/api/payments/booking/${bookingCode}`);
          setPayment(p);
        } catch {
          // ignore
        }
        try {
          const t = await apiRequest<CheckinTicket>(`/api/checkin/ticket/${bookingCode}`);
          setTicket(t);
        } catch {
          // Ticket may take ~0.5s via RabbitMQ event
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được thông tin đơn hàng');
    }
  }, [bookingCode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll payment/ticket status every 2.5s while waiting
  useEffect(() => {
    if (!booking) return;
    if (booking.status === 'PAID' && ticket) return;
    if (booking.status === 'CANCELLED' || booking.status === 'EXPIRED') return;

    const timer = setInterval(() => {
      loadData();
    }, 2500);
    return () => clearInterval(timer);
  }, [booking, ticket, loadData]);

  // Countdown timer
  useEffect(() => {
    if (!booking || booking.status !== 'PENDING_PAYMENT') return;
    const updateCountdown = () => {
      const diff = Math.max(0, Math.floor((new Date(booking.expires_at).getTime() - Date.now()) / 1000));
      setSecondsLeft(diff);
    };
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [booking]);

  const handleSimulatePayment = async () => {
    if (!bookingCode) return;
    setSimulating(true);
    setError('');
    try {
      await apiRequest(`/api/payments/simulate-webhook/${bookingCode}`, { method: 'POST' });
      // Wait briefly for RabbitMQ async propagation
      setTimeout(() => loadData(), 600);
      setTimeout(() => loadData(), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể giả lập thanh toán');
    } finally {
      setSimulating(false);
    }
  };

  const handleCancelBooking = async () => {
    if (!bookingCode) return;
    try {
      await apiRequest(`/api/bookings/${bookingCode}/cancel`, { method: 'POST' });
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hủy đơn thất bại');
    }
  };

  if (error && !booking) {
    return (
      <div className="max-w-xl mx-auto mt-10 bg-white rounded-2xl p-6 border border-red-200 text-center">
        <p className="text-red-600 font-medium">{error}</p>
        <Link to="/" className="inline-block mt-4 text-sm text-emerald-700 font-semibold hover:underline">
          ← Quay lại trang đặt sân
        </Link>
      </div>
    );
  }

  if (!booking) {
    return <div className="max-w-xl mx-auto mt-10 text-center text-slate-500">Đang tải thông tin thanh toán...</div>;
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, '0');
  const ss = String(secondsLeft % 60).padStart(2, '0');

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {error && (
        <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}

      {booking.status === 'PAID' ? (
        <div className="bg-white rounded-2xl border border-emerald-200 shadow-sm overflow-hidden">
          <div className="bg-emerald-700 text-white p-6 text-center">
            <CheckCircle2 className="w-12 h-12 mx-auto text-lime-300 mb-2" />
            <h1 className="text-2xl font-bold">Thanh toán thành công!</h1>
            <p className="text-sm text-emerald-100 mt-1">
              Hệ thống đã phát hành vé QR và gửi email tới <strong>{booking.customer_email}</strong>
            </p>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
            <div className="space-y-3 text-sm">
              <h2 className="font-bold text-slate-900 text-base border-b pb-2">Thông tin vé đặt sân</h2>
              <div className="flex justify-between">
                <span className="text-slate-500">Mã đặt sân:</span>
                <span className="font-bold text-slate-900">{booking.booking_code}</span>
              </div>
              {booking.branch_name_snapshot && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Chi nhánh:</span>
                  <span className="font-semibold text-emerald-800">{booking.branch_name_snapshot}</span>
                </div>
              )}
              {booking.location_name_snapshot && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Địa điểm:</span>
                  <span className="font-semibold">{booking.location_name_snapshot}</span>
                </div>
              )}
              {booking.location_address_snapshot && (
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500 shrink-0">Địa chỉ:</span>
                  <span className="font-medium text-right text-slate-700">{booking.location_address_snapshot}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Sân:</span>
                <span className="font-semibold">{booking.court_name_snapshot}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Ngày chơi:</span>
                <span className="font-semibold">{booking.play_date}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Khung giờ:</span>
                <span className="font-semibold">
                  {String(booking.start_hour).padStart(2, '0')}:00 - {String(booking.end_hour).padStart(2, '0')}:00
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Khách hàng:</span>
                <span className="font-semibold">{booking.customer_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Tổng thanh toán:</span>
                <span className="font-bold text-emerald-700">{formatVND(booking.total_amount)}</span>
              </div>
              <div className="mt-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
                <Mail className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  Email kèm ảnh QR đã được gửi qua RabbitMQ Notification Service (có thể kiểm tra hộp thư demo Mailpit tại cổng <code>:8025</code>).
                </span>
              </div>
            </div>

            <div className="bg-slate-50 border border-dashed border-emerald-400 rounded-2xl p-6 text-center">
              <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-800 uppercase mb-3">
                <QrCode className="w-4 h-4" />
                <span>Mã QR Check-in tại sân</span>
              </div>
              {ticket?.qr_image_base64 ? (
                <>
                  <img
                    src={ticket.qr_image_base64}
                    alt="Ticket QR"
                    className="w-52 h-52 mx-auto rounded-lg bg-white p-2 border border-slate-200 shadow-sm"
                  />
                  <div className="mt-3 text-[11px] text-slate-500 break-all font-mono bg-white p-2 rounded border border-slate-200">
                    {ticket.qr_payload}
                  </div>
                  <div className="mt-2">
                    <span
                      className={`inline-block text-xs font-bold px-3 py-1 rounded-full ${
                        ticket.status === 'CHECKED_IN'
                          ? 'bg-blue-100 text-blue-800'
                          : ticket.status === 'REVOKED'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      Trạng thái vé: {ticket.status}
                    </span>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500 py-10">Đang sinh mã QR qua RabbitMQ...</p>
              )}
            </div>
          </div>

          <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-between items-center">
            <Link to="/" className="text-sm font-semibold text-emerald-700 hover:underline">
              ← Đặt thêm sân khác
            </Link>
            <Link to="/lookup" className="text-sm font-semibold text-slate-700 hover:underline">
              Tra cứu vé
            </Link>
          </div>
        </div>
      ) : booking.status === 'CANCELLED' || booking.status === 'EXPIRED' ? (
        <div className="bg-white rounded-2xl border border-red-200 p-8 text-center shadow-sm">
          <XCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
          <h1 className="text-xl font-bold text-slate-900">
            Đơn đặt sân đã {booking.status === 'EXPIRED' ? 'hết hạn giữ chỗ' : 'bị hủy'}
          </h1>
          <p className="text-sm text-slate-600 mt-1">{booking.cancel_reason || 'Các khung giờ đã được giải phóng.'}</p>
          <Link
            to="/"
            className="inline-block mt-5 bg-emerald-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold"
          >
            Đặt lịch mới
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-bold text-slate-900">Chuyển khoản VietQR giữ sân</h1>
              <p className="text-xs text-slate-600">
                Mã đơn: <strong className="text-slate-900">{booking.booking_code}</strong> • Vui lòng thanh toán trước khi hết giờ
              </p>
            </div>
            <div className="flex items-center gap-2 bg-amber-100 text-amber-900 px-3.5 py-2 rounded-xl font-mono font-bold text-base">
              <Clock className="w-4 h-4" />
              <span>
                {mm}:{ss}
              </span>
            </div>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
            <div className="text-center bg-slate-50 rounded-2xl p-5 border border-slate-200">
              {payment?.qr_image_url ? (
                <img
                  src={payment.qr_image_url}
                  alt="VietQR"
                  className="w-64 mx-auto rounded-xl border border-slate-200 bg-white shadow-sm"
                />
              ) : (
                <div className="py-16 text-sm text-slate-500">Đang tạo mã VietQR...</div>
              )}
              <p className="text-xs text-slate-500 mt-3">Quét bằng ứng dụng ngân hàng bất kỳ hỗ trợ VietQR</p>
            </div>

            <div className="space-y-4">
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-2 text-sm">
                {booking.branch_name_snapshot && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Chi nhánh:</span>
                    <span className="font-semibold text-emerald-800">{booking.branch_name_snapshot}</span>
                  </div>
                )}
                {booking.location_name_snapshot && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Địa điểm:</span>
                    <span className="font-semibold">{booking.location_name_snapshot}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-slate-500">Sân:</span>
                  <span className="font-semibold">{booking.court_name_snapshot}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Thời gian:</span>
                  <span className="font-semibold">
                    {booking.play_date} ({String(booking.start_hour).padStart(2, '0')}:00 -{' '}
                    {String(booking.end_hour).padStart(2, '0')}:00)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Chủ tài khoản:</span>
                  <span className="font-semibold">{payment?.bank_account_name || 'SAN PICKLEBALL SOA'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Số tài khoản:</span>
                  <span className="font-mono font-semibold">{payment?.bank_account_no || '0123456789'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Nội dung CK:</span>
                  <button
                    type="button"
                    onClick={() => {
                      if (payment?.transfer_content) {
                        navigator.clipboard.writeText(payment.transfer_content);
                        setCopied(true);
                        setTimeout(() => setCopied(false), 1500);
                      }
                    }}
                    className="inline-flex items-center gap-1 font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200"
                  >
                    <span>{payment?.transfer_content || `PKB ${booking.booking_code}`}</span>
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
                {copied && <div className="text-right text-[11px] text-emerald-600">Đã sao chép nội dung CK!</div>}
                <div className="pt-2 border-t border-slate-200 flex justify-between items-center">
                  <span className="font-medium">Số tiền cần chuyển:</span>
                  <span className="text-xl font-bold text-emerald-700">{formatVND(booking.total_amount)}</span>
                </div>
              </div>

              <button
                type="button"
                disabled={simulating}
                onClick={handleSimulatePayment}
                className="w-full flex items-center justify-center gap-2 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-semibold py-3 rounded-xl text-sm transition shadow-sm"
              >
                <Zap className="w-4 h-4 text-lime-300" />
                <span>{simulating ? 'Đang xử lý Webhook...' : 'Giả lập Ngân hàng Xác nhận (Demo Webhook)'}</span>
              </button>

              <button
                type="button"
                onClick={handleCancelBooking}
                className="w-full border border-red-200 text-red-600 hover:bg-red-50 font-medium py-2.5 rounded-xl text-sm transition"
              >
                Hủy đơn & Nhả khung giờ
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
