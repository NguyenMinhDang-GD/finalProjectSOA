import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, MapPin, Search, Ticket } from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND } from '../api/client';
import { Button } from '../components/ui/Button';
import { AlertBanner, EmptyState, LoadingSkeleton } from '../components/ui/FeedbackStates';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { BookingOrder } from '../types';

export const LookupPage: React.FC = () => {
  const [code, setCode] = useState('');
  const [booking, setBooking] = useState<BookingOrder | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true);
    setError('');
    setBooking(null);
    try {
      const data = await apiRequest<BookingOrder>(`/api/bookings/lookup/${code.trim()}`);
      setBooking(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tìm thấy đơn đặt sân');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
      <div className="bg-white rounded-2xl border border-[#D4D6CD] p-6 sm:p-8 shadow-sm">
        <h1 className="text-xl font-bold text-charcoal flex items-center gap-2 mb-1.5">
          <Search className="w-5 h-5 text-court" aria-hidden="true" />
          <span>Tra cứu đơn đặt sân &amp; Vé QR</span>
        </h1>
        <p className="text-sm text-court-muted mb-5">
          Dành cho cả khách đặt nhanh không cần đăng nhập. Nhập mã đặt sân (ví dụ:{' '}
          <code className="font-mono text-charcoal bg-warm-white px-1.5 py-0.5 rounded">
            PKB-20261124-XXXX
          </code>
          ).
        </p>

        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2.5">
          <label htmlFor="lookup-booking-code" className="sr-only">
            Mã đặt sân
          </label>
          <input
            id="lookup-booking-code"
            type="text"
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Nhập mã đơn PKB-..."
            className="flex-1 rounded-lg border border-[#D4D6CD] px-3.5 py-2.5 text-sm font-mono focus:ring-2 focus:ring-court focus:outline-none"
          />
          <Button type="submit" variant="primary" size="md" loading={loading}>
            {loading ? 'Đang tìm...' : 'Tra cứu'}
          </Button>
        </form>

        {error && (
          <div className="mt-4">
            <AlertBanner tone="error">{error}</AlertBanner>
          </div>
        )}

        {booking && (
          <div className="mt-6 p-5 rounded-xl bg-warm-white border border-[#D4D6CD] space-y-2.5 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-[#D4D6CD]">
              <span className="font-mono font-bold text-base text-charcoal">
                {booking.booking_code}
              </span>
              <StatusBadge status={booking.status} />
            </div>
            <div className="font-bold text-charcoal">{booking.court_name_snapshot}</div>
            {(booking.branch_name_snapshot || booking.location_name_snapshot) && (
              <div className="text-xs text-court flex items-start gap-1.5">
                <MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
                <span>
                  <strong>{booking.branch_name_snapshot}</strong> • {booking.location_name_snapshot}
                  {booking.location_address_snapshot ? ` (${booking.location_address_snapshot})` : ''}
                </span>
              </div>
            )}
            <div className="flex justify-between pt-1">
              <span className="text-court-muted">Thời gian:</span>
              <span className="font-semibold tabular-nums">
                {formatDateVN(booking.play_date)} ({formatHourRange(booking.start_hour, booking.end_hour)})
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-court-muted">Tổng tiền:</span>
              <span className="font-bold text-court tabular-nums">{formatVND(booking.total_amount)}</span>
            </div>
            <div className="pt-2">
              <Link
                to={`/checkout/${booking.booking_code}`}
                className="inline-flex items-center gap-1.5 text-court font-bold hover:underline"
              >
                <span>Mở trang Thanh toán / Vé QR</span>
                <ExternalLink className="w-4 h-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export const MyBookingsPage: React.FC = () => {
  const { user } = useAuth();
  const [orders, setOrders] = useState<BookingOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadOrders = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest<BookingOrder[]>('/api/bookings/my');
      setOrders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được lịch sử đặt sân');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  if (!user) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12">
        <EmptyState
          title="Vui lòng đăng nhập"
          description="Đăng nhập tài khoản thành viên để xem toàn bộ lịch sử đặt sân và vé QR của bạn."
          action={
            <Link
              to="/login"
              className="inline-block bg-court text-white font-semibold px-5 py-2.5 rounded-lg text-sm"
            >
              Đăng nhập ngay
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-charcoal flex items-center gap-2">
          <Ticket className="w-5 h-5 text-court" aria-hidden="true" />
          <span>Lịch sử đặt sân — {user.full_name}</span>
        </h1>
        <Link
          to="/"
          className="text-xs font-bold text-court bg-[#E9EFEA] hover:bg-[#DCE7DF] px-3.5 py-2 rounded-lg transition-colors"
        >
          + Đặt sân mới
        </Link>
      </div>

      {error && (
        <AlertBanner tone="error" onRetry={loadOrders}>
          {error}
        </AlertBanner>
      )}

      {loading ? (
        <LoadingSkeleton rows={4} />
      ) : !error && orders.length === 0 ? (
        <EmptyState
          title="Bạn chưa có đơn đặt sân nào"
          description="Chọn chi nhánh và khung giờ phù hợp để tạo đơn đặt sân đầu tiên."
          action={
            <Link
              to="/"
              className="inline-block bg-court text-white font-semibold px-5 py-2.5 rounded-lg text-sm"
            >
              Đặt sân ngay
            </Link>
          }
        />
      ) : !error ? (
        <div className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto shadow-sm">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Sân</th>
                <th className="px-4 py-3">Ngày &amp; Giờ</th>
                <th className="px-4 py-3">Tổng tiền</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {orders.map((o) => (
                <tr key={o.id} className="hover:bg-warm-white/60">
                  <td className="px-4 py-3 font-mono font-bold text-charcoal whitespace-nowrap">
                    {o.booking_code}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-charcoal">{o.court_name_snapshot}</div>
                    {o.branch_name_snapshot && (
                      <div className="text-xs text-court-muted">
                        {o.branch_name_snapshot} • {o.location_name_snapshot}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 tabular-nums whitespace-nowrap">
                    {formatDateVN(o.play_date)} ({formatHourRange(o.start_hour, o.end_hour)})
                  </td>
                  <td className="px-4 py-3 font-bold text-court tabular-nums whitespace-nowrap">
                    {formatVND(o.total_amount)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <Link
                      to={`/checkout/${o.booking_code}`}
                      className="text-court font-bold hover:underline"
                    >
                      Chi tiết / Vé QR
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
};
