import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Search, Ticket } from 'lucide-react';
import { apiRequest, formatVND } from '../api/client';
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
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2 mb-2">
          <Search className="w-5 h-5 text-emerald-700" />
          <span>Tra cứu đơn đặt sân & Vé QR</span>
        </h1>
        <p className="text-sm text-slate-500 mb-5">
          Dành cho cả khách đặt nhanh không cần đăng nhập — nhập mã đặt sân (VD: <code>PKB-20261124-XXXX</code>).
        </p>

        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Nhập mã đơn PKB-..."
            className="flex-1 rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-emerald-700 hover:bg-emerald-800 text-white font-semibold px-5 py-2.5 rounded-xl text-sm"
          >
            {loading ? 'Đang tìm...' : 'Tra cứu'}
          </button>
        </form>

        {error && <div className="mt-4 p-3 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}

        {booking && (
          <div className="mt-5 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-bold text-slate-900">{booking.booking_code}</span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                {booking.status}
              </span>
            </div>
            <div>Sân: {booking.court_name_snapshot}</div>
            <div>
              Thời gian: {booking.play_date} ({String(booking.start_hour).padStart(2, '0')}:00 -{' '}
              {String(booking.end_hour).padStart(2, '0')}:00)
            </div>
            <div>Tổng tiền: {formatVND(booking.total_amount)}</div>
            <div className="pt-2">
              <Link
                to={`/checkout/${booking.booking_code}`}
                className="inline-flex items-center gap-1.5 text-emerald-700 font-semibold hover:underline"
              >
                <span>Mở trang Thanh toán / Vé QR</span>
                <ExternalLink className="w-4 h-4" />
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

  useEffect(() => {
    if (!user) return;
    apiRequest<BookingOrder[]>('/api/bookings/my')
      .then(setOrders)
      .finally(() => setLoading(false));
  }, [user]);

  if (!user) {
    return (
      <div className="max-w-xl mx-auto mt-10 text-center bg-white p-6 rounded-2xl border">
        Vui lòng <Link to="/login" className="text-emerald-700 font-semibold underline">đăng nhập</Link> để xem lịch sử đặt sân.
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2 mb-5">
        <Ticket className="w-5 h-5 text-emerald-700" />
        <span>Lịch sử đặt sân của {user.full_name}</span>
      </h1>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto shadow-sm">
        {loading ? (
          <div className="p-8 text-center text-slate-500">Đang tải lịch sử...</div>
        ) : orders.length === 0 ? (
          <div className="p-8 text-center text-slate-500">Bạn chưa có đơn đặt sân nào.</div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Sân</th>
                <th className="px-4 py-3">Ngày & Giờ</th>
                <th className="px-4 py-3">Tổng tiền</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {orders.map((o) => (
                <tr key={o.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono font-semibold">{o.booking_code}</td>
                  <td className="px-4 py-3">{o.court_name_snapshot}</td>
                  <td className="px-4 py-3">
                    {o.play_date} ({String(o.start_hour).padStart(2, '0')}:00–{String(o.end_hour).padStart(2, '0')}:00)
                  </td>
                  <td className="px-4 py-3 font-semibold text-emerald-700">{formatVND(o.total_amount)}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800">
                      {o.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/checkout/${o.booking_code}`}
                      className="text-emerald-700 font-semibold hover:underline"
                    >
                      Chi tiết / Vé QR
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
