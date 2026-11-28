import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Building2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flame,
  Info,
  MapPin,
  RefreshCw,
} from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND, todayVN } from '../api/client';
import courtIndoorImg from '../assets/images/court-indoor.webp';
import courtOutdoorImg from '../assets/images/court-outdoor.webp';
import { Button } from '../components/ui/Button';
import { AlertBanner, EmptyState, LoadingSkeleton } from '../components/ui/FeedbackStates';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { AvailabilityResponse, BookingOrder, BranchItem, CourtAvailability } from '../types';

const VN_WEEKDAYS = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];

function parseLocalIsoDate(isoDate: string): Date {
  const [y, m, d] = isoDate.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function toLocalIsoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function addLocalDays(isoDate: string, delta: number): string {
  const d = parseLocalIsoDate(isoDate);
  d.setDate(d.getDate() + delta);
  return toLocalIsoDate(d);
}

export const BookingPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const minDate = todayVN();

  const [playDate, setPlayDate] = useState<string>(minDate);
  const [stripStart, setStripStart] = useState<string>(minDate);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [filterBranchId, setFilterBranchId] = useState<string>(
    searchParams.get('branch_id') || ''
  );
  const [filterLocationId, setFilterLocationId] = useState<string>('');
  const [filterCourtType, setFilterCourtType] = useState<'ALL' | 'INDOOR' | 'OUTDOOR'>('ALL');

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

  const dateStrip = useMemo(() => {
    return Array.from({ length: 7 }).map((_, idx) => {
      const iso = addLocalDays(stripStart, idx);
      const dt = parseLocalIsoDate(iso);
      return {
        iso,
        weekday: VN_WEEKDAYS[dt.getDay()],
        dayLabel: `${String(dt.getDate()).padStart(2, '0')}/${String(dt.getMonth() + 1).padStart(
          2,
          '0'
        )}`,
        isToday: iso === minDate,
      };
    });
  }, [stripStart, minDate]);

  const activeFilterBranch = branches.find((b) => b.id === filterBranchId) || null;

  const displayedCourts = useMemo(() => {
    if (!availability) return [];
    if (filterCourtType === 'ALL') return availability.courts;
    return availability.courts.filter((c) => c.court.court_type === filterCourtType);
  }, [availability, filterCourtType]);

  const handleSelectCourtType = (nextType: 'ALL' | 'INDOOR' | 'OUTDOOR') => {
    setFilterCourtType(nextType);
    if (selectedCourtId && nextType !== 'ALL') {
      const current = availability?.courts.find((c) => c.court.id === selectedCourtId);
      if (current && current.court.court_type !== nextType) {
        setSelectedCourtId(null);
        setSelectedHours([]);
      }
    }
  };

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

  const totalAvailableSlots = displayedCourts.reduce(
    (sum, item) => sum + item.slots.filter((s) => s.status === 'AVAILABLE').length,
    0
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-5 pb-24 lg:pb-10">
      {/* Editorial Reservation Header (non-generic, high-clarity) */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#DCDCD2] pb-5">
        <div className="space-y-1.5">
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-terracotta">
            Đặt sân trực tuyến • Giữ chỗ 15 phút
          </div>
          <h1 className="font-display text-2xl sm:text-4xl font-extrabold text-charcoal tracking-tight">
            Lịch sân &amp; Khung giờ trống
          </h1>
          <p className="text-sm text-court-muted max-w-2xl">
            Chọn từ 1 đến 6 khung giờ liên tiếp trên cùng một sân. Giá hiển thị theo bảng giá giờ thường, cao điểm hoặc cuối tuần.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          {!loading && availability && (
            <div className="bg-white border border-[#DCDCD2] rounded-xl px-3.5 py-2 text-xs font-semibold text-charcoal tabular-nums">
              <span className="text-court font-bold">{displayedCourts.length}</span> sân •{' '}
              <span className="text-court font-bold">{totalAvailableSlots}</span> khung giờ trống
            </div>
          )}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => loadAvailability(playDate, filterBranchId, filterLocationId)}
          >
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Làm mới</span>
          </Button>
        </div>
      </section>

      {/* 7-Day Date Strip + Native Date Picker */}
      <section
        aria-label="Chọn ngày chơi"
        className="bg-white rounded-2xl border border-[#CFCFC4] p-4 space-y-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CalendarDays className="w-4 h-4 text-court" aria-hidden="true" />
            <span className="text-xs font-bold uppercase tracking-wider text-charcoal">
              Ngày chơi: <span className="font-mono text-court">{formatDateVN(playDate)}</span>
            </span>
            {availability?.is_weekend && (
              <span className="text-[11px] font-semibold text-[#8F4324] bg-[#FDF1EB] px-2.5 py-0.5 rounded-md border border-[#E8C1B0]">
                Bảng giá cuối tuần
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={stripStart <= minDate}
              onClick={() => {
                const prev = addLocalDays(stripStart, -7);
                setStripStart(prev < minDate ? minDate : prev);
              }}
              className="p-1.5 rounded-lg border border-[#D4D6CD] text-charcoal hover:bg-warm-white disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="7 ngày trước"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setStripStart(addLocalDays(stripStart, 7))}
              className="p-1.5 rounded-lg border border-[#D4D6CD] text-charcoal hover:bg-warm-white"
              aria-label="7 ngày tiếp theo"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <label htmlFor="booking-play-date" className="sr-only">
              Chọn ngày từ lịch
            </label>
            <input
              id="booking-play-date"
              type="date"
              min={minDate}
              value={playDate}
              onChange={(e) => {
                const val = e.target.value;
                if (val) {
                  setPlayDate(val);
                  setStripStart(val < minDate ? minDate : val);
                }
              }}
              className="rounded-lg border border-[#D4D6CD] bg-warm-white px-2.5 py-1.5 text-xs font-mono font-semibold text-charcoal focus:ring-2 focus:ring-court focus:outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-7 gap-1.5 sm:gap-2">
          {dateStrip.map((d) => {
            const active = d.iso === playDate;
            return (
              <button
                key={d.iso}
                type="button"
                onClick={() => setPlayDate(d.iso)}
                aria-pressed={active}
                className={`rounded-xl py-2 px-1 text-center border transition-colors ${
                  active
                    ? 'bg-court border-court text-white shadow-sm'
                    : 'bg-warm-white border-[#E5E5DC] text-charcoal hover:border-court/50'
                }`}
              >
                <div
                  className={`text-[10px] font-bold uppercase ${
                    active ? 'text-ball-lime' : 'text-court-muted'
                  }`}
                >
                  {d.isToday ? 'Hôm nay' : d.weekday}
                </div>
                <div className="font-mono text-xs sm:text-sm font-bold mt-0.5 tabular-nums">
                  {d.dayLabel}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Venue & Court-Type Selection Bar */}
      <section
        aria-label="Bộ lọc chi nhánh và loại sân"
        className="bg-white px-4 py-3.5 rounded-2xl border border-[#CFCFC4] flex flex-col lg:flex-row lg:items-center justify-between gap-3"
      >
        <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2 text-xs font-semibold text-charcoal min-w-0">
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
              className="w-full sm:w-auto max-w-full rounded-lg border border-[#D4D6CD] px-3 py-2 sm:py-1.5 text-xs font-medium bg-warm-white text-charcoal focus:outline-none focus:ring-2 focus:ring-court"
            >
              <option value="">Tất cả chi nhánh</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.display_name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2 text-xs font-semibold text-charcoal min-w-0">
            <div className="flex items-center gap-1.5 shrink-0">
              <MapPin className="w-4 h-4 text-court" aria-hidden="true" />
              <label htmlFor="filter-location">Địa điểm:</label>
            </div>
            <select
              id="filter-location"
              value={filterLocationId}
              onChange={(e) => setFilterLocationId(e.target.value)}
              className="w-full sm:w-auto max-w-full rounded-lg border border-[#D4D6CD] px-3 py-2 sm:py-1.5 text-xs font-medium bg-warm-white text-charcoal focus:outline-none focus:ring-2 focus:ring-court"
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
        </div>

        <div className="flex items-center gap-1.5" role="group" aria-label="Lọc loại sân">
          {(['ALL', 'INDOOR', 'OUTDOOR'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => handleSelectCourtType(t)}
              aria-pressed={filterCourtType === t}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                filterCourtType === t
                  ? 'bg-court text-white border-court'
                  : 'bg-warm-white text-charcoal border-[#D4D6CD] hover:border-court/50'
              }`}
            >
              {t === 'ALL' ? 'Tất cả sân' : t === 'INDOOR' ? 'Trong nhà' : 'Ngoài trời'}
            </button>
          ))}
        </div>
      </section>

      {/* Slot Legend */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-court-muted bg-white px-4 py-2.5 rounded-xl border border-[#DCDCD2]">
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-white border border-court/50 inline-block" />
          <span>Trống (Giờ thường)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-[#FDF1EB] border border-terracotta inline-block" />
          <span className="inline-flex items-center gap-1">
            Cao điểm 16h–22h <Flame className="w-3.5 h-3.5 text-terracotta" aria-hidden="true" />
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-court inline-block" />
          <span className="font-semibold text-charcoal">Đang chọn</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-amber-100 border border-amber-400 inline-block" />
          <span>Giữ chỗ 15p</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-[#E7E6DC] inline-block" />
          <span>Đã đặt / Quá giờ / Bảo trì</span>
        </div>
      </div>

      {error && (
        <AlertBanner
          tone="error"
          onRetry={() => loadAvailability(playDate, filterBranchId, filterLocationId)}
        >
          {error}
        </AlertBanner>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Court Cards & Time Slot Grids */}
        <div className="lg:col-span-2 space-y-5">
          {loading ? (
            <LoadingSkeleton rows={3} />
          ) : displayedCourts.length === 0 ? (
            <EmptyState
              title="Không có sân nào phù hợp bộ lọc"
              description="Thử chọn chi nhánh, địa điểm hoặc loại sân khác để xem lịch trống."
            />
          ) : (
            displayedCourts.map((item) => {
              const { court, slots } = item;
              const isMaintenance = court.status === 'MAINTENANCE';
              const availablePrices = slots
                .filter((s) => s.status === 'AVAILABLE')
                .map((s) => s.price);
              const minPrice =
                availablePrices.length > 0 ? Math.min(...availablePrices) : null;
              const thumb =
                court.court_type === 'INDOOR' ? courtIndoorImg : courtOutdoorImg;

              return (
                <article
                  key={court.id}
                  className={`bg-white rounded-2xl border overflow-hidden transition-colors ${
                    selectedCourtId === court.id
                      ? 'border-court ring-1 ring-court'
                      : 'border-[#CFCFC4]'
                  }`}
                >
                  {/* Court Header with compact photography */}
                  <div className="p-4 sm:p-5 border-b border-[#ECEBE2] flex flex-col sm:flex-row gap-4">
                    <div className="relative w-full sm:w-36 h-28 sm:h-24 rounded-xl overflow-hidden shrink-0 bg-court-deep">
                      <img
                        src={thumb}
                        alt={`Ảnh minh họa ${court.name}`}
                        width={960}
                        height={717}
                        loading="lazy"
                        className="w-full h-full object-cover block"
                      />
                      <span className="absolute bottom-1 right-1 bg-black/65 text-white text-[9px] px-1.5 py-0.5 rounded">
                        Minh họa
                      </span>
                    </div>

                    <div className="flex-1 min-w-0 flex flex-col justify-between gap-2">
                      <div>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <h2 className="font-display text-lg font-extrabold text-charcoal">
                              {court.name}
                            </h2>
                            <StatusBadge status={court.court_type} />
                            {isMaintenance && <StatusBadge status="MAINTENANCE" />}
                          </div>
                          {minPrice !== null && (
                            <span className="font-mono text-xs font-bold text-court bg-[#E9EFEA] px-2.5 py-1 rounded-md tabular-nums">
                              Từ {formatVND(minPrice)}/giờ
                            </span>
                          )}
                        </div>

                        {(court.branch_name || court.location_name) && (
                          <p className="text-xs text-court font-medium mt-1.5 flex items-start gap-1">
                            <MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5 text-terracotta" aria-hidden="true" />
                            <span>
                              {court.branch_name} • {court.location_name}
                              {court.location_address ? ` (${court.location_address})` : ''}
                            </span>
                          </p>
                        )}
                      </div>

                      <p className="text-xs text-court-muted">
                        {court.surface}
                        {court.description ? ` • ${court.description}` : ''}
                      </p>
                    </div>
                  </div>

                  {/* Time Slots Grid */}
                  <div className="p-4 sm:p-5 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                    {slots.map((slot) => {
                      const isSelected =
                        selectedCourtId === court.id && selectedHours.includes(slot.start_hour);
                      const isAvailable = slot.status === 'AVAILABLE';

                      let btnStyle =
                        'bg-[#ECEBE2] border-[#D4D6CD] text-[#6E746F] cursor-not-allowed';
                      if (isSelected) {
                        btnStyle =
                          'bg-court border-court text-white ring-2 ring-ball-lime font-bold shadow-sm';
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
                          className={`rounded-xl border px-2 py-2.5 text-center transition-all min-h-[60px] flex flex-col justify-center ${btnStyle}`}
                        >
                          <div className="font-mono text-xs font-bold tabular-nums">
                            {slot.label}
                          </div>
                          <div className="text-[11px] mt-0.5 tabular-nums flex items-center justify-center gap-0.5">
                            {isAvailable ? (
                              <>
                                {slot.is_peak_hour && !isSelected && (
                                  <Flame className="w-3 h-3 text-terracotta" aria-hidden="true" />
                                )}
                                <span>{Math.round(slot.price / 1000)}k</span>
                              </>
                            ) : slot.status === 'LOCKED' ? (
                              'Giữ 15p'
                            ) : slot.status === 'BOOKED' ? (
                              'Đã đặt'
                            ) : slot.status === 'PAST' ? (
                              'Quá giờ'
                            ) : (
                              'Bảo trì'
                            )}
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

        {/* Transaction-style Sticky Summary & Customer Form */}
        <aside
          id="booking-summary-panel"
          className="bg-white rounded-2xl border border-[#CFCFC4] p-5 lg:sticky lg:top-20 shadow-sm"
        >
          <div className="flex items-center justify-between pb-3.5 border-b border-[#ECEBE2] mb-4">
            <h2 className="font-display text-lg font-extrabold text-charcoal flex items-center gap-2">
              <Clock className="w-4 h-4 text-court" aria-hidden="true" />
              <span>Chi tiết đặt sân</span>
            </h2>
            {selectedHours.length > 0 && (
              <span className="text-xs font-bold bg-court text-ball-lime px-2.5 py-0.5 rounded-md tabular-nums">
                {selectedHours.length} giờ
              </span>
            )}
          </div>

          {selectedCourt && selectedHours.length > 0 ? (
            <div className="bg-warm-white border border-[#D4D6CD] rounded-xl p-4 mb-4 text-sm space-y-2">
              {selectedCourt.court.branch_name && (
                <div className="flex justify-between gap-2">
                  <span className="text-court-muted">Chi nhánh</span>
                  <span className="font-semibold text-right text-court">
                    {selectedCourt.court.branch_name}
                  </span>
                </div>
              )}
              {selectedCourt.court.location_name && (
                <div className="flex justify-between gap-2">
                  <span className="text-court-muted">Địa điểm</span>
                  <span className="font-semibold text-right">
                    {selectedCourt.court.location_name}
                  </span>
                </div>
              )}
              <div className="flex justify-between gap-2">
                <span className="text-court-muted">Sân</span>
                <span className="font-bold text-charcoal text-right">
                  {selectedCourt.court.name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-court-muted">Ngày chơi</span>
                <span className="font-mono font-semibold tabular-nums">
                  {formatDateVN(playDate)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-court-muted">Khung giờ</span>
                <span className="font-mono font-semibold tabular-nums">
                  {formatHourRange(selectedHours[0], selectedHours[selectedHours.length - 1] + 1)}
                </span>
              </div>
              <div className="flex justify-between pt-2.5 border-t border-[#D4D6CD] text-base items-baseline">
                <span className="font-bold text-charcoal">Tổng tạm tính</span>
                <span className="font-mono font-extrabold text-lg text-court tabular-nums">
                  {formatVND(totalAmount)}
                </span>
              </div>
            </div>
          ) : (
            <div className="bg-warm-white border border-dashed border-[#C9CBC1] rounded-xl p-4 mb-4 text-xs text-court-muted flex items-start gap-2 leading-relaxed">
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
                className="w-full rounded-xl border border-[#D4D6CD] px-3.5 py-2.5 text-sm bg-white focus:ring-2 focus:ring-court focus:outline-none"
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
                className="w-full rounded-xl border border-[#D4D6CD] px-3.5 py-2.5 text-sm bg-white focus:ring-2 focus:ring-court focus:outline-none"
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
                className="w-full rounded-xl border border-[#D4D6CD] px-3.5 py-2.5 text-sm bg-white focus:ring-2 focus:ring-court focus:outline-none"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={submitting}
              disabled={!selectedCourtId || selectedHours.length === 0}
              className="w-full py-3.5"
            >
              {submitting ? 'Đang giữ chỗ...' : 'Giữ chỗ 15 phút & Thanh toán'}
            </Button>
          </form>
        </aside>
      </div>

      {/* Mobile Sticky Action Bar when slots are selected */}
      {selectedCourt && selectedHours.length > 0 && (
        <div className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-court text-white border-t border-[#2A5448] px-4 py-3 flex items-center justify-between gap-3 shadow-lg">
          <div className="min-w-0">
            <div className="text-[11px] text-[#B7C9BE] truncate">
              {selectedCourt.court.name} •{' '}
              {formatHourRange(selectedHours[0], selectedHours[selectedHours.length - 1] + 1)}
            </div>
            <div className="font-mono font-bold text-sm text-ball-lime tabular-nums">
              {formatVND(totalAmount)}
            </div>
          </div>
          <a
            href="#booking-summary-panel"
            className="bg-ball-lime text-court font-bold px-4 py-2 rounded-lg text-xs shrink-0"
          >
            Nhập thông tin →
          </a>
        </div>
      )}
    </div>
  );
};
