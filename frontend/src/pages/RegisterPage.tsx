import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, UserPlus } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { AlertBanner } from '../components/ui/FeedbackStates';
import { useAuth } from '../context/AuthContext';

export const RegisterPage: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
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
      await register({
        full_name: fullName.trim(),
        phone: phone.trim(),
        email: email.trim(),
        password,
      });
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng ký thất bại');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-10">
      <div className="bg-white rounded-2xl border border-[#D4D6CD] p-6 sm:p-8 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="bg-court text-ball-lime p-2.5 rounded-xl">
            <UserPlus className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-charcoal">Đăng ký thành viên</h1>
            <p className="text-xs text-court-muted">
              Lưu lịch sử đặt sân và theo dõi vé QR mọi lúc
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
            <label htmlFor="reg-name" className="block text-sm font-semibold text-charcoal mb-1">
              Họ và tên
            </label>
            <input
              id="reg-name"
              type="text"
              required
              minLength={2}
              maxLength={150}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Nguyễn Văn A"
              className="w-full rounded-lg border border-[#D4D6CD] px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-court focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="reg-phone" className="block text-sm font-semibold text-charcoal mb-1">
              Số điện thoại
            </label>
            <input
              id="reg-phone"
              type="tel"
              required
              minLength={8}
              maxLength={20}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="0901234567"
              className="w-full rounded-lg border border-[#D4D6CD] px-3.5 py-2.5 text-sm focus:ring-2 focus:ring-court focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="reg-email" className="block text-sm font-semibold text-charcoal mb-1">
              Email
            </label>
            <input
              id="reg-email"
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
            <label htmlFor="reg-password" className="block text-sm font-semibold text-charcoal mb-1">
              Mật khẩu (tối thiểu 6 ký tự)
            </label>
            <div className="relative">
              <input
                id="reg-password"
                type={showPw ? 'text' : 'password'}
                required
                minLength={6}
                maxLength={100}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••"
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
            {submitting ? 'Đang tạo tài khoản...' : 'Tạo tài khoản'}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-court-muted">
          Đã có tài khoản?{' '}
          <Link to="/login" className="text-court font-bold hover:underline">
            Đăng nhập
          </Link>
        </p>
      </div>
    </div>
  );
};
