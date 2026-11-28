import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Calendar, LogIn, LogOut, Menu, QrCode, Search, ShieldCheck, UserCheck, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { CourtEmblem } from './ui/CourtHeroGraphic';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (path: string) => location.pathname === path;

  const linkClass = (path: string) =>
    `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      isActive(path)
        ? 'bg-ball-lime text-court font-bold'
        : 'text-[#E3EAE5] hover:bg-court-soft hover:text-white'
    }`;

  const closeMobile = () => setMobileOpen(false);

  return (
    <header className="bg-court text-white border-b border-court-soft sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        <Link to="/" onClick={closeMobile} className="flex items-center gap-2.5 shrink-0">
          <div className="bg-ball-lime text-court p-1.5 rounded-lg">
            <CourtEmblem className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-sm sm:text-base tracking-tight leading-tight">
              Pickleball SOA Arena
            </div>
            <div className="text-[11px] text-[#B7C9BE] hidden sm:block">
              Athletic Club &amp; Court Booking
            </div>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-1" aria-label="Điều hướng chính">
          <Link to="/" className={linkClass('/')}>
            <Calendar className="w-4 h-4" aria-hidden="true" />
            <span>Đặt sân</span>
          </Link>
          <Link to="/lookup" className={linkClass('/lookup')}>
            <Search className="w-4 h-4" aria-hidden="true" />
            <span>Tra cứu vé</span>
          </Link>
          {user && (
            <Link to="/my-bookings" className={linkClass('/my-bookings')}>
              <UserCheck className="w-4 h-4" aria-hidden="true" />
              <span>Lịch sử</span>
            </Link>
          )}
          {(user?.role === 'STAFF' || user?.role === 'ADMIN') && (
            <Link to="/staff/scanner" className={linkClass('/staff/scanner')}>
              <QrCode className="w-4 h-4" aria-hidden="true" />
              <span>Quét QR</span>
            </Link>
          )}
          {user?.role === 'ADMIN' && (
            <Link to="/admin" className={linkClass('/admin')}>
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              <span>Quản trị</span>
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center">
            {user ? (
              <div className="flex items-center gap-2.5 bg-court-deep/70 px-3 py-1.5 rounded-lg border border-court-soft">
                <div className="text-right">
                  <div className="text-xs font-semibold leading-tight text-white">{user.full_name}</div>
                  <div className="text-[10px] text-ball-lime font-semibold tracking-wide">{user.role}</div>
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
                className="inline-flex items-center gap-1.5 bg-ball-lime hover:bg-[#cbe844] text-court font-bold px-3.5 py-2 rounded-lg text-sm transition-colors"
              >
                <LogIn className="w-4 h-4" aria-hidden="true" />
                <span>Đăng nhập</span>
              </Link>
            )}
          </div>

          <button
            type="button"
            onClick={() => setMobileOpen((prev) => !prev)}
            className="md:hidden p-2 rounded-lg text-[#E3EAE5] hover:bg-court-soft hover:text-white"
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
          className="md:hidden border-t border-court-soft bg-court-deep px-4 py-3 space-y-1.5"
        >
          <Link to="/" onClick={closeMobile} className={linkClass('/')}>
            <Calendar className="w-4 h-4" aria-hidden="true" />
            <span>Đặt sân</span>
          </Link>
          <Link to="/lookup" onClick={closeMobile} className={linkClass('/lookup')}>
            <Search className="w-4 h-4" aria-hidden="true" />
            <span>Tra cứu vé</span>
          </Link>
          {user && (
            <Link to="/my-bookings" onClick={closeMobile} className={linkClass('/my-bookings')}>
              <UserCheck className="w-4 h-4" aria-hidden="true" />
              <span>Lịch sử đặt sân</span>
            </Link>
          )}
          {(user?.role === 'STAFF' || user?.role === 'ADMIN') && (
            <Link to="/staff/scanner" onClick={closeMobile} className={linkClass('/staff/scanner')}>
              <QrCode className="w-4 h-4" aria-hidden="true" />
              <span>Quét QR Check-in</span>
            </Link>
          )}
          {user?.role === 'ADMIN' && (
            <Link to="/admin" onClick={closeMobile} className={linkClass('/admin')}>
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              <span>Quản trị hệ thống</span>
            </Link>
          )}
          <div className="pt-2 mt-2 border-t border-court-soft">
            {user ? (
              <div className="flex items-center justify-between px-2 py-1.5">
                <div>
                  <div className="text-xs font-semibold text-white">{user.full_name}</div>
                  <div className="text-[11px] text-ball-lime font-semibold">{user.role}</div>
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
              <Link
                to="/login"
                onClick={closeMobile}
                className="flex items-center justify-center gap-2 w-full bg-ball-lime text-court font-bold px-4 py-2.5 rounded-lg text-sm"
              >
                <LogIn className="w-4 h-4" aria-hidden="true" />
                <span>Đăng nhập</span>
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
