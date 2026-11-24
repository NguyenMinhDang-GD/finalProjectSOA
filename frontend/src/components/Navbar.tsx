import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Calendar, LogIn, LogOut, QrCode, Search, ShieldCheck, Trophy, UserCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const linkClass = (path: string) =>
    `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
      location.pathname === path
        ? 'bg-emerald-700 text-white shadow-sm'
        : 'text-emerald-100 hover:bg-emerald-800/70 hover:text-white'
    }`;

  return (
    <header className="bg-emerald-900 text-white shadow-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="bg-lime-400 text-emerald-950 p-2 rounded-xl">
            <Trophy className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-base leading-tight">Pickleball SOA Arena</div>
            <div className="text-[11px] text-emerald-300">Microservices Booking & QR Check-in</div>
          </div>
        </Link>

        <nav className="flex flex-wrap items-center gap-1.5">
          <Link to="/" className={linkClass('/')}>
            <Calendar className="w-4 h-4" />
            <span>Đặt sân</span>
          </Link>
          <Link to="/lookup" className={linkClass('/lookup')}>
            <Search className="w-4 h-4" />
            <span>Tra cứu vé</span>
          </Link>
          {user && (
            <Link to="/my-bookings" className={linkClass('/my-bookings')}>
              <UserCheck className="w-4 h-4" />
              <span>Lịch sử</span>
            </Link>
          )}
          {(user?.role === 'STAFF' || user?.role === 'ADMIN') && (
            <Link to="/staff/scanner" className={linkClass('/staff/scanner')}>
              <QrCode className="w-4 h-4" />
              <span>Quét QR</span>
            </Link>
          )}
          {user?.role === 'ADMIN' && (
            <Link to="/admin" className={linkClass('/admin')}>
              <ShieldCheck className="w-4 h-4" />
              <span>Quản trị</span>
            </Link>
          )}
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <div className="flex items-center gap-2 bg-emerald-800/80 px-3 py-1.5 rounded-lg border border-emerald-700">
              <div className="text-right">
                <div className="text-xs font-semibold leading-tight">{user.full_name}</div>
                <div className="text-[10px] text-lime-300 font-medium">{user.role}</div>
              </div>
              <button
                onClick={() => {
                  logout();
                  navigate('/');
                }}
                className="p-1.5 text-emerald-200 hover:text-white hover:bg-emerald-700 rounded-md"
                title="Đăng xuất"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-1.5 bg-lime-400 hover:bg-lime-300 text-emerald-950 font-semibold px-3.5 py-2 rounded-lg text-sm transition"
            >
              <LogIn className="w-4 h-4" />
              <span>Đăng nhập</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
