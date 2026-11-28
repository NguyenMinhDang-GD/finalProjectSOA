import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ExternalLink, MapPin, Plus, Search, Ticket } from 'lucide-react';
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
      const data = await apiRequest<BookingOrder>(
        `/api/bookings/lookup/${code.trim()}`,
        {},
        code.trim()
      );
      setBooking(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tìm thấy đơn đặt sân');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-6">
      <div className="space-y-2">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-terracotta">
          Tra cứu nhanh
        </div>
        <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal">
          Tra cứu đơn đặt sân &amp; Vé QR
        </h1>
        <p className="text-sm text-court-muted">
          Dành cho cả khách đặt nhanh không cần tài khoản. Nhập mã đơn (ví dụ:{' '}
          <code className="font-mono text-charcoal bg-white px-1.5 py-0.5 rounded border border-[#DCDCD2]">
            PKB-20261124-XXXX
          </code>
          ) để xem trạng thái hoặc mở vé QR.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-[#CFCFC4] p-6 sm:p-8 shadow-sm">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
          <label htmlFor="lookup-booking-code" className="sr-only">
            Mã đặt sân
          </label>
          <div className="relative flex-1">
            <Search
              className="w-4 h-4 text-court-muted absolute left-3.5 top-1/2 -translate-y-1/2"
              aria-hidden="true"
            />
            <input
              id="lookup-booking-code"
              type="text"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Nhập mã đơn PKB-..."
              className="w-full rounded-xl border border-[#CFCFC4] pl-10 pr-4 py-3 text-sm font-mono focus:ring-2 focus:ring-court focus:border-court focus:outline-none"
            />
          </div>
          <Button type="submit" variant="primary" size="lg" loading={loading}>
            {loading ? 'Đang tìm...' : 'Tra cứu đơn'}
          </Button>
        </form>

        {error && (
          <div className="mt-5">
            <AlertBanner tone="error">{error}</AlertBanner>
          </div>
        )}

        {booking && (
          <div className="mt-6 p-5 rounded-xl bg-warm-white border border-[#CFCFC4] space-y-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#DCDCD2]">
              <span className="font-mono font-bold text-base text-charcoal">
                {booking.booking_code}
              </span>
              <StatusBadge status={booking.status} />
            </div>

            <div>
              <div className="font-display text-lg font-bold text-charcoal">
                {booking.court_name_snapshot}
              </div>
              {(booking.branch_name_snapshot || booking.location_name_snapshot) && (
                <div className="text-xs text-court mt-1 flex items-start gap-1.5">
                  <MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5 text-terracotta" aria-hidden="true" />
                  <span>
                    <strong>{booking.branch_name_snapshot}</strong> • {booking.location_name_snapshot}
                    {booking.location_address_snapshot ? ` (${booking.location_address_snapshot})` : ''}
                  </span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-sm">
              <div className="flex justify-between sm:block">
                <span className="text-court-muted text-xs block">Thời gian</span>
                <span className="font-mono font-semibold tabular-nums">
                  {formatDateVN(booking.play_date)} ({formatHourRange(booking.start_hour, booking.end_hour)})
                </span>
              </div>
              <div className="flex justify-between sm:block sm:text-right">
                <span className="text-court-muted text-xs block">Tổng thanh toán</span>
                <span className="font-mono font-bold text-court tabular-nums">
                  {formatVND(booking.total_amount)}
                </span>
              </div>
            </div>

            <div className="pt-3 border-t border-[#DCDCD2] flex justify-end">
              <Link
                to={`/checkout/${booking.booking_code}`}
                className="inline-flex items-center gap-1.5 bg-court hover:bg-court-soft text-white font-semibold px-4 py-2 rounded-lg text-xs transition-colors"
              >
                <span>Mở trang Thanh toán / Vé QR</span>
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
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
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#DCDCD2] pb-5">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-terracotta">
            Tài khoản thành viên
          </div>
          <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal mt-1 flex items-center gap-2.5">
            <Ticket className="w-6 h-6 text-court" aria-hidden="true" />
            <span>Lịch sử đặt sân — {user.full_name}</span>
          </h1>
        </div>
        <Link
          to="/book"
          className="inline-flex items-center gap-1.5 bg-court hover:bg-court-soft text-white font-semibold px-4 py-2.5 rounded-xl text-sm transition-colors"
        >
          <Plus className="w-4 h-4 text-ball-lime" aria-hidden="true" />
          <span>Đặt sân mới</span>
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
              to="/book"
              className="inline-block bg-court text-white font-semibold px-5 py-2.5 rounded-lg text-sm"
            >
              Đặt sân ngay
            </Link>
          }
        />
      ) : !error ? (
        <div className="bg-white rounded-2xl border border-[#CFCFC4] overflow-x-auto shadow-sm">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#DCDCD2] text-[11px] uppercase tracking-wider text-court-muted">
              <tr>
                <th className="px-4 py-3.5">Mã đơn</th>
                <th className="px-4 py-3.5">Sân &amp; Chi nhánh</th>
                <th className="px-4 py-3.5">Ngày &amp; Khung giờ</th>
                <th className="px-4 py-3.5">Tổng tiền</th>
                <th className="px-4 py-3.5">Trạng thái</th>
                <th className="px-4 py-3.5 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {orders.map((o) => (
                <tr key={o.id} className="hover:bg-warm-white/60 transition-colors">
                  <td className="px-4 py-3.5 font-mono font-bold text-charcoal whitespace-nowrap">
                    {o.booking_code}
                  </td>
                  <td className="px-4 py-3.5">
                    <div className="font-semibold text-charcoal">{o.court_name_snapshot}</div>
                    {o.branch_name_snapshot && (
                      <div className="text-xs text-court-muted">
                        {o.branch_name_snapshot} • {o.location_name_snapshot}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3.5 font-mono text-xs sm:text-sm tabular-nums whitespace-nowrap">
                    {formatDateVN(o.play_date)} ({formatHourRange(o.start_hour, o.end_hour)})
                  </td>
                  <td className="px-4 py-3.5 font-mono font-bold text-court tabular-nums whitespace-nowrap">
                    {formatVND(o.total_amount)}
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge status={o.status} />
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap text-right">
                    <Link
                      to={`/checkout/${o.booking_code}`}
                      className="inline-flex items-center gap-1 text-court font-bold hover:underline"
                    >
                      <span>Chi tiết / Vé QR</span>
                      <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
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
