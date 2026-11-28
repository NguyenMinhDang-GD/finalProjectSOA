import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, CalendarDays, Clock, Flame, Info, MapPin, RefreshCw } from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND, todayVN } from '../api/client';
import { Button } from '../components/ui/Button';
import { CourtLinesBackdrop } from '../components/ui/CourtHeroGraphic';
import { AlertBanner, EmptyState, LoadingSkeleton } from '../components/ui/FeedbackStates';
import { StatusBadge } from '../components/ui/StatusBadge';
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
    async (targetDate: string, branchId: string, locationId: string, clearError = true) => {
      setLoading(true);
      if (clearError) setError('');
      try {
        const params = new URLSearchParams({ date: targetDate });
        if (locationId) params.set('location_id', locationId);
        else if (branchId) params.set('branch_id', branchId);
        const data = await apiRequest<AvailabilityResponse>(
          `/api/courts/availability?${params.toString()}`
        );
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
          customer_name: customerName.trim(),
          customer_phone: customerPhone.trim(),
          customer_email: customerEmail.trim(),
        }),
      });
      navigate(`/checkout/${order.booking_code}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đặt sân thất bại');
      setSelectedCourtId(null);
      setSelectedHours([]);
      loadAvailability(playDate, filterBranchId, filterLocationId, false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-5">
      {/* Athletic Club Hero */}
      <section className="relative overflow-hidden bg-court text-white rounded-2xl p-6 sm:p-8 border border-court-soft">
        <CourtLinesBackdrop />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-ball-lime mb-2">
              <span>Đặt sân trực tuyến • Xác nhận QR tại sân</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Đặt sân Pickleball theo Chi nhánh &amp; Khung giờ
            </h1>
            <p className="text-sm text-[#C7D6CD] mt-2 leading-relaxed">
              Chọn chi nhánh, địa điểm và các khung giờ 60 phút liên tiếp (tối đa 6 giờ/đơn). Giữ chỗ trong 15 phút để hoàn tất thanh toán VietQR.
            </p>
          </div>

          <div className="flex items-center gap-3 bg-court-deep/80 px-4 py-3 rounded-xl border border-court-soft shrink-0">
            <CalendarDays className="w-5 h-5 text-ball-lime shrink-0" aria-hidden="true" />
            <div>
              <label
                htmlFor="booking-play-date"
                className="block text-[11px] text-[#B7C9BE] uppercase font-semibold tracking-wide"
              >
                Ngày chơi
              </label>
              <input
                id="booking-play-date"
                type="date"
                min={todayVN()}
                value={playDate}
                onChange={(e) => setPlayDate(e.target.value)}
                className="bg-transparent text-white font-semibold text-sm focus:outline-none [color-scheme:dark] tabular-nums"
              />
            </div>
            <button
              type="button"
              onClick={() => loadAvailability(playDate, filterBranchId, filterLocationId)}
              className="ml-2 p-2 rounded-lg text-[#E3EAE5] hover:bg-court-soft hover:text-white transition-colors"
              title="Làm mới lịch sân"
              aria-label="Làm mới lịch sân"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      {/* Branch & Location Filter Bar */}
      <section
        aria-label="Bộ lọc chi nhánh và địa điểm"
        className="bg-white px-4 py-3.5 rounded-xl border border-[#D4D6CD] flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 sm:gap-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2 text-xs font-semibold text-charcoal w-full sm:w-auto min-w-0">
          <div className="flex items-center gap-1.5 shrink-0">
            <Building2 className="w-4 h-4 text-court" aria-hidden="true" />
            <label htmlFor="filter-branch">Chi nhánh:</label>
          </div>
          <select
            id="filter-branch"
            value={filterBranchId}
            onChange={(e) => {
              setFilterBranchId(e.target.value);
              setFilterLocationId('');
            }}
            className="w-full sm:w-auto max-w-full min-w-0 rounded-lg border border-[#D4D6CD] px-3 py-2 sm:py-1.5 text-xs font-medium bg-warm-white text-charcoal focus:outline-none focus:ring-2 focus:ring-court"
          >
            <option value="">Tất cả chi nhánh</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.display_name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2 text-xs font-semibold text-charcoal w-full sm:w-auto min-w-0">
          <div className="flex items-center gap-1.5 shrink-0">
            <MapPin className="w-4 h-4 text-court" aria-hidden="true" />
            <label htmlFor="filter-location">Địa điểm:</label>
          </div>
          <select
            id="filter-location"
            value={filterLocationId}
            onChange={(e) => setFilterLocationId(e.target.value)}
            className="w-full sm:w-auto max-w-full min-w-0 rounded-lg border border-[#D4D6CD] px-3 py-2 sm:py-1.5 text-xs font-medium bg-warm-white text-charcoal focus:outline-none focus:ring-2 focus:ring-court"
          >
            <option value="">
              {activeFilterBranch
                ? `Tất cả địa điểm thuộc ${activeFilterBranch.display_name}`
                : 'Tất cả địa điểm'}
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

        {availability?.is_weekend && (
          <span className="ml-auto text-xs font-semibold text-[#8F4324] bg-[#FDF1EB] px-3 py-1 rounded-md border border-[#E8C1B0]">
            Đang áp dụng bảng giá Cuối tuần
          </span>
        )}
      </section>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-court-muted bg-white px-4 py-2.5 rounded-xl border border-[#D4D6CD]">
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-white border border-court/50 inline-block" />
          <span>Trống (Giờ thường)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-[#FDF1EB] border border-terracotta inline-block" />
          <span className="inline-flex items-center gap-1">
            Trống (Cao điểm 16h–22h <Flame className="w-3.5 h-3.5 text-terracotta" aria-hidden="true" />)
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-court inline-block" />
          <span className="font-semibold text-charcoal">Đang chọn</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-amber-100 border border-amber-400 inline-block" />
          <span>Đang giữ chỗ (15p)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-[#E7E6DC] inline-block" />
          <span>Đã đặt / Quá giờ / Bảo trì</span>
        </div>
      </div>

      {error && (
        <AlertBanner tone="error" onRetry={() => loadAvailability(playDate, filterBranchId, filterLocationId)}>
          {error}
        </AlertBanner>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Courts & Slot Grid */}
        <div className="lg:col-span-2 space-y-4">
          {loading ? (
            <LoadingSkeleton rows={3} />
          ) : !availability || availability.courts.length === 0 ? (
            <EmptyState
              title="Không có sân nào phù hợp bộ lọc"
              description="Thử chọn chi nhánh hoặc địa điểm khác để xem lịch sân trống."
            />
          ) : (
            availability.courts.map((item) => {
              const { court, slots } = item;
              const isMaintenance = court.status === 'MAINTENANCE';

              return (
                <article
                  key={court.id}
                  className="bg-white rounded-2xl border border-[#D4D6CD] p-5 transition-colors"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2 mb-4 pb-3 border-b border-[#ECEBE2]">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-base font-bold text-charcoal">{court.name}</h2>
                        <StatusBadge status={court.court_type} />
                        {isMaintenance && <StatusBadge status="MAINTENANCE" />}
                      </div>
                      {(court.branch_name || court.location_name) && (
                        <p className="text-xs text-court font-medium mt-1 flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                          <span>
                            {court.branch_name} • {court.location_name}
                            {court.location_address ? ` (${court.location_address})` : ''}
                          </span>
                        </p>
                      )}
                      <p className="text-xs text-court-muted mt-0.5">
                        {court.surface}
                        {court.description ? ` • ${court.description}` : ''}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                    {slots.map((slot) => {
                      const isSelected =
                        selectedCourtId === court.id && selectedHours.includes(slot.start_hour);
                      const isAvailable = slot.status === 'AVAILABLE';

                      let btnStyle =
                        'bg-[#ECEBE2] border-[#D4D6CD] text-[#6E746F] cursor-not-allowed';
                      if (isSelected) {
                        btnStyle =
                          'bg-court border-court text-white ring-2 ring-ball-lime font-bold';
                      } else if (isAvailable && slot.is_peak_hour) {
                        btnStyle =
                          'bg-[#FDF1EB] border-[#E0A78E] text-[#7D371B] hover:border-terracotta hover:bg-[#FAE6DC] cursor-pointer';
                      } else if (isAvailable) {
                        btnStyle =
                          'bg-white border-[#C3D1C7] text-charcoal hover:border-court hover:bg-[#F1F5F2] cursor-pointer';
                      } else if (slot.status === 'LOCKED') {
                        btnStyle =
                          'bg-amber-50 border-amber-300 text-amber-900 cursor-not-allowed';
                      }

                      return (
                        <button
                          key={slot.start_hour}
                          type="button"
                          disabled={!isAvailable}
                          aria-pressed={isSelected}
                          aria-label={`${court.name}, khung giờ ${slot.label}, giá ${formatVND(
                            slot.price
                          )}, trạng thái ${slot.status}`}
                          onClick={() => handleToggleSlot(item, slot.start_hour, slot.status)}
                          className={`rounded-xl border px-2 py-2.5 text-center transition-colors min-h-[58px] flex flex-col justify-center ${btnStyle}`}
                        >
                          <div className="text-xs font-bold tabular-nums">{slot.label}</div>
                          <div className="text-[11px] mt-0.5 tabular-nums">
                            {isAvailable
                              ? `${Math.round(slot.price / 1000)}k`
                              : slot.status === 'LOCKED'
                              ? 'Giữ 15p'
                              : slot.status === 'BOOKED'
                              ? 'Đã đặt'
                              : slot.status === 'PAST'
                              ? 'Quá giờ'
                              : 'Bảo trì'}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </article>
              );
            })
          )}
        </div>

        {/* Sticky Booking Summary & Customer Form */}
        <aside className="bg-white rounded-2xl border border-[#D4D6CD] p-5 lg:sticky lg:top-20">
          <div className="flex items-center justify-between pb-3 border-b border-[#ECEBE2] mb-4">
            <h2 className="text-base font-bold text-charcoal flex items-center gap-2">
              <Clock className="w-4 h-4 text-court" aria-hidden="true" />
              <span>Tóm tắt đặt sân</span>
            </h2>
            {selectedHours.length > 0 && (
              <span className="text-xs font-bold bg-court text-ball-lime px-2.5 py-0.5 rounded-md tabular-nums">
                {selectedHours.length} giờ
              </span>
            )}
          </div>

          {selectedCourt && selectedHours.length > 0 ? (
            <div className="bg-warm-white border border-[#D4D6CD] rounded-xl p-3.5 mb-4 text-sm space-y-1.5">
              {selectedCourt.court.branch_name && (
                <div className="flex justify-between gap-2">
                  <span className="text-court-muted">Chi nhánh:</span>
                  <span className="font-semibold text-right text-court">
                    {selectedCourt.court.branch_name}
                  </span>
                </div>
              )}
              {selectedCourt.court.location_name && (
                <div className="flex justify-between gap-2">
                  <span className="text-court-muted">Địa điểm:</span>
                  <span className="font-semibold text-right">
                    {selectedCourt.court.location_name}
                  </span>
                </div>
              )}
              <div className="flex justify-between gap-2">
                <span className="text-court-muted">Sân:</span>
                <span className="font-bold text-charcoal text-right">
                  {selectedCourt.court.name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-court-muted">Ngày chơi:</span>
                <span className="font-semibold tabular-nums">{formatDateVN(playDate)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-court-muted">Khung giờ:</span>
                <span className="font-semibold tabular-nums">
                  {formatHourRange(selectedHours[0], selectedHours[selectedHours.length - 1] + 1)}
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t border-[#D4D6CD] text-base">
                <span className="font-bold text-charcoal">Tạm tính:</span>
                <span className="font-bold text-court tabular-nums">{formatVND(totalAmount)}</span>
              </div>
            </div>
          ) : (
            <div className="bg-warm-white border border-dashed border-[#C9CBC1] rounded-xl p-4 mb-4 text-xs text-court-muted flex items-start gap-2">
              <Info className="w-4 h-4 text-court shrink-0 mt-0.5" aria-hidden="true" />
              <span>Chọn 1 đến 6 khung giờ liên tiếp trên bảng lịch để giữ chỗ.</span>
            </div>
          )}

          <form onSubmit={handleCreateBooking} className="space-y-3.5">
            <div>
              <label htmlFor="cust-name" className="block text-xs font-semibold text-charcoal mb-1">
                Họ và tên
              </label>
              <input
                id="cust-name"
                type="text"
                required
                minLength={2}
                maxLength={150}
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Nguyễn Văn A"
                className="w-full rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-court focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="cust-phone" className="block text-xs font-semibold text-charcoal mb-1">
                Số điện thoại
              </label>
              <input
                id="cust-phone"
                type="tel"
                required
                minLength={8}
                maxLength={20}
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                placeholder="0901234567"
                className="w-full rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-court focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="cust-email" className="block text-xs font-semibold text-charcoal mb-1">
                Email nhận vé QR
              </label>
              <input
                id="cust-email"
                type="email"
                required
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="email@domain.com"
                className="w-full rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-court focus:outline-none"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={submitting}
              disabled={!selectedCourtId || selectedHours.length === 0}
              className="w-full"
            >
              {submitting ? 'Đang giữ chỗ...' : 'Giữ chỗ 15 phút & Thanh toán'}
            </Button>
          </form>
        </aside>
      </div>
    </div>
  );
};
