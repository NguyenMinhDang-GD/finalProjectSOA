import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, KeyRound, LogIn } from 'lucide-react';
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
    <div className="max-w-md mx-auto px-4 py-10">
      <div className="bg-white rounded-2xl border border-[#D4D6CD] p-6 sm:p-8 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="bg-court text-ball-lime p-2.5 rounded-xl">
            <LogIn className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-charcoal">Đăng nhập thành viên</h1>
            <p className="text-xs text-court-muted">
              Khách vãng lai vẫn có thể đặt sân nhanh mà không cần tài khoản
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4">
            <AlertBanner tone="error">{error}</AlertBanner>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-sm font-semibold text-charcoal mb-1">
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
              className="w-full rounded-lg border border-[#D4D6CD] px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-court focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="login-password" className="block text-sm font-semibold text-charcoal mb-1">
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
                className="w-full rounded-lg border border-[#D4D6CD] pl-3.5 pr-10 py-2.5 text-sm focus:ring-2 focus:ring-court focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPw((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-court-muted hover:text-charcoal"
                aria-label={showPw ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <Button type="submit" variant="primary" size="lg" loading={submitting} className="w-full">
            {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-[#ECEBE2]">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-court-muted mb-2.5">
            <KeyRound className="w-3.5 h-3.5 text-court" aria-hidden="true" />
            <span>Hỗ trợ thuyết trình (Điền nhanh tài khoản mẫu):</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => quickFill('khachhang@pickleball.vn', 'Customer@123')}
              className="text-xs px-2 py-2 rounded-lg border border-[#D4D6CD] bg-warm-white hover:bg-[#E9EFEA] text-charcoal font-semibold transition-colors"
            >
              Khách hàng
            </button>
            <button
              type="button"
              onClick={() => quickFill('staff@pickleball.vn', 'Staff@123')}
              className="text-xs px-2 py-2 rounded-lg border border-[#D4D6CD] bg-warm-white hover:bg-[#E9EFEA] text-charcoal font-semibold transition-colors"
            >
              Nhân viên
            </button>
            <button
              type="button"
              onClick={() => quickFill('admin@pickleball.vn', 'Admin@123')}
              className="text-xs px-2 py-2 rounded-lg border border-[#D4D6CD] bg-warm-white hover:bg-[#E9EFEA] text-charcoal font-semibold transition-colors"
            >
              Admin
            </button>
          </div>
        </div>

        <p className="mt-5 text-center text-sm text-court-muted">
          Chưa có tài khoản?{' '}
          <Link to="/register" className="text-court font-bold hover:underline">
            Đăng ký thành viên
          </Link>
        </p>
      </div>
    </div>
  );
};
