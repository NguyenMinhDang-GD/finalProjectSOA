import React from 'react';
import { Calendar, Clock, Download, MapPin, Printer, QrCode } from 'lucide-react';
import { formatDateVN, formatHourRange, formatVND } from '../../api/client';
import { CheckinTicket } from '../../types';
import { Button } from './Button';
import { StatusBadge } from './StatusBadge';

interface QrTicketCardProps {
  ticket: CheckinTicket | null;
  bookingCode: string;
  branchName?: string;
  locationName?: string;
  locationAddress?: string;
  courtName: string;
  playDate: string;
  startHour: number;
  endHour: number;
  customerName: string;
  totalAmount: number;
}

export const QrTicketCard: React.FC<QrTicketCardProps> = ({
  ticket,
  bookingCode,
  branchName,
  locationName,
  locationAddress,
  courtName,
  playDate,
  startHour,
  endHour,
  customerName,
  totalAmount,
}) => {
  const handleDownloadQR = () => {
    if (!ticket?.qr_image_base64) return;
    const link = document.createElement('a');
    link.href = ticket.qr_image_base64;
    link.download = `ve-qr-${bookingCode}.png`;
    link.click();
  };

  return (
    <div className="bg-white rounded-2xl border border-[#D4D6CD] overflow-hidden shadow-sm">
      <div className="bg-court text-white px-6 py-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="bg-ball-lime text-court p-1.5 rounded-lg">
            <QrCode className="w-4 h-4" aria-hidden="true" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-ball-lime font-semibold">
              Thẻ vào sân điện tử
            </div>
            <div className="font-mono font-bold text-base">{bookingCode}</div>
          </div>
        </div>
        {ticket && <StatusBadge status={ticket.status} />}
      </div>

      <div className="p-6 grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
        <div className="md:col-span-7 space-y-3 text-sm">
          <div className="pb-3 border-b border-[#ECEBE2]">
            <div className="text-xs text-court-muted uppercase font-semibold">Sân thi đấu</div>
            <div className="text-lg font-bold text-charcoal mt-0.5">{courtName}</div>
            {(branchName || locationName) && (
              <div className="text-xs text-court mt-1 flex items-start gap-1.5">
                <MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
                <span>
                  <strong>{branchName}</strong>
                  {locationName ? ` • ${locationName}` : ''}
                  {locationAddress ? ` — ${locationAddress}` : ''}
                </span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-warm-white rounded-xl p-3 border border-[#E6E5DC]">
              <div className="text-[11px] text-court-muted uppercase font-semibold flex items-center gap-1">
                <Calendar className="w-3 h-3" aria-hidden="true" /> Ngày chơi
              </div>
              <div className="font-bold text-charcoal mt-0.5 tabular-nums">
                {formatDateVN(playDate)}
              </div>
            </div>
            <div className="bg-warm-white rounded-xl p-3 border border-[#E6E5DC]">
              <div className="text-[11px] text-court-muted uppercase font-semibold flex items-center gap-1">
                <Clock className="w-3 h-3" aria-hidden="true" /> Khung giờ
              </div>
              <div className="font-bold text-charcoal mt-0.5 tabular-nums">
                {formatHourRange(startHour, endHour)}
              </div>
            </div>
          </div>

          <div className="flex justify-between pt-1">
            <span className="text-court-muted">Người đặt:</span>
            <span className="font-semibold text-charcoal">{customerName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-court-muted">Tổng thanh toán:</span>
            <span className="font-bold text-court tabular-nums">{formatVND(totalAmount)}</span>
          </div>

          <div className="rounded-xl bg-[#E9EFEA] border border-[#C3D1C7] px-3.5 py-2.5 text-xs text-court">
            Vui lòng xuất trình mã QR tại quầy lễ tân trước giờ chơi tối đa 30 phút để nhân viên quét check-in.
          </div>
        </div>

        <div className="md:col-span-5 flex flex-col items-center justify-center bg-warm-white border border-dashed border-court/40 rounded-2xl p-5 text-center">
          {ticket?.qr_image_base64 ? (
            <>
              <div className="bg-white p-3 rounded-xl border border-[#D4D6CD] shadow-sm">
                <img
                  src={ticket.qr_image_base64}
                  alt={`Mã QR Check-in cho đơn ${bookingCode}`}
                  className="w-48 h-48 block"
                />
              </div>
              <div className="mt-3 w-full text-[11px] text-court-muted break-all font-mono bg-white px-2.5 py-1.5 rounded-lg border border-[#E6E5DC]">
                {ticket.qr_payload}
              </div>
              <div className="mt-3 flex flex-wrap justify-center gap-2 no-print">
                <Button type="button" variant="secondary" size="sm" onClick={handleDownloadQR}>
                  <Download className="w-3.5 h-3.5" aria-hidden="true" />
                  Tải ảnh QR
                </Button>
                <Button type="button" variant="secondary" size="sm" onClick={() => window.print()}>
                  <Printer className="w-3.5 h-3.5" aria-hidden="true" />
                  In vé
                </Button>
              </div>
            </>
          ) : (
            <div className="py-10 text-sm text-court-muted">
              Đang đồng bộ vé QR từ hệ thống...
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
