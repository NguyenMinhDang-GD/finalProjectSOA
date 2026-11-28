import React from 'react';
import { Link } from 'react-router-dom';
import { BrandLockup } from './brand/BrandLogo';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-court-deep text-[#C7D6CD] border-t border-[#23483D] no-print">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        <div className="md:col-span-5 space-y-3">
          <BrandLockup theme="dark" />
          <p className="text-xs leading-relaxed text-[#9DB3A6] max-w-sm">
            Hệ thống đặt sân Pickleball theo khung giờ thực tế, giữ chỗ 15 phút, thanh toán VietQR và phát hành vé điện tử QR Check-in tại sân.
          </p>
        </div>

        <div className="md:col-span-4 space-y-2">
          <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-ball-lime">
            Điều hướng khách hàng
          </div>
          <ul className="space-y-1.5 text-sm">
            <li>
              <Link to="/" className="hover:text-white transition-colors">
                Trang chủ câu lạc bộ
              </Link>
            </li>
            <li>
              <Link to="/book" className="hover:text-white transition-colors">
                Đặt sân theo chi nhánh &amp; giờ
              </Link>
            </li>
            <li>
              <Link to="/lookup" className="hover:text-white transition-colors">
                Tra cứu đơn đặt sân &amp; Vé QR
              </Link>
            </li>
            <li>
              <Link to="/my-bookings" className="hover:text-white transition-colors">
                Lịch sử đặt sân thành viên
              </Link>
            </li>
          </ul>
        </div>

        <div className="md:col-span-3 space-y-2">
          <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-ball-lime">
            Tài khoản
          </div>
          <ul className="space-y-1.5 text-sm">
            <li>
              <Link to="/login" className="hover:text-white transition-colors">
                Đăng nhập thành viên
              </Link>
            </li>
            <li>
              <Link to="/register" className="hover:text-white transition-colors">
                Đăng ký tài khoản mới
              </Link>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-[#1D3B32] px-4 sm:px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-[#8CA396]">
          <span>Pickleball SOA Arena • Câu lạc bộ Pickleball &amp; Đặt sân trực tuyến</span>
          <span>Đồ án Kiến trúc Hướng Dịch vụ (SOA)</span>
        </div>
      </div>
    </footer>
  );
};
