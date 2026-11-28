import React from 'react';
import { Calendar, Clock, Download, MapPin, Printer } from 'lucide-react';
import { formatDateVN, formatHourRange, formatVND } from '../../api/client';
import { CheckinTicket } from '../../types';
import { BrandMark } from '../brand/BrandLogo';
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
    <article className="bg-white rounded-2xl border border-[#CFCFC4] overflow-hidden shadow-sm">
      {/* Venue Pass Header */}
      <div className="bg-court text-white px-6 py-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#254B40]">
        <div className="flex items-center gap-3">
          <BrandMark variant="lime" className="w-9 h-9 shrink-0" />
          <div>
            <div className="text-[11px] uppercase tracking-[0.16em] text-ball-lime font-bold">
              Pickleball SOA Arena • Digital Venue Pass
            </div>
            <div className="font-mono font-bold text-base sm:text-lg tracking-tight">
              {bookingCode}
            </div>
          </div>
        </div>
        {ticket && <StatusBadge status={ticket.status} />}
      </div>

      {/* Pass Body */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
        <div className="md:col-span-7 space-y-4 text-sm">
          <div className="pb-3.5 border-b border-[#ECEBE2]">
            <div className="text-[11px] text-court-muted uppercase tracking-wider font-bold">
              Sân thi đấu
            </div>
            <div className="font-display text-xl font-extrabold text-charcoal mt-0.5">
              {courtName}
            </div>
            {(branchName || locationName) && (
              <div className="text-xs text-court mt-1.5 flex items-start gap-1.5">
                <MapPin className="w-3.5 h-3.5 shrink-0 mt-0.5 text-terracotta" aria-hidden="true" />
                <span>
                  <strong>{branchName}</strong>
                  {locationName ? ` • ${locationName}` : ''}
                  {locationAddress ? ` — ${locationAddress}` : ''}
                </span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-warm-white rounded-xl p-3.5 border border-[#E5E5DC]">
              <div className="text-[11px] text-court-muted uppercase font-bold flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-court" aria-hidden="true" /> Ngày chơi
              </div>
              <div className="font-mono font-bold text-base text-charcoal mt-1 tabular-nums">
                {formatDateVN(playDate)}
              </div>
            </div>
            <div className="bg-warm-white rounded-xl p-3.5 border border-[#E5E5DC]">
              <div className="text-[11px] text-court-muted uppercase font-bold flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-court" aria-hidden="true" /> Khung giờ
              </div>
              <div className="font-mono font-bold text-base text-charcoal mt-1 tabular-nums">
                {formatHourRange(startHour, endHour)}
              </div>
            </div>
          </div>

          <div className="space-y-1.5 pt-1">
            <div className="flex justify-between">
              <span className="text-court-muted">Người đặt sân:</span>
              <span className="font-semibold text-charcoal">{customerName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-court-muted">Tổng thanh toán:</span>
              <span className="font-mono font-bold text-court tabular-nums">
                {formatVND(totalAmount)}
              </span>
            </div>
          </div>

          <div className="rounded-xl bg-[#E9EFEA] border border-[#C3D1C7] px-3.5 py-2.5 text-xs text-court leading-relaxed">
            Xuất trình mã QR tại quầy lễ tân trước giờ chơi tối đa 30 phút để nhân viên quét check-in.
          </div>
        </div>

        {/* High-Contrast QR Area with Quiet Zone */}
        <div className="md:col-span-5 flex flex-col items-center justify-center bg-warm-white border border-dashed border-court/35 rounded-2xl p-5 text-center">
          {ticket?.qr_image_base64 ? (
            <>
              <div className="bg-white p-4 rounded-xl border border-[#D4D6CD] shadow-sm">
                <img
                  src={ticket.qr_image_base64}
                  alt={`Mã QR Check-in cho đơn ${bookingCode}`}
                  className="w-48 h-48 block"
                />
              </div>
              <div className="mt-3 w-full text-[11px] text-court-muted break-all font-mono bg-white px-2.5 py-1.5 rounded-lg border border-[#E5E5DC]">
                {ticket.qr_payload}
              </div>
              <div className="mt-3.5 flex flex-wrap justify-center gap-2 no-print">
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
    </article>
  );
};
