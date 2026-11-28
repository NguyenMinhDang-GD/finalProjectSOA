import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import {
  Camera,
  CameraOff,
  CheckCircle2,
  ClipboardCheck,
  Coins,
  PlusCircle,
  QrCode,
  RefreshCw,
  ShieldAlert,
  UserCheck,
  UserX,
  Wrench,
} from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND } from '../api/client';
import { BrandMark } from '../components/brand/BrandLogo';
import { Button } from '../components/ui/Button';
import { AlertBanner, EmptyState } from '../components/ui/FeedbackStates';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import {
  AvailabilityResponse,
  BookingOrder,
  CheckinTicket,
  CourtAvailability,
  MaintenanceBlock,
  ScanQRResponse,
} from '../types';

type StaffTab = 'scanner' | 'operations' | 'walkin' | 'maintenance';

function todayVN(): string {
  return new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);
}

export const StaffScannerPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<StaffTab>('scanner');
  const [manualInput, setManualInput] = useState('');
  const [bypassTimeCheck, setBypassTimeCheck] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [logsError, setLogsError] = useState('');
  const [scanResult, setScanResult] = useState<{
    ok: boolean;
    message: string;
    ticket?: CheckinTicket | null;
  } | null>(null);
  const [logs, setLogs] = useState<CheckinTicket[]>([]);
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const busyRef = useRef(false);

  const [bookings, setBookings] = useState<BookingOrder[]>([]);
  const [opFeedback, setOpFeedback] = useState<{ ok: boolean; message: string } | null>(null);
  const [opFilter, setOpFilter] = useState('');
  const [opReason, setOpReason] = useState('Thao tác vận hành tại quầy');
  const [earlyCompletion, setEarlyCompletion] = useState(false);
  const [opBusyCode, setOpBusyCode] = useState<string | null>(null);

  const [walkInDate, setWalkInDate] = useState(todayVN());
  const [availability, setAvailability] = useState<CourtAvailability[]>([]);
  const [walkInCourtId, setWalkInCourtId] = useState('');
  const [walkInHours, setWalkInHours] = useState<number[]>([]);
  const [walkInName, setWalkInName] = useState('');
  const [walkInPhone, setWalkInPhone] = useState('');
  const [walkInEmail, setWalkInEmail] = useState('');
  const [collectCashNow, setCollectCashNow] = useState(true);
  const [walkInBusy, setWalkInBusy] = useState(false);

  const [maintenanceList, setMaintenanceList] = useState<MaintenanceBlock[]>([]);
  const [maintenanceDate, setMaintenanceDate] = useState(todayVN());

  const loadLogs = useCallback(async () => {
    setLogsError('');
    try {
      const data = await apiRequest<CheckinTicket[]>('/api/checkin/logs');
      setLogs(data);
    } catch (err) {
      setLogsError(err instanceof Error ? err.message : 'Không tải được danh sách vé check-in');
    }
  }, []);

  const loadOperations = useCallback(async () => {
    try {
      const data = await apiRequest<BookingOrder[]>('/api/bookings/admin/list');
      setBookings(data);
    } catch (err) {
      setOpFeedback({
        ok: false,
        message: err instanceof Error ? err.message : 'Không tải được danh sách đơn đặt sân',
      });
    }
  }, []);

  const loadAvailability = useCallback(async (date: string) => {
    try {
      const data = await apiRequest<AvailabilityResponse>(`/api/courts/availability?date=${date}`);
      setAvailability(data.courts);
      if (data.courts.length > 0 && !data.courts.some((c) => c.court.id === walkInCourtId)) {
        setWalkInCourtId(data.courts[0].court.id);
      }
    } catch (err) {
      setOpFeedback({
        ok: false,
        message: err instanceof Error ? err.message : 'Không tải được lịch trống sân',
      });
    }
  }, [walkInCourtId]);

  const loadMaintenance = useCallback(async (date: string) => {
    try {
      const query = date ? `?play_date=${date}` : '';
      const data = await apiRequest<MaintenanceBlock[]>(`/api/bookings/maintenance${query}`);
      setMaintenanceList(data);
    } catch (err) {
      setOpFeedback({
        ok: false,
        message: err instanceof Error ? err.message : 'Không tải được lịch bảo trì',
      });
    }
  }, []);

  useEffect(() => {
    loadLogs();
    loadOperations();
    loadAvailability(walkInDate);
    loadMaintenance(maintenanceDate);
    return () => {
      if (scannerRef.current && scannerRef.current.isScanning) {
        scannerRef.current.stop().catch(() => undefined);
      }
    };
  }, [loadLogs, loadOperations, loadAvailability, loadMaintenance, walkInDate, maintenanceDate]);

  const submitScan = async (qrData: string) => {
    if (!qrData.trim() || busyRef.current) return;
    busyRef.current = true;
    setSubmitting(true);
    try {
      const res = await apiRequest<ScanQRResponse>('/api/checkin/scan', {
        method: 'POST',
        body: JSON.stringify({ qr_data: qrData.trim(), bypass_time_check: bypassTimeCheck }),
      });
      setScanResult({ ok: true, message: res.message, ticket: res.ticket });
      loadLogs();
    } catch (err) {
      setScanResult({
        ok: false,
        message: err instanceof Error ? err.message : 'Check-in thất bại',
        ticket: null,
      });
    } finally {
      setSubmitting(false);
      window.setTimeout(() => {
        busyRef.current = false;
      }, 1500);
    }
  };

  const toggleCamera = async () => {
    if (cameraActive) {
      if (scannerRef.current) {
        await scannerRef.current.stop().catch(() => undefined);
        scannerRef.current.clear();
      }
      setCameraActive(false);
      return;
    }

    try {
      const qrScanner = new Html5Qrcode('qr-reader-region');
      scannerRef.current = qrScanner;
      await qrScanner.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (decodedText) => {
          setManualInput(decodedText);
          submitScan(decodedText);
        },
        () => undefined
      );
      setCameraActive(true);
    } catch {
      setScanResult({
        ok: false,
        message:
          'Không mở được Camera (trên thiết bị di động cần cấp quyền Camera và truy cập qua HTTPS hoặc localhost). Bạn có thể dán chuỗi QR hoặc mã đơn ở ô bên cạnh.',
      });
    }
  };

  if (!user || (user.role !== 'STAFF' && user.role !== 'ADMIN')) {
    return (
      <div className="max-w-xl mx-auto px-4 py-12">
        <AlertBanner tone="error" title="Không có quyền truy cập">
          Chỉ tài khoản Nhân viên (STAFF) hoặc Admin mới được sử dụng cổng quét QR Check-in.
        </AlertBanner>
      </div>
    );
  }

  const validCount = logs.filter((t) => t.status === 'VALID').length;
  const checkedInCount = logs.filter((t) => t.status === 'CHECKED_IN').length;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
      {/* Staff Operational Header */}
      <header className="bg-court text-white rounded-2xl p-5 sm:p-6 border border-[#23483D] flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <BrandMark variant="lime" className="w-10 h-10 shrink-0 mt-0.5" />
          <div>
            <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-ball-lime">
              Vận hành tại quầy • Staff Check-in Desk
            </div>
            <h1 className="font-display text-xl sm:text-2xl font-extrabold flex items-center gap-2 mt-0.5">
              <span>Cổng Quét Mã QR Check-in</span>
            </h1>
            <p className="text-xs text-[#C7D6CD] mt-1">
              Xác thực chữ ký số HMAC-SHA256 • Kiểm tra khung giờ (sớm tối đa 30p) • Chống quét trùng
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-3 bg-court-deep/80 px-3.5 py-2 rounded-xl border border-[#2D584B] text-xs tabular-nums">
            <span>
              Chờ check-in: <strong className="text-ball-lime">{validCount}</strong>
            </span>
            <span className="text-[#3C6D5E]">|</span>
            <span>
              Đã vào sân: <strong className="text-white">{checkedInCount}</strong>
            </span>
          </div>

          {import.meta.env.VITE_ENABLE_DEMO_CONTROLS !== 'false' && (
          <label className="inline-flex items-center gap-2 text-xs font-semibold bg-court-deep text-white px-3.5 py-2.5 rounded-xl border border-[#2D584B] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={bypassTimeCheck}
              onChange={(e) => setBypassTimeCheck(e.target.checked)}
              className="w-4 h-4 rounded accent-ball-lime"
            />
            <span>Chế độ Demo: Bỏ qua khung giờ</span>
          </label>
          )}
        </div>
      </header>

      {/* Staff Workspace Tabs */}
      <nav aria-label="Phân hệ vận hành nhân viên" className="flex flex-wrap gap-2">
        {[
          { key: 'scanner' as StaffTab, label: 'Quét QR Check-in', icon: QrCode },
          { key: 'operations' as StaffTab, label: `Vận hành đơn & Tiền mặt (${bookings.length})`, icon: Coins },
          { key: 'walkin' as StaffTab, label: 'Đặt sân Walk-in', icon: PlusCircle },
          { key: 'maintenance' as StaffTab, label: `Lịch bảo trì (${maintenanceList.length})`, icon: Wrench },
        ].map((item) => {
          const Icon = item.icon;
          const active = activeTab === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setActiveTab(item.key)}
              className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold border transition cursor-pointer ${
                active
                  ? 'bg-court text-white border-court shadow-sm'
                  : 'bg-white text-charcoal border-[#D4D6CD] hover:border-court'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {opFeedback && (
        <AlertBanner
          tone={opFeedback.ok ? 'success' : 'error'}
          title={opFeedback.ok ? 'Thao tác thành công' : 'Có lỗi xảy ra'}
        >
          {opFeedback.message}
        </AlertBanner>
      )}

      {activeTab === 'scanner' && (
        <>
      {/* Immediate Result Feedback Banner */}
      {scanResult && (
        <div
          role="status"
          aria-live="polite"
          className={`rounded-2xl p-5 border-2 flex items-start gap-3.5 shadow-sm ${
            scanResult.ok
              ? 'bg-[#E6F4EC] border-[#1E6F43] text-[#14532D]'
              : 'bg-red-50 border-[#B93829] text-red-950'
          }`}
        >
          {scanResult.ok ? (
            <CheckCircle2 className="w-8 h-8 text-[#1E6F43] shrink-0 mt-0.5" aria-hidden="true" />
          ) : (
            <ShieldAlert className="w-8 h-8 text-[#B93829] shrink-0 mt-0.5" aria-hidden="true" />
          )}
          <div className="min-w-0">
            <div className="font-display font-extrabold text-lg">
              {scanResult.ok ? 'HỢP LỆ — MỜI KHÁCH VÀO SÂN' : 'TỪ CHỐI CHECK-IN'}
            </div>
            <p className="text-sm mt-0.5">{scanResult.message}</p>
            {scanResult.ticket && (
              <div className="mt-2.5 text-xs font-medium bg-white/90 inline-block px-3 py-2 rounded-lg border border-[#A7D7BA]">
                <strong>{scanResult.ticket.customer_name}</strong> •{' '}
                {scanResult.ticket.branch_name
                  ? `${scanResult.ticket.branch_name} (${scanResult.ticket.location_name}) • `
                  : ''}
                {scanResult.ticket.court_name} • Mã:{' '}
                <span className="font-mono font-bold">{scanResult.ticket.booking_code}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Touch-friendly Scanner + Manual Fallback */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-white rounded-2xl border border-[#CFCFC4] p-5 shadow-sm flex flex-col justify-between gap-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <QrCode className="w-4 h-4 text-court" aria-hidden="true" />
              <h2 className="font-display font-bold text-charcoal">1. Quét bằng Camera</h2>
            </div>
            <Button
              type="button"
              variant={cameraActive ? 'danger' : 'primary'}
              size="md"
              onClick={toggleCamera}
              className="min-h-[44px]"
            >
              {cameraActive ? (
                <>
                  <CameraOff className="w-4 h-4" aria-hidden="true" />
                  <span>Tắt Camera</span>
                </>
              ) : (
                <>
                  <Camera className="w-4 h-4" aria-hidden="true" />
                  <span>Mở Camera quét QR</span>
                </>
              )}
            </Button>
          </div>
          <div
            id="qr-reader-region"
            className="w-full min-h-[260px] bg-court-deep rounded-xl overflow-hidden flex items-center justify-center text-[#B7C9BE] text-xs px-4 text-center border border-[#23483D]"
          >
            {!cameraActive &&
              'Bấm "Mở Camera quét QR" để bắt đầu quét vé từ điện thoại khách hàng'}
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-[#CFCFC4] p-5 shadow-sm flex flex-col justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <ClipboardCheck className="w-4 h-4 text-court" aria-hidden="true" />
              <h2 className="font-display font-bold text-charcoal">
                2. Nhập / Dán chuỗi QR hoặc Mã đơn
              </h2>
            </div>
            <p className="text-xs text-court-muted mb-3">
              Hỗ trợ chuỗi QR ký số (
              <code className="font-mono">PKB1.&lt;id&gt;.&lt;code&gt;.&lt;hmac&gt;</code>) hoặc
              mã đơn <code className="font-mono">PKB-...</code>.
            </p>
            <label htmlFor="manual-qr-input" className="sr-only">
              Chuỗi QR hoặc mã đặt sân
            </label>
            <textarea
              id="manual-qr-input"
              rows={5}
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="Dán chuỗi QR hoặc nhập PKB-20261124-XXXX..."
              className="w-full rounded-xl border border-[#CFCFC4] p-3.5 text-sm font-mono focus:ring-2 focus:ring-court focus:outline-none"
            />
          </div>
          <Button
            type="button"
            variant="primary"
            size="lg"
            loading={submitting}
            disabled={!manualInput.trim()}
            onClick={() => submitScan(manualInput)}
            className="w-full min-h-[48px]"
          >
            {submitting ? 'Đang xác thực...' : 'Xác thực & Check-in Ngay'}
          </Button>
        </section>
      </div>

      {/* Recent Check-in Logs */}
      <section className="bg-white rounded-2xl border border-[#CFCFC4] p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-bold text-charcoal">Danh sách vé gần đây</h2>
          <Button type="button" variant="ghost" size="sm" onClick={loadLogs}>
            <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
            Làm mới
          </Button>
        </div>

        {logsError && (
          <AlertBanner tone="error" onRetry={loadLogs}>
            {logsError}
          </AlertBanner>
        )}

        {logs.length === 0 ? (
          <EmptyState title="Chưa có vé check-in nào" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-warm-white border-b border-[#DCDCD2] text-[11px] uppercase tracking-wider text-court-muted">
                <tr>
                  <th className="px-3 py-3">Mã đơn</th>
                  <th className="px-3 py-3">Khách hàng</th>
                  <th className="px-3 py-3">Sân &amp; Giờ</th>
                  <th className="px-3 py-3">Trạng thái</th>
                  <th className="px-3 py-3 text-right">Thao tác nhanh</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ECEBE2]">
                {logs.map((t) => (
                  <tr key={t.id} className="hover:bg-warm-white/60">
                    <td className="px-3 py-3 font-mono font-bold text-charcoal whitespace-nowrap">
                      {t.booking_code}
                    </td>
                    <td className="px-3 py-3">{t.customer_name}</td>
                    <td className="px-3 py-3">
                      <div className="font-semibold text-charcoal">
                        {t.court_name} ({formatDateVN(t.play_date)}{' '}
                        {formatHourRange(t.start_hour, t.end_hour)})
                      </div>
                      {t.branch_name && (
                        <div className="text-xs text-court-muted">
                          {t.branch_name} • {t.location_name}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setManualInput(t.qr_payload)}
                      >
                        Nạp QR test
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
        </>
      )}

      {activeTab === 'operations' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <h2 className="font-display text-lg font-bold text-charcoal">Vận hành đơn, Thu tiền mặt (Demo) & Trạng thái</h2>
              <p className="text-xs text-court-muted">Thu tiền mặt tại quầy, đánh dấu No-Show (sau grace 30p), hoặc Hoàn tất lượt chơi.</p>
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <input
                type="text"
                value={opFilter}
                onChange={(e) => setOpFilter(e.target.value)}
                placeholder="Lọc mã đơn / tên / SĐT..."
                className="rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm"
              />
              <Button variant="secondary" size="sm" onClick={loadOperations}>
                <RefreshCw className="w-4 h-4" />
                <span>Làm mới</span>
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-warm-white p-3.5 rounded-xl border border-[#ECEBE2]">
            <div>
              <label className="block text-xs font-semibold text-court-muted mb-1">Lý do thao tác (No-Show / Hoàn tất / Tiền mặt)</label>
              <input
                type="text"
                value={opReason}
                onChange={(e) => setOpReason(e.target.value)}
                className="w-full rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm bg-white"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal self-end pb-2 cursor-pointer">
              <input
                type="checkbox"
                checked={earlyCompletion}
                onChange={(e) => setEarlyCompletion(e.target.checked)}
                className="w-4 h-4 rounded accent-court"
              />
              <span>Cho phép hoàn tất sớm (early_completion)</span>
            </label>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
                <tr>
                  <th className="px-4 py-3">Mã đơn</th>
                  <th className="px-4 py-3">Nguồn</th>
                  <th className="px-4 py-3">Khách</th>
                  <th className="px-4 py-3">Ngày & Giờ</th>
                  <th className="px-4 py-3">Tổng tiền</th>
                  <th className="px-4 py-3">Trạng thái</th>
                  <th className="px-4 py-3">Thao tác quầy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ECEBE2]">
                {bookings
                  .filter((b) => {
                    if (!opFilter.trim()) return true;
                    const q = opFilter.trim().toLowerCase();
                    return (
                      b.booking_code.toLowerCase().includes(q) ||
                      b.customer_name.toLowerCase().includes(q) ||
                      b.customer_phone.toLowerCase().includes(q)
                    );
                  })
                  .slice(0, 40)
                  .map((b) => (
                    <tr key={b.id}>
                      <td className="px-4 py-3 font-mono font-bold text-charcoal">
                        {b.booking_code}{' '}
                        <span className="text-[11px] font-normal text-court-muted">v{b.booking_revision || 1}</span>
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold">
                        <span className="px-2 py-0.5 rounded bg-[#F1F2EC] text-charcoal">{b.booking_source || 'ONLINE'}</span>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div className="font-semibold text-charcoal">{b.customer_name}</div>
                        <div className="text-court-muted">{b.customer_phone}</div>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div>{formatDateVN(b.play_date)}</div>
                        <div className="text-court-muted">{formatHourRange(b.start_hour, b.end_hour)}</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{formatVND(b.total_amount)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          <StatusBadge status={b.status} />
                          {b.admission_status && (
                            <span className="text-[10px] font-mono text-court-muted">{b.admission_status}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {b.status === 'PENDING_PAYMENT' && (
                            <Button
                              variant="primary"
                              size="sm"
                              disabled={opBusyCode === b.booking_code}
                              onClick={async () => {
                                setOpBusyCode(b.booking_code);
                                try {
                                  await apiRequest('/api/payments/staff/cash-collect', {
                                    method: 'POST',
                                    body: JSON.stringify({
                                      booking_code: b.booking_code,
                                      amount: b.total_amount,
                                      idempotency_key: `CASH-${b.booking_code}-${Date.now()}`,
                                      note: opReason || 'Thu tiền mặt tại quầy',
                                    }),
                                  });
                                  setOpFeedback({
                                    ok: true,
                                    message: `Đã thu tiền mặt (Demo) cho đơn ${b.booking_code}. Hệ thống đang xác nhận vé.`,
                                  });
                                  await Promise.all([loadOperations(), loadLogs()]);
                                } catch (err) {
                                  setOpFeedback({
                                    ok: false,
                                    message: err instanceof Error ? err.message : 'Thu tiền mặt thất bại',
                                  });
                                } finally {
                                  setOpBusyCode(null);
                                }
                              }}
                            >
                              <Coins className="w-3.5 h-3.5" />
                              <span>Thu tiền mặt</span>
                            </Button>
                          )}
                          {b.status === 'PAID' && b.admission_status !== 'ADMITTED' && (
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={opBusyCode === b.booking_code}
                              onClick={async () => {
                                setOpBusyCode(b.booking_code);
                                try {
                                  await apiRequest(`/api/bookings/staff/${b.booking_code}/no-show`, {
                                    method: 'POST',
                                    body: JSON.stringify({
                                      reason: opReason || 'Khách không đến sau giờ quy định',
                                    }),
                                  });
                                  setOpFeedback({
                                    ok: true,
                                    message: `Đã đánh dấu NO_SHOW cho đơn ${b.booking_code}.`,
                                  });
                                  await Promise.all([loadOperations(), loadLogs()]);
                                } catch (err) {
                                  setOpFeedback({
                                    ok: false,
                                    message: err instanceof Error ? err.message : 'Không thể đánh dấu No-Show',
                                  });
                                } finally {
                                  setOpBusyCode(null);
                                }
                              }}
                            >
                              <UserX className="w-3.5 h-3.5" />
                              <span>No-Show</span>
                            </Button>
                          )}
                          {b.status === 'PAID' && b.admission_status === 'ADMITTED' && (
                            <Button
                              variant="primary"
                              size="sm"
                              disabled={opBusyCode === b.booking_code}
                              onClick={async () => {
                                setOpBusyCode(b.booking_code);
                                try {
                                  await apiRequest(`/api/bookings/staff/${b.booking_code}/complete`, {
                                    method: 'POST',
                                    body: JSON.stringify({
                                      reason: opReason || 'Khách đã hoàn tất lượt chơi',
                                      early_completion: earlyCompletion,
                                    }),
                                  });
                                  setOpFeedback({
                                    ok: true,
                                    message: `Đã hoàn tất lượt chơi cho đơn ${b.booking_code}.`,
                                  });
                                  await Promise.all([loadOperations(), loadLogs()]);
                                } catch (err) {
                                  setOpFeedback({
                                    ok: false,
                                    message: err instanceof Error ? err.message : 'Không thể hoàn tất đơn',
                                  });
                                } finally {
                                  setOpBusyCode(null);
                                }
                              }}
                            >
                              <UserCheck className="w-3.5 h-3.5" />
                              <span>Hoàn tất</span>
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activeTab === 'walkin' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 space-y-5">
          <div>
            <h2 className="font-display text-lg font-bold text-charcoal">Tạo đơn Walk-in tại quầy</h2>
            <p className="text-xs text-court-muted">Cho phép đặt sân trong khung giờ hiện tại nếu giờ kết thúc chưa qua.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-court-muted mb-1">Ngày chơi</label>
              <input
                type="date"
                value={walkInDate}
                onChange={(e) => {
                  setWalkInDate(e.target.value);
                  setWalkInHours([]);
                  loadAvailability(e.target.value);
                }}
                className="w-full rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-court-muted mb-1">Chọn sân</label>
              <select
                value={walkInCourtId}
                onChange={(e) => {
                  setWalkInCourtId(e.target.value);
                  setWalkInHours([]);
                }}
                className="w-full rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm bg-white"
              >
                {availability.map((c) => (
                  <option key={c.court.id} value={c.court.id}>
                    {c.court.name} ({c.court.court_type})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <Button variant="secondary" size="sm" onClick={() => loadAvailability(walkInDate)}>
                <RefreshCw className="w-4 h-4" />
                <span>Tải lại lịch sân</span>
              </Button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-court-muted mb-2">Chọn khung giờ trống</label>
            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
              {(availability.find((c) => c.court.id === walkInCourtId)?.slots || []).map((slot) => {
                const selected = walkInHours.includes(slot.start_hour);
                const disabled = slot.status !== 'AVAILABLE';
                return (
                  <button
                    key={slot.start_hour}
                    type="button"
                    disabled={disabled}
                    onClick={() =>
                      setWalkInHours((prev) =>
                        prev.includes(slot.start_hour)
                          ? prev.filter((h) => h !== slot.start_hour)
                          : [...prev, slot.start_hour].sort((a, b) => a - b)
                      )
                    }
                    className={`px-2 py-2 rounded-xl text-xs font-semibold border transition ${
                      disabled
                        ? 'bg-[#ECEBE2] text-court-muted border-[#D4D6CD] cursor-not-allowed line-through'
                        : selected
                        ? 'bg-court text-white border-court'
                        : 'bg-white text-charcoal border-[#D4D6CD] hover:border-court cursor-pointer'
                    }`}
                  >
                    {String(slot.start_hour).padStart(2, '0')}:00
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-court-muted mb-1">Tên khách hàng</label>
              <input
                type="text"
                value={walkInName}
                onChange={(e) => setWalkInName(e.target.value)}
                placeholder="Nguyễn Văn Walk-in"
                className="w-full rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-court-muted mb-1">Số điện thoại</label>
              <input
                type="text"
                value={walkInPhone}
                onChange={(e) => setWalkInPhone(e.target.value)}
                placeholder="0901234567"
                className="w-full rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-court-muted mb-1">Email (tùy chọn)</label>
              <input
                type="email"
                value={walkInEmail}
                onChange={(e) => setWalkInEmail(e.target.value)}
                placeholder="khach@example.com"
                className="w-full rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
            <label className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal cursor-pointer">
              <input
                type="checkbox"
                checked={collectCashNow}
                onChange={(e) => setCollectCashNow(e.target.checked)}
                className="w-4 h-4 rounded accent-court"
              />
              <span>Thu tiền mặt (Demo) ngay sau khi tạo đơn Walk-in</span>
            </label>
            <Button
              variant="primary"
              disabled={walkInBusy || !walkInCourtId || walkInHours.length === 0 || !walkInName.trim() || !walkInPhone.trim()}
              onClick={async () => {
                setWalkInBusy(true);
                try {
                  const created = await apiRequest<BookingOrder>('/api/bookings/staff/walk-in', {
                    method: 'POST',
                    body: JSON.stringify({
                      court_id: walkInCourtId,
                      play_date: walkInDate,
                      hours: walkInHours,
                      customer_name: walkInName.trim(),
                      customer_phone: walkInPhone.trim(),
                      customer_email: walkInEmail.trim() || undefined,
                    }),
                  });
                  if (collectCashNow) {
                    await apiRequest('/api/payments/staff/cash-collect', {
                      method: 'POST',
                      body: JSON.stringify({
                        booking_code: created.booking_code,
                        amount: created.total_amount,
                        idempotency_key: `WALKIN-CASH-${created.booking_code}`,
                        note: 'Thu tiền mặt ngay khi tạo đơn Walk-in',
                      }),
                    });
                  }
                  setOpFeedback({
                    ok: true,
                    message: collectCashNow
                      ? `Đã tạo đơn Walk-in ${created.booking_code} và thu tiền mặt (Demo) ${formatVND(created.total_amount)}.`
                      : `Đã tạo đơn Walk-in ${created.booking_code} (${formatVND(created.total_amount)}).`,
                  });
                  setWalkInHours([]);
                  await Promise.all([loadOperations(), loadAvailability(walkInDate), loadLogs()]);
                  setActiveTab('operations');
                } catch (err) {
                  setOpFeedback({
                    ok: false,
                    message: err instanceof Error ? err.message : 'Tạo đơn Walk-in thất bại',
                  });
                } finally {
                  setWalkInBusy(false);
                }
              }}
            >
              {walkInBusy ? 'Đang tạo đơn...' : 'Tạo đơn Walk-in'}
            </Button>
          </div>
        </section>
      )}

      {activeTab === 'maintenance' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="font-display text-lg font-bold text-charcoal">Lịch bảo trì sân</h2>
              <p className="text-xs text-court-muted">Các khung giờ bảo trì sẽ tự động khóa khỏi lịch đặt sân.</p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={maintenanceDate}
                onChange={(e) => {
                  setMaintenanceDate(e.target.value);
                  loadMaintenance(e.target.value);
                }}
                className="rounded-xl border border-[#D4D6CD] px-3 py-2 text-sm"
              />
              <Button variant="secondary" size="sm" onClick={() => loadMaintenance(maintenanceDate)}>
                <RefreshCw className="w-4 h-4" />
                <span>Làm mới</span>
              </Button>
            </div>
          </div>

          {maintenanceList.length === 0 ? (
            <EmptyState title="Không có lịch bảo trì" description="Ngày đã chọn hiện chưa có khung giờ bảo trì nào." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
                  <tr>
                    <th className="px-4 py-3">Sân</th>
                    <th className="px-4 py-3">Ngày</th>
                    <th className="px-4 py-3">Khung giờ</th>
                    <th className="px-4 py-3">Lý do</th>
                    <th className="px-4 py-3">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ECEBE2]">
                  {maintenanceList.map((m) => (
                    <tr key={m.id}>
                      <td className="px-4 py-3 font-medium text-charcoal">{availability.find((c) => c.court.id === m.court_id)?.court.name || m.court_id}</td>
                      <td className="px-4 py-3 font-mono text-xs">{formatDateVN(m.play_date)}</td>
                      <td className="px-4 py-3 font-mono text-xs">{String(m.start_hour).padStart(2, '0')}:00 - {String(m.end_hour).padStart(2, '0')}:00</td>
                      <td className="px-4 py-3 text-xs">{m.reason}</td>
                      <td className="px-4 py-3"><StatusBadge status={m.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
};
