import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, CalendarDays, Clock, Flame, Info, MapPin, RefreshCw, Sparkles } from 'lucide-react';
import { apiRequest, formatVND, todayVN } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { AvailabilityResponse, BookingOrder, BranchItem, CourtAvailability } from '../types';

export const BookingPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [playDate, setPlayDate] = useState<string>(todayVN());
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [filterBranchId, setFilterBranchId] = useState<string>('');
  const [filterLocationId, setFilterLocationId] = useState<string>('');

  const [availability, setAvailability] = useState<AvailabilityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const [selectedCourtId, setSelectedCourtId] = useState<string | null>(null);
  const [selectedHours, setSelectedHours] = useState<number[]>([]);

  const [customerName, setCustomerName] = useState(user?.full_name || '');
  const [customerPhone, setCustomerPhone] = useState(user?.phone || '');
  const [customerEmail, setCustomerEmail] = useState(user?.email || '');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      setCustomerName((prev) => prev || user.full_name);
      setCustomerPhone((prev) => prev || user.phone);
      setCustomerEmail((prev) => prev || user.email);
    }
  }, [user]);

  useEffect(() => {
    apiRequest<BranchItem[]>('/api/branches')
      .then((data) => setBranches(data))
      .catch(() => undefined);
  }, []);

  const loadAvailability = useCallback(
    async (targetDate: string, branchId: string, locationId: string) => {
      setLoading(true);
      setError('');
      try {
        const params = new URLSearchParams({ date: targetDate });
        if (locationId) params.set('location_id', locationId);
        else if (branchId) params.set('branch_id', branchId);
        const data = await apiRequest<AvailabilityResponse>(`/api/courts/availability?${params.toString()}`);
        setAvailability(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không tải được lịch sân');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    setSelectedCourtId(null);
    setSelectedHours([]);
    loadAvailability(playDate, filterBranchId, filterLocationId);
  }, [playDate, filterBranchId, filterLocationId, loadAvailability]);

  const activeFilterBranch = branches.find((b) => b.id === filterBranchId) || null;

  const handleToggleSlot = (courtItem: CourtAvailability, hour: number, status: string) => {
    if (status !== 'AVAILABLE') return;
    setError('');

    if (selectedCourtId !== courtItem.court.id) {
      setSelectedCourtId(courtItem.court.id);
      setSelectedHours([hour]);
      return;
    }

    if (selectedHours.includes(hour)) {
      const next = selectedHours.filter((h) => h !== hour).sort((a, b) => a - b);
      if (next.length > 1) {
        const isContiguous = next.every((val, idx) => idx === 0 || val === next[idx - 1] + 1);
        if (!isContiguous) {
          setSelectedHours([hour]);
          return;
        }
      }
      setSelectedHours(next);
      if (next.length === 0) setSelectedCourtId(null);
      return;
    }

    const candidate = [...selectedHours, hour].sort((a, b) => a - b);
    const isContiguous = candidate.every((val, idx) => idx === 0 || val === candidate[idx - 1] + 1);
    if (!isContiguous) {
      setError('Vui lòng chọn các khung giờ liên tiếp nhau trên cùng một sân.');
      return;
    }
    if (candidate.length > 6) {
      setError('Mỗi đơn đặt tối đa 6 khung giờ liên tiếp.');
      return;
    }
    setSelectedHours(candidate);
  };

  const selectedCourt = availability?.courts.find((c) => c.court.id === selectedCourtId) || null;
  const totalAmount =
    selectedCourt?.slots
      .filter((s) => selectedHours.includes(s.start_hour))
      .reduce((acc, s) => acc + s.price, 0) || 0;

  const handleCreateBooking = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCourtId || selectedHours.length === 0) {
      setError('Vui lòng chọn ít nhất 1 khung giờ trống.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const order = await apiRequest<BookingOrder>('/api/bookings', {
        method: 'POST',
        body: JSON.stringify({
          court_id: selectedCourtId,
          play_date: playDate,
          hours: selectedHours,
          customer_name: customerName,
          customer_phone: customerPhone,
          customer_email: customerEmail,
        }),
      });
      navigate(`/checkout/${order.booking_code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đặt sân thất bại');
      loadAvailability(playDate, filterBranchId, filterLocationId);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="bg-gradient-to-r from-emerald-800 to-teal-700 text-white rounded-2xl p-6 mb-5 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 bg-lime-400/20 text-lime-300 text-xs font-semibold px-2.5 py-1 rounded-full mb-2">
            <Sparkles className="w-3.5 h-3.5" /> Đặt sân trực tuyến 24/7 • Nhận vé QR kèm Địa chỉ sân qua Email
          </span>
          <h1 className="text-2xl font-bold">Đặt sân Pickleball theo Chi nhánh & Khung giờ</h1>
          <p className="text-sm text-emerald-100 mt-1">
            Chọn chi nhánh, địa điểm và các slot 60 phút liên tiếp, chuyển khoản VietQR và nhận mã QR vào sân ngay.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-white/10 backdrop-blur px-4 py-3 rounded-xl border border-white/20">
          <CalendarDays className="w-5 h-5 text-lime-300" />
          <div>
            <label className="block text-[11px] text-emerald-200 uppercase font-semibold">Ngày chơi</label>
            <input
              type="date"
              min={todayVN()}
              value={playDate}
              onChange={(e) => setPlayDate(e.target.value)}
              className="bg-transparent text-white font-semibold text-sm focus:outline-none [color-scheme:dark]"
            />
          </div>
          <button
            onClick={() => loadAvailability(playDate, filterBranchId, filterLocationId)}
            className="ml-2 p-2 rounded-lg hover:bg-white/15 transition"
            title="Làm mới lịch sân"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Branch & Location Filter Bar */}
      <div className="bg-white px-4 py-3 rounded-xl border border-slate-200 mb-4 flex flex-wrap items-center gap-3 shadow-sm">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <Building2 className="w-4 h-4 text-emerald-700" />
          <span>Chi nhánh:</span>
          <select
            value={filterBranchId}
            onChange={(e) => {
              setFilterBranchId(e.target.value);
              setFilterLocationId('');
            }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="">Tất cả chi nhánh</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.display_name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <MapPin className="w-4 h-4 text-emerald-700" />
          <span>Địa điểm:</span>
          <select
            value={filterLocationId}
            onChange={(e) => setFilterLocationId(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="">
              {activeFilterBranch ? `Tất cả địa điểm thuộc ${activeFilterBranch.display_name}` : 'Tất cả địa điểm'}
            </option>
            {(activeFilterBranch
              ? activeFilterBranch.locations
              : branches.flatMap((b) => b.locations)
            ).map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.branch_name} • {loc.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 mb-5 bg-white px-4 py-2.5 rounded-xl border border-slate-200">
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-white border border-emerald-400 inline-block" />
          <span>Trống (Giờ thường)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-amber-50 border border-amber-400 inline-block" />
          <span className="flex items-center gap-1">
            Trống (Giờ cao điểm 16h–22h <Flame className="w-3.5 h-3.5 text-amber-500" />)
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-emerald-600 inline-block" />
          <span>Đang chọn</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-yellow-100 border border-yellow-400 inline-block" />
          <span>Đang giữ chỗ (15p)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-slate-200 inline-block" />
          <span>Đã đặt / Quá giờ / Bảo trì</span>
        </div>
        {availability?.is_weekend && (
          <span className="ml-auto text-amber-700 font-semibold bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
            Đang áp dụng bảng giá Cuối tuần
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-sm text-red-700 flex items-center gap-2">
          <Info className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Courts & Time Grid */}
        <div className="lg:col-span-2 space-y-4">
          {loading ? (
            <div className="bg-white rounded-2xl p-10 text-center text-slate-500 border border-slate-200">
              Đang tải lịch trống các sân...
            </div>
          ) : availability?.courts.length === 0 ? (
            <div className="bg-white rounded-2xl p-10 text-center text-slate-500 border border-slate-200">
              Chưa có sân hoạt động tại chi nhánh / địa điểm đang chọn.
            </div>
          ) : (
            availability?.courts.map((item) => (
              <div key={item.court.id} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-bold text-slate-900">{item.court.name}</h2>
                      <span
                        className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                          item.court.court_type === 'INDOOR'
                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                            : 'bg-teal-50 text-teal-700 border border-teal-200'
                        }`}
                      >
                        {item.court.court_type === 'INDOOR' ? 'Trong nhà (Mái che)' : 'Ngoài trời'}
                      </span>
                      {item.court.branch_name && (
                        <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {item.court.branch_name} • {item.court.location_name}
                        </span>
                      )}
                      {item.court.status === 'MAINTENANCE' && (
                        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-700">
                          Đang bảo trì
                        </span>
                      )}
                    </div>
                    {item.court.location_address && (
                      <p className="text-xs text-slate-600 mt-1 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-emerald-700 shrink-0" />
                        <span>{item.court.location_address}</span>
                      </p>
                    )}
                    {item.court.description && (
                      <p className="text-xs text-slate-500 mt-0.5">{item.court.description}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                  {item.slots.map((slot) => {
                    const isSelected = selectedCourtId === item.court.id && selectedHours.includes(slot.start_hour);
                    let cls =
                      'border rounded-xl p-2 text-center transition flex flex-col items-center justify-center ';
                    if (isSelected) {
                      cls += 'bg-emerald-600 border-emerald-700 text-white shadow-sm cursor-pointer';
                    } else if (slot.status === 'AVAILABLE') {
                      cls += slot.is_peak_hour
                        ? 'bg-amber-50/70 border-amber-300 hover:border-emerald-600 hover:bg-emerald-50 text-slate-800 cursor-pointer'
                        : 'bg-white border-emerald-200 hover:border-emerald-600 hover:bg-emerald-50 text-slate-800 cursor-pointer';
                    } else if (slot.status === 'LOCKED') {
                      cls += 'bg-yellow-50 border-yellow-300 text-yellow-800 cursor-not-allowed opacity-80';
                    } else if (slot.status === 'PAST') {
                      cls += 'bg-slate-100/70 border-slate-200 text-slate-400 cursor-not-allowed opacity-70';
                    } else {
                      cls += 'bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed';
                    }

                    return (
                      <button
                        key={slot.start_hour}
                        type="button"
                        disabled={slot.status !== 'AVAILABLE' && !isSelected}
                        onClick={() => handleToggleSlot(item, slot.start_hour, slot.status)}
                        className={cls}
                      >
                        <span className={`text-xs font-bold ${slot.status === 'PAST' ? 'line-through' : ''}`}>
                          {String(slot.start_hour).padStart(2, '0')}:00
                        </span>
                        <span className={`text-[11px] mt-0.5 ${isSelected ? 'text-emerald-100' : 'text-slate-500'}`}>
                          {slot.status === 'AVAILABLE'
                            ? `${Math.round(slot.price / 1000)}k`
                            : slot.status === 'LOCKED'
                            ? 'Giữ chỗ'
                            : slot.status === 'PAST'
                            ? 'Quá giờ'
                            : slot.status === 'MAINTENANCE'
                            ? 'Bảo trì'
                            : 'Đã đặt'}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Sticky Booking Summary Form */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm sticky top-20">
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-emerald-700" />
            <span>Thông tin đặt sân</span>
          </h3>

          {selectedCourt && selectedHours.length > 0 ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3.5 mb-4 text-sm space-y-1.5">
              <div className="font-bold text-emerald-950">{selectedCourt.court.name}</div>
              {selectedCourt.court.branch_name && (
                <div className="text-xs font-semibold text-emerald-800">
                  {selectedCourt.court.branch_name} • {selectedCourt.court.location_name}
                </div>
              )}
              {selectedCourt.court.location_address && (
                <div className="text-xs text-emerald-700">{selectedCourt.court.location_address}</div>
              )}
              <div className="text-emerald-800 pt-1">
                Ngày chơi: <span className="font-semibold">{playDate}</span>
              </div>
              <div className="text-emerald-800">
                Khung giờ:{' '}
                <span className="font-semibold">
                  {String(selectedHours[0]).padStart(2, '0')}:00 -{' '}
                  {String(selectedHours[selectedHours.length - 1] + 1).padStart(2, '0')}:00
                </span>{' '}
                ({selectedHours.length} giờ)
              </div>
              <div className="pt-2 border-t border-emerald-200 flex items-center justify-between">
                <span className="font-medium text-emerald-900">Tổng thanh toán:</span>
                <span className="text-lg font-bold text-emerald-700">{formatVND(totalAmount)}</span>
              </div>
            </div>
          ) : (
            <div className="bg-slate-50 border border-dashed border-slate-300 rounded-xl p-4 mb-4 text-xs text-slate-500 text-center">
              Hãy bấm chọn các ô khung giờ còn trống ở bên trái để bắt đầu đặt sân.
            </div>
          )}

          <form onSubmit={handleCreateBooking} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Họ và tên người đặt *</label>
              <input
                type="text"
                required
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Nguyễn Văn A"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Số điện thoại *</label>
              <input
                type="tel"
                required
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                placeholder="0901234567"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email nhận mã QR check-in *
              </label>
              <input
                type="email"
                required
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="email@gmail.com"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={submitting || selectedHours.length === 0}
              className="w-full bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-semibold py-3 rounded-xl text-sm transition shadow-sm"
            >
              {submitting ? 'Đang khóa sân & tạo đơn...' : 'Tiếp tục thanh toán VietQR'}
            </button>
            <p className="text-[11px] text-slate-500 text-center">
              Hệ thống sẽ giữ chỗ sân cho bạn trong 15 phút để hoàn tất chuyển khoản.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};
