import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import { Camera, CameraOff, CheckCircle2, QrCode, RefreshCw, ShieldAlert } from 'lucide-react';
import { formatDateVN, formatHourRange, apiRequest } from '../api/client';
import { Button } from '../components/ui/Button';
import { AlertBanner, EmptyState } from '../components/ui/FeedbackStates';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { CheckinTicket, ScanQRResponse } from '../types';

export const StaffScannerPage: React.FC = () => {
  const { user } = useAuth();
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

  const loadLogs = useCallback(async () => {
    setLogsError('');
    try {
      const data = await apiRequest<CheckinTicket[]>('/api/checkin/logs');
      setLogs(data);
    } catch (err) {
      setLogsError(err instanceof Error ? err.message : 'Không tải được danh sách vé check-in');
    }
  }, []);

  useEffect(() => {
    loadLogs();
    return () => {
      if (scannerRef.current && scannerRef.current.isScanning) {
        scannerRef.current.stop().catch(() => undefined);
      }
    };
  }, [loadLogs]);

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

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
      {/* Operational Header */}
      <div className="bg-court text-white rounded-2xl p-5 sm:p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-ball-lime">
            Vận hành tại sân • Staff Operations
          </div>
          <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2 mt-1">
            <QrCode className="w-6 h-6 text-ball-lime" aria-hidden="true" />
            <span>Cổng Quét Mã QR Check-in</span>
          </h1>
          <p className="text-xs text-[#C7D6CD] mt-1">
            Xác thực chữ ký số HMAC-SHA256 • Kiểm tra khung giờ (cho phép sớm 30p) • Chống quét trùng
          </p>
        </div>

        <label className="inline-flex items-center gap-2.5 text-xs font-semibold bg-court-deep text-white px-4 py-2.5 rounded-xl border border-court-soft cursor-pointer select-none">
          <input
            type="checkbox"
            checked={bypassTimeCheck}
            onChange={(e) => setBypassTimeCheck(e.target.checked)}
            className="w-4 h-4 rounded accent-ball-lime"
          />
          <span>Chế độ Demo: Bỏ qua kiểm tra khung giờ</span>
        </label>
      </div>

      {/* Scan Outcome Banner */}
      {scanResult && (
        <div
          role="status"
          aria-live="polite"
          className={`rounded-2xl p-5 border-2 flex items-start gap-3.5 ${
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
            <div className="font-bold text-lg">
              {scanResult.ok ? 'HỢP LỆ — MỜI KHÁCH VÀO SÂN' : 'TỪ CHỐI CHECK-IN'}
            </div>
            <p className="text-sm mt-0.5">{scanResult.message}</p>
            {scanResult.ticket && (
              <div className="mt-2.5 text-xs font-medium bg-white/85 inline-block px-3 py-2 rounded-lg border border-[#A7D7BA]">
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

      {/* Scanner + Manual Entry */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="font-bold text-charcoal">1. Quét bằng Camera</h2>
            <Button
              type="button"
              variant={cameraActive ? 'danger' : 'primary'}
              size="md"
              onClick={toggleCamera}
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
            className="w-full min-h-[260px] bg-court-deep rounded-xl overflow-hidden flex items-center justify-center text-[#B7C9BE] text-xs px-4 text-center"
          >
            {!cameraActive && 'Bấm "Mở Camera quét QR" để bắt đầu quét vé từ điện thoại khách'}
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 shadow-sm flex flex-col justify-between">
          <div>
            <h2 className="font-bold text-charcoal mb-1.5">2. Nhập / Dán chuỗi QR hoặc Mã đơn</h2>
            <p className="text-xs text-court-muted mb-3">
              Hỗ trợ chuỗi QR ký số (<code className="font-mono">PKB1.&lt;id&gt;.&lt;code&gt;.&lt;hmac&gt;</code>) hoặc mã đơn{' '}
              <code className="font-mono">PKB-...</code>.
            </p>
            <label htmlFor="manual-qr-input" className="sr-only">
              Chuỗi QR hoặc mã đặt sân
            </label>
            <textarea
              id="manual-qr-input"
              rows={4}
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="Dán chuỗi QR hoặc nhập PKB-20261124-XXXX..."
              className="w-full rounded-xl border border-[#D4D6CD] p-3 text-sm font-mono focus:ring-2 focus:ring-court focus:outline-none"
            />
          </div>
          <Button
            type="button"
            variant="primary"
            size="lg"
            loading={submitting}
            disabled={!manualInput.trim()}
            onClick={() => submitScan(manualInput)}
            className="mt-4 w-full"
          >
            {submitting ? 'Đang xác thực...' : 'Xác thực & Check-in Ngay'}
          </Button>
        </section>
      </div>

      {/* Recent Check-in Tickets */}
      <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-charcoal">Danh sách vé gần đây</h2>
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
              <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
                <tr>
                  <th className="px-3 py-2.5">Mã đơn</th>
                  <th className="px-3 py-2.5">Khách hàng</th>
                  <th className="px-3 py-2.5">Sân &amp; Giờ</th>
                  <th className="px-3 py-2.5">Trạng thái</th>
                  <th className="px-3 py-2.5">Thao tác nhanh</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ECEBE2]">
                {logs.map((t) => (
                  <tr key={t.id} className="hover:bg-warm-white/60">
                    <td className="px-3 py-2.5 font-mono font-bold text-charcoal whitespace-nowrap">
                      {t.booking_code}
                    </td>
                    <td className="px-3 py-2.5">{t.customer_name}</td>
                    <td className="px-3 py-2.5">
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
                    <td className="px-3 py-2.5">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
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
    </div>
  );
};
