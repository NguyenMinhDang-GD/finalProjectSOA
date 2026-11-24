import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import { Camera, CameraOff, CheckCircle2, QrCode, RefreshCw, ShieldAlert } from 'lucide-react';
import { apiRequest } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { CheckinTicket, ScanQRResponse } from '../types';

export const StaffScannerPage: React.FC = () => {
  const { user } = useAuth();
  const [manualInput, setManualInput] = useState('');
  const [bypassTimeCheck, setBypassTimeCheck] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [scanResult, setScanResult] = useState<{ ok: boolean; message: string; ticket?: CheckinTicket | null } | null>(
    null
  );
  const [logs, setLogs] = useState<CheckinTicket[]>([]);
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const busyRef = useRef(false);

  const loadLogs = useCallback(async () => {
    try {
      const data = await apiRequest<CheckinTicket[]>('/api/checkin/logs');
      setLogs(data);
    } catch {
      // ignore
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
      setTimeout(() => {
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
    } catch (err) {
      setScanResult({
        ok: false,
        message:
          'Không mở được Camera (trên điện thoại bắt buộc truy cập qua HTTPS ngrok hoặc localhost). Bạn vẫn có thể dán mã QR / mã đơn ở ô bên cạnh.',
      });
    }
  };

  if (!user || (user.role !== 'STAFF' && user.role !== 'ADMIN')) {
    return (
      <div className="max-w-xl mx-auto mt-10 bg-white p-6 rounded-2xl border border-red-200 text-center text-red-700 font-medium">
        Chỉ tài khoản Nhân viên (STAFF) hoặc Admin mới được truy cập cổng quét QR Check-in.
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <QrCode className="w-6 h-6 text-emerald-700" />
            <span>Cổng Quét Mã QR Check-in Tại Sân</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Xác thực chữ ký HMAC-SHA256 • Kiểm tra khung giờ (sớm 30p) • Chống quét lại 2 lần
          </p>
        </div>

        <label className="flex items-center gap-2 text-xs font-semibold bg-amber-50 text-amber-900 px-3 py-2 rounded-xl border border-amber-200 cursor-pointer">
          <input
            type="checkbox"
            checked={bypassTimeCheck}
            onChange={(e) => setBypassTimeCheck(e.target.checked)}
            className="rounded text-emerald-700"
          />
          <span>Chế độ Demo: Bỏ qua kiểm tra khung giờ</span>
        </label>
      </div>

      {scanResult && (
        <div
          className={`rounded-2xl p-5 border-2 shadow-sm flex items-start gap-3 ${
            scanResult.ok
              ? 'bg-emerald-50 border-emerald-500 text-emerald-950'
              : 'bg-red-50 border-red-500 text-red-950'
          }`}
        >
          {scanResult.ok ? (
            <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
          ) : (
            <ShieldAlert className="w-8 h-8 text-red-600 shrink-0" />
          )}
          <div>
            <div className="font-bold text-lg">
              {scanResult.ok ? 'HỢP LỆ — MỜI KHÁCH VÀO SÂN' : 'TỪ CHỐI CHECK-IN'}
            </div>
            <p className="text-sm mt-0.5">{scanResult.message}</p>
            {scanResult.ticket && (
              <div className="mt-2 text-xs font-medium bg-white/70 inline-block px-3 py-1.5 rounded-lg border border-emerald-200">
                Khách: {scanResult.ticket.customer_name} • {scanResult.ticket.court_name} • Mã:{' '}
                {scanResult.ticket.booking_code}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-slate-900">1. Quét bằng Camera</h2>
            <button
              type="button"
              onClick={toggleCamera}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition ${
                cameraActive
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-emerald-700 hover:bg-emerald-800 text-white'
              }`}
            >
              {cameraActive ? <CameraOff className="w-4 h-4" /> : <Camera className="w-4 h-4" />}
              <span>{cameraActive ? 'Tắt Camera' : 'Mở Camera quét QR'}</span>
            </button>
          </div>
          <div
            id="qr-reader-region"
            className="w-full min-h-[260px] bg-slate-900 rounded-xl overflow-hidden flex items-center justify-center text-slate-400 text-xs"
          >
            {!cameraActive && 'Bấm "Mở Camera quét QR" để bắt đầu quét vé từ điện thoại khách'}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between">
          <div>
            <h2 className="font-bold text-slate-900 mb-2">2. Nhập / Dán chuỗi QR hoặc Mã đơn</h2>
            <p className="text-xs text-slate-500 mb-3">
              Hỗ trợ chuỗi QR ký số (<code>PKB1.&lt;id&gt;.&lt;code&gt;.&lt;hmac&gt;</code>) hoặc nhập mã đơn{' '}
              <code>PKB-...</code>.
            </p>
            <textarea
              rows={4}
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="Dán chuỗi QR hoặc nhập PKB-20261124-XXXX..."
              className="w-full rounded-xl border border-slate-300 p-3 text-sm font-mono focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={() => submitScan(manualInput)}
            className="mt-4 w-full bg-emerald-700 hover:bg-emerald-800 text-white font-semibold py-3 rounded-xl text-sm transition"
          >
            Xác thực & Check-in Ngay
          </button>
        </div>
      </div>

      {/* Recent Check-in Tickets */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-slate-900">Danh sách vé gần đây</h2>
          <button
            onClick={loadLogs}
            className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:underline"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Làm mới
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2.5">Mã đơn</th>
                <th className="px-3 py-2.5">Khách hàng</th>
                <th className="px-3 py-2.5">Sân & Giờ</th>
                <th className="px-3 py-2.5">Trạng thái</th>
                <th className="px-3 py-2.5">Thao tác nhanh</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map((t) => (
                <tr key={t.id}>
                  <td className="px-3 py-2.5 font-mono font-semibold">{t.booking_code}</td>
                  <td className="px-3 py-2.5">{t.customer_name}</td>
                  <td className="px-3 py-2.5">
                    {t.court_name} ({t.play_date} {String(t.start_hour).padStart(2, '0')}h–{String(t.end_hour).padStart(2, '0')}h)
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                        t.status === 'CHECKED_IN'
                          ? 'bg-blue-100 text-blue-800'
                          : t.status === 'REVOKED'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <button
                      type="button"
                      onClick={() => setManualInput(t.qr_payload)}
                      className="text-xs text-emerald-700 font-semibold hover:underline"
                    >
                      Nạp QR test
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
