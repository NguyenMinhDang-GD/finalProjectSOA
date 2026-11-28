import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowUpRight,
  CalendarDays,
  History,
  LogIn,
  LogOut,
  Menu,
  QrCode,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { BrandLockup } from './brand/BrandLogo';

const ROLE_LABELS: Record<string, string> = {
  CUSTOMER: 'Thành viên',
  STAFF: 'Nhân viên sân',
  ADMIN: 'Quản trị viên',
};

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/'
      : location.pathname === path || location.pathname.startsWith(`${path}/`);

  const linkClass = (path: string) =>
    `inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
      isActive(path)
        ? 'bg-court-soft text-ball-lime font-semibold'
        : 'text-[#D6E1DA] hover:text-white hover:bg-court-soft/60'
    }`;

  const closeMobile = () => setMobileOpen(false);
  const isOperationalRole = user?.role === 'STAFF' || user?.role === 'ADMIN';

  return (
    <header className="bg-court text-white border-b border-[#23483D] sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <Link
          to="/"
          onClick={closeMobile}
          className="shrink-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ball-lime"
          aria-label="Pickleball SOA Arena — Trang chủ"
        >
          <BrandLockup theme="dark" />
        </Link>

        <nav className="hidden lg:flex items-center gap-1" aria-label="Điều hướng chính">
          <Link to="/" className={linkClass('/')}>
            <span>Trang chủ</span>
          </Link>
          <Link to="/book" className={linkClass('/book')}>
            <CalendarDays className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>Đặt sân</span>
          </Link>
          <Link to="/lookup" className={linkClass('/lookup')}>
            <Search className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>Tra cứu vé</span>
          </Link>
          {user && (
            <Link to="/my-bookings" className={linkClass('/my-bookings')}>
              <History className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Lịch sử</span>
            </Link>
          )}
          {(user?.role === 'STAFF' || user?.role === 'ADMIN') && (
            <Link to="/staff/scanner" className={linkClass('/staff/scanner')}>
              <QrCode className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Quét QR</span>
            </Link>
          )}
          {user?.role === 'ADMIN' && (
            <Link to="/admin" className={linkClass('/admin')}>
              <ShieldCheck className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Quản trị</span>
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-2.5 shrink-0">
          <div className="hidden sm:flex items-center gap-2.5">
            {!isActive('/book') && !isOperationalRole && (
              <Link
                to="/book"
                className="inline-flex items-center gap-1.5 bg-ball-lime hover:bg-[#cde94b] text-court font-bold px-3.5 py-2 rounded-lg text-sm whitespace-nowrap transition-colors"
              >
                <span>Đặt sân ngay</span>
                <ArrowUpRight className="w-4 h-4 shrink-0" aria-hidden="true" />
              </Link>
            )}

            {user ? (
              <div className="flex items-center gap-2.5 bg-court-deep/80 pl-3 pr-2 py-1.5 rounded-lg border border-[#285044]">
                <div className="text-right">
                  <div className="text-xs font-semibold leading-tight text-white max-w-[140px] truncate">
                    {user.full_name}
                  </div>
                  <div className="text-[10px] text-ball-lime font-semibold tracking-wide">
                    {ROLE_LABELS[user.role] || user.role}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    navigate('/');
                  }}
                  className="p-1.5 text-[#C7D6CD] hover:text-white hover:bg-court-soft rounded-md transition-colors"
                  title="Đăng xuất"
                  aria-label="Đăng xuất"
                >
                  <LogOut className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 border border-[#356355] hover:border-ball-lime text-white hover:text-ball-lime font-semibold px-3.5 py-2 rounded-lg text-sm transition-colors"
              >
                <LogIn className="w-4 h-4" aria-hidden="true" />
                <span>Đăng nhập</span>
              </Link>
            )}
          </div>

          <button
            type="button"
            onClick={() => setMobileOpen((prev) => !prev)}
            className="lg:hidden p-2 rounded-lg text-[#E3EAE5] hover:bg-court-soft hover:text-white"
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav-menu"
            aria-label={mobileOpen ? 'Đóng menu' : 'Mở menu'}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div
          id="mobile-nav-menu"
          className="lg:hidden border-t border-[#23483D] bg-court-deep px-4 py-3.5 space-y-1.5"
        >
          <Link to="/" onClick={closeMobile} className={`w-full ${linkClass('/')}`}>
            <span>Trang chủ</span>
          </Link>
          <Link to="/book" onClick={closeMobile} className={`w-full ${linkClass('/book')}`}>
            <CalendarDays className="w-4 h-4" aria-hidden="true" />
            <span>Đặt sân trực tuyến</span>
          </Link>
          <Link to="/lookup" onClick={closeMobile} className={`w-full ${linkClass('/lookup')}`}>
            <Search className="w-4 h-4" aria-hidden="true" />
            <span>Tra cứu vé QR</span>
          </Link>
          {user && (
            <Link
              to="/my-bookings"
              onClick={closeMobile}
              className={`w-full ${linkClass('/my-bookings')}`}
            >
              <History className="w-4 h-4" aria-hidden="true" />
              <span>Lịch sử đặt sân</span>
            </Link>
          )}
          {(user?.role === 'STAFF' || user?.role === 'ADMIN') && (
            <Link
              to="/staff/scanner"
              onClick={closeMobile}
              className={`w-full ${linkClass('/staff/scanner')}`}
            >
              <QrCode className="w-4 h-4" aria-hidden="true" />
              <span>Quét QR Check-in</span>
            </Link>
          )}
          {user?.role === 'ADMIN' && (
            <Link to="/admin" onClick={closeMobile} className={`w-full ${linkClass('/admin')}`}>
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              <span>Quản trị hệ thống</span>
            </Link>
          )}
          <div className="pt-2.5 mt-2 border-t border-[#23483D]">
            {user ? (
              <div className="flex items-center justify-between px-2 py-1.5">
                <div>
                  <div className="text-xs font-semibold text-white">{user.full_name}</div>
                  <div className="text-[11px] text-ball-lime font-semibold">
                    {ROLE_LABELS[user.role] || user.role}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    logout();
                    closeMobile();
                    navigate('/');
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-court-soft text-white text-xs font-semibold"
                >
                  <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
                  Đăng xuất
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <Link
                  to="/book"
                  onClick={closeMobile}
                  className="flex items-center justify-center gap-1.5 bg-ball-lime text-court font-bold px-3 py-2.5 rounded-lg text-sm"
                >
                  <span>Đặt sân</span>
                </Link>
                <Link
                  to="/login"
                  onClick={closeMobile}
                  className="flex items-center justify-center gap-1.5 border border-[#356355] text-white font-semibold px-3 py-2.5 rounded-lg text-sm"
                >
                  <LogIn className="w-4 h-4" aria-hidden="true" />
                  <span>Đăng nhập</span>
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
