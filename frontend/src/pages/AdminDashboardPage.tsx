import React, { useCallback, useEffect, useState } from 'react';
import { BarChart3, Building2, Coins, Mail, PlusCircle, ShieldCheck } from 'lucide-react';
import { apiRequest, formatVND } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { AdminStats, BookingOrder, Court, NotificationLog, PricingRule } from '../types';

export const AdminDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState<'courts' | 'pricing' | 'bookings' | 'emails'>('courts');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [courts, setCourts] = useState<Court[]>([]);
  const [rules, setRules] = useState<PricingRule[]>([]);
  const [bookings, setBookings] = useState<BookingOrder[]>([]);
  const [emails, setEmails] = useState<NotificationLog[]>([]);
  const [newCourtName, setNewCourtName] = useState('');
  const [newCourtType, setNewCourtType] = useState<'INDOOR' | 'OUTDOOR'>('OUTDOOR');
  const [priceEdits, setPriceEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');

  const loadAll = useCallback(async () => {
    try {
      const [s, c, r, b, e] = await Promise.all([
        apiRequest<AdminStats>('/api/bookings/admin/stats'),
        apiRequest<Court[]>('/api/courts?include_inactive=true'),
        apiRequest<PricingRule[]>('/api/pricing-rules'),
        apiRequest<BookingOrder[]>('/api/bookings/admin/list'),
        apiRequest<NotificationLog[]>('/api/notifications/logs'),
      ]);
      setStats(s);
      setCourts(c);
      setRules(r);
      setBookings(b);
      setEmails(e);
      const map: Record<string, string> = {};
      r.forEach((rule) => {
        map[rule.id] = String(rule.price_per_hour);
      });
      setPriceEdits(map);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (user?.role === 'ADMIN') loadAll();
  }, [user, loadAll]);

  const handleAddCourt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCourtName.trim()) return;
    await apiRequest('/api/courts', {
      method: 'POST',
      body: JSON.stringify({
        name: newCourtName.trim(),
        court_type: newCourtType,
        description: 'Sân mới được thêm bởi Quản trị viên',
      }),
    });
    setNewCourtName('');
    setMessage('Đã thêm sân mới thành công');
    loadAll();
  };

  const handleToggleCourtStatus = async (court: Court) => {
    const nextStatus = court.status === 'ACTIVE' ? 'MAINTENANCE' : 'ACTIVE';
    await apiRequest(`/api/courts/${court.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: nextStatus }),
    });
    loadAll();
  };

  const handleSavePrice = async (ruleId: string) => {
    const val = Number(priceEdits[ruleId]);
    if (!val || val <= 0) return;
    await apiRequest(`/api/pricing-rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify({ price_per_hour: val }),
    });
    setMessage('Đã cập nhật bảng giá');
    loadAll();
  };

  const handleAdminCancel = async (bookingCode: string) => {
    await apiRequest(`/api/bookings/admin/${bookingCode}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'Admin hủy đơn ngoại lệ' }),
    });
    setMessage(`Đã hủy đơn ${bookingCode}`);
    loadAll();
  };

  if (!user || user.role !== 'ADMIN') {
    return (
      <div className="max-w-xl mx-auto mt-10 bg-white p-6 rounded-2xl border border-red-200 text-center text-red-700 font-medium">
        Chỉ tài khoản Quản trị viên (ADMIN) mới có quyền truy cập trang này.
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-emerald-700" />
          <span>Bảng điều khiển Quản trị Sân (Admin)</span>
        </h1>
        {message && (
          <span className="text-xs font-semibold bg-emerald-100 text-emerald-800 px-3 py-1.5 rounded-full">
            {message}
          </span>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Tổng doanh thu (Đã thanh toán)</div>
            <div className="text-xl font-bold text-emerald-700 mt-1">{formatVND(stats.total_revenue)}</div>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Đơn đã thanh toán</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{stats.paid_bookings}</div>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Đơn chờ thanh toán</div>
            <div className="text-xl font-bold text-amber-600 mt-1">{stats.pending_bookings}</div>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Số sân đang hoạt động</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{stats.active_courts}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setTab('courts')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'courts' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <Building2 className="w-4 h-4" /> Quản lý Sân
        </button>
        <button
          onClick={() => setTab('pricing')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'pricing' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <Coins className="w-4 h-4" /> Bảng giá Khung giờ
        </button>
        <button
          onClick={() => setTab('bookings')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'bookings' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <BarChart3 className="w-4 h-4" /> Danh sách Đơn đặt
        </button>
        <button
          onClick={() => setTab('emails')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'emails' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <Mail className="w-4 h-4" /> Nhật ký Email QR
        </button>
      </div>

      {tab === 'courts' && (
        <div className="space-y-4">
          <form onSubmit={handleAddCourt} className="bg-white p-4 rounded-2xl border border-slate-200 flex flex-wrap gap-3">
            <input
              type="text"
              value={newCourtName}
              onChange={(e) => setNewCourtName(e.target.value)}
              placeholder="Tên sân mới (VD: Sân 05 - VIP)..."
              className="flex-1 min-w-[220px] rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
            <select
              value={newCourtType}
              onChange={(e) => setNewCourtType(e.target.value as 'INDOOR' | 'OUTDOOR')}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="INDOOR">Trong nhà (INDOOR)</option>
              <option value="OUTDOOR">Ngoài trời (OUTDOOR)</option>
            </select>
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 bg-emerald-700 text-white px-4 py-2 rounded-xl text-sm font-semibold"
            >
              <PlusCircle className="w-4 h-4" /> Thêm sân
            </button>
          </form>

          <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Tên sân</th>
                  <th className="px-4 py-3">Loại</th>
                  <th className="px-4 py-3">Trạng thái</th>
                  <th className="px-4 py-3">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {courts.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3 font-semibold">{c.name}</td>
                    <td className="px-4 py-3">{c.court_type}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                          c.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleCourtStatus(c)}
                        className="text-xs font-semibold text-emerald-700 hover:underline"
                      >
                        {c.status === 'ACTIVE' ? 'Chuyển Bảo trì' : 'Mở hoạt động'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'pricing' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Loại sân</th>
                <th className="px-4 py-3">Ngày áp dụng</th>
                <th className="px-4 py-3">Khung giờ</th>
                <th className="px-4 py-3">Loại giờ</th>
                <th className="px-4 py-3">Giá / giờ (VNĐ)</th>
                <th className="px-4 py-3">Lưu</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rules.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-3 font-semibold">{r.court_type}</td>
                  <td className="px-4 py-3">{r.is_weekend ? 'Cuối tuần (T7-CN)' : 'Ngày thường (T2-T6)'}</td>
                  <td className="px-4 py-3">
                    {String(r.start_hour).padStart(2, '0')}:00 - {String(r.end_hour).padStart(2, '0')}:00
                  </td>
                  <td className="px-4 py-3">{r.is_peak_hour ? 'Cao điểm' : 'Giờ thường'}</td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      value={priceEdits[r.id] || ''}
                      onChange={(e) => setPriceEdits({ ...priceEdits, [r.id]: e.target.value })}
                      className="w-32 rounded-lg border border-slate-300 px-2.5 py-1 text-sm"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleSavePrice(r.id)}
                      className="bg-emerald-700 text-white px-3 py-1 rounded-lg text-xs font-semibold"
                    >
                      Cập nhật
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'bookings' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Khách hàng</th>
                <th className="px-4 py-3">Sân & Giờ</th>
                <th className="px-4 py-3">Tổng tiền</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {bookings.map((b) => (
                <tr key={b.id}>
                  <td className="px-4 py-3 font-mono font-semibold">{b.booking_code}</td>
                  <td className="px-4 py-3">
                    <div>{b.customer_name}</div>
                    <div className="text-xs text-slate-500">{b.customer_email}</div>
                  </td>
                  <td className="px-4 py-3">
                    {b.court_name_snapshot} • {b.play_date} ({b.start_hour}h–{b.end_hour}h)
                  </td>
                  <td className="px-4 py-3 font-semibold text-emerald-700">{formatVND(b.total_amount)}</td>
                  <td className="px-4 py-3">{b.status}</td>
                  <td className="px-4 py-3">
                    {(b.status === 'PENDING_PAYMENT' || b.status === 'PAID') && (
                      <button
                        onClick={() => handleAdminCancel(b.booking_code)}
                        className="text-xs text-red-600 font-semibold hover:underline"
                      >
                        Hủy ngoại lệ
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'emails' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Email nhận</th>
                <th className="px-4 py-3">Tiêu đề</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Retry</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {emails.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 font-mono font-semibold">{e.booking_code}</td>
                  <td className="px-4 py-3">{e.recipient_email}</td>
                  <td className="px-4 py-3">{e.subject}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                        e.status === 'SENT' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {e.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">{e.retry_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
