import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronDown, Eye, EyeOff, KeyRound, LogIn } from 'lucide-react';
import authEditorialImg from '../assets/images/auth-editorial.webp';
import { BrandLockup } from '../components/brand/BrandLogo';
import { Button } from '../components/ui/Button';
import { AlertBanner } from '../components/ui/FeedbackStates';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const u = await login(email.trim(), password);
      if (u.role === 'STAFF') navigate('/staff/scanner');
      else if (u.role === 'ADMIN') navigate('/admin');
      else navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại');
    } finally {
      setSubmitting(false);
    }
  };

  const quickFill = (demoEmail: string, demoPw: string) => {
    setEmail(demoEmail);
    setPassword(demoPw);
    setError('');
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-warm-white grid grid-cols-1 lg:grid-cols-12">
      {/* Editorial Visual Panel (compact on mobile, full-height split on desktop) */}
      <div className="lg:col-span-6 relative bg-court text-white overflow-hidden flex flex-col justify-between p-6 sm:p-10 lg:p-14 min-h-[200px] lg:min-h-full">
        <img
          src={authEditorialImg}
          alt="Vợt và bóng Pickleball trên mặt sân xanh câu lạc bộ"
          width={896}
          height={1200}
          className="absolute inset-0 w-full h-full object-cover opacity-45"
        />
        <div
          className="absolute inset-0 bg-gradient-to-t from-court-deep via-court/75 to-court/60"
          aria-hidden="true"
        />

        <div className="relative z-10 flex items-center justify-between gap-3">
          <BrandLockup theme="dark" />
          <span className="text-[10px] bg-court-deep/80 text-[#C7D6CD] px-2.5 py-1 rounded border border-[#2F5B4E]">
            Hình ảnh minh họa
          </span>
        </div>

        <div className="relative z-10 mt-8 lg:mt-0 space-y-3 max-w-md">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-ball-lime">
            Member Access
          </div>
          <h2 className="font-display text-2xl sm:text-4xl font-extrabold leading-tight">
            Quản lý lịch chơi &amp; vé QR tại một nơi.
          </h2>
          <p className="text-sm text-[#D1DDD6] leading-relaxed hidden sm:block">
            Đăng nhập để tự động điền thông tin khi đặt sân, xem lại toàn bộ lịch sử giao dịch và mở nhanh vé check-in QR của bạn.
          </p>
        </div>
      </div>

      {/* Focused Authentication Panel */}
      <div className="lg:col-span-6 flex items-center justify-center px-4 sm:px-8 py-8 lg:py-12">
        <div className="w-full max-w-md space-y-6">
          <div>
            <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-terracotta mb-1.5">
              <LogIn className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Tài khoản thành viên</span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal">
              Đăng nhập hệ thống
            </h1>
            <p className="text-sm text-court-muted mt-1">
              Khách vãng lai vẫn có thể{' '}
              <Link to="/book" className="text-court font-semibold hover:underline">
                đặt sân nhanh
              </Link>{' '}
              mà không cần đăng nhập.
            </p>
          </div>

          {error && <AlertBanner tone="error">{error}</AlertBanner>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="block text-sm font-semibold text-charcoal mb-1.5">
                Email
              </label>
              <input
                id="login-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-xl border border-[#CFCFC4] bg-white px-4 py-3 text-sm focus:ring-2 focus:ring-court focus:border-court focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="login-password" className="block text-sm font-semibold text-charcoal mb-1.5">
                Mật khẩu
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPw ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu"
                  className="w-full rounded-xl border border-[#CFCFC4] bg-white pl-4 pr-11 py-3 text-sm focus:ring-2 focus:ring-court focus:border-court focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-court-muted hover:text-charcoal rounded-lg"
                  aria-label={showPw ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" variant="primary" size="lg" loading={submitting} className="w-full py-3.5">
              {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </Button>
          </form>

          <p className="text-sm text-court-muted">
            Chưa có tài khoản?{' '}
            <Link to="/register" className="text-court font-bold hover:underline">
              Đăng ký thành viên mới
            </Link>
          </p>

          {/* Secondary collapsible presentation/demo autofill */}
          <div className="pt-4 border-t border-[#DCDCD2]">
            <button
              type="button"
              onClick={() => setDemoOpen((v) => !v)}
              aria-expanded={demoOpen}
              className="w-full flex items-center justify-between gap-2 text-xs font-semibold text-court-muted hover:text-charcoal py-1.5"
            >
              <span className="inline-flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5 text-court" aria-hidden="true" />
                <span>Chế độ thuyết trình (Điền nhanh tài khoản mẫu)</span>
              </span>
              <ChevronDown
                className={`w-4 h-4 transition-transform ${demoOpen ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </button>

            {demoOpen && (
              <div className="mt-2.5 p-3 rounded-xl bg-white border border-dashed border-[#C9CBC1] space-y-2">
                <p className="text-[11px] text-court-muted">
                  Tài khoản phục vụ kiểm thử và thuyết trình đồ án theo từng vai trò:
                </p>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => quickFill('khachhang@pickleball.vn', 'Customer@123')}
                    className="text-xs px-2.5 py-2 rounded-lg border border-[#D4D6CD] bg-warm-white hover:bg-[#E9EFEA] text-charcoal font-semibold transition-colors"
                  >
                    Khách hàng
                  </button>
                  <button
                    type="button"
                    onClick={() => quickFill('staff@pickleball.vn', 'Staff@123')}
                    className="text-xs px-2.5 py-2 rounded-lg border border-[#D4D6CD] bg-warm-white hover:bg-[#E9EFEA] text-charcoal font-semibold transition-colors"
                  >
                    Nhân viên
                  </button>
                  <button
                    type="button"
                    onClick={() => quickFill('admin@pickleball.vn', 'Admin@123')}
                    className="text-xs px-2.5 py-2 rounded-lg border border-[#D4D6CD] bg-warm-white hover:bg-[#E9EFEA] text-charcoal font-semibold transition-colors"
                  >
                    Admin
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
