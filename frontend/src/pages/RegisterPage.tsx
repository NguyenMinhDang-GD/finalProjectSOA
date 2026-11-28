import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, UserPlus } from 'lucide-react';
import authEditorialImg from '../assets/images/auth-editorial.webp';
import { BrandLockup } from '../components/brand/BrandLogo';
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
    <div className="min-h-[calc(100vh-4rem)] bg-warm-white grid grid-cols-1 lg:grid-cols-12">
      {/* Editorial Visual Panel */}
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
            Join The Club
          </div>
          <h2 className="font-display text-2xl sm:text-4xl font-extrabold leading-tight">
            Tạo tài khoản thành viên trong 30 giây.
          </h2>
          <p className="text-sm text-[#D1DDD6] leading-relaxed hidden sm:block">
            Lưu trữ lịch sử đặt sân, theo dõi trạng thái thanh toán VietQR và truy cập vé QR check-in mọi lúc.
          </p>
        </div>
      </div>

      {/* Registration Form Panel */}
      <div className="lg:col-span-6 flex items-center justify-center px-4 sm:px-8 py-8 lg:py-12">
        <div className="w-full max-w-md space-y-6">
          <div>
            <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-terracotta mb-1.5">
              <UserPlus className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Thành viên mới</span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal">
              Đăng ký tài khoản
            </h1>
            <p className="text-sm text-court-muted mt-1">
              Thông tin của bạn được dùng để điền sẵn đơn đặt sân và gửi vé QR.
            </p>
          </div>

          {error && <AlertBanner tone="error">{error}</AlertBanner>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="reg-name" className="block text-sm font-semibold text-charcoal mb-1.5">
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
                className="w-full rounded-xl border border-[#CFCFC4] bg-white px-4 py-3 text-sm focus:ring-2 focus:ring-court focus:border-court focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="reg-phone" className="block text-sm font-semibold text-charcoal mb-1.5">
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
                className="w-full rounded-xl border border-[#CFCFC4] bg-white px-4 py-3 text-sm focus:ring-2 focus:ring-court focus:border-court focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="reg-email" className="block text-sm font-semibold text-charcoal mb-1.5">
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
                className="w-full rounded-xl border border-[#CFCFC4] bg-white px-4 py-3 text-sm focus:ring-2 focus:ring-court focus:border-court focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="reg-password" className="block text-sm font-semibold text-charcoal mb-1.5">
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
              {submitting ? 'Đang tạo tài khoản...' : 'Tạo tài khoản'}
            </Button>
          </form>

          <p className="text-sm text-court-muted">
            Đã có tài khoản?{' '}
            <Link to="/login" className="text-court font-bold hover:underline">
              Đăng nhập ngay
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};
