import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { KeyRound, LogIn } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const u = await login(email, password);
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
    <div className="max-w-md mx-auto mt-10 bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center gap-2.5 mb-5">
        <div className="bg-emerald-100 text-emerald-700 p-2.5 rounded-xl">
          <LogIn className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-900">Đăng nhập hệ thống</h1>
          <p className="text-xs text-slate-500">Khách hàng vẫn có thể đặt sân nhanh mà không cần đăng nhập</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Mật khẩu</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg text-sm transition"
        >
          {submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
        </button>
      </form>

      <div className="mt-6 pt-4 border-t border-slate-200">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 mb-2">
          <KeyRound className="w-3.5 h-3.5 text-emerald-600" />
          <span>Tài khoản Demo nhanh (thuyết trình):</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => quickFill('khachhang@pickleball.vn', 'Customer@123')}
            className="text-xs px-2 py-1.5 rounded-lg border border-slate-200 hover:bg-emerald-50 text-slate-700 font-medium"
          >
            Khách hàng
          </button>
          <button
            type="button"
            onClick={() => quickFill('staff@pickleball.vn', 'Staff@123')}
            className="text-xs px-2 py-1.5 rounded-lg border border-slate-200 hover:bg-emerald-50 text-slate-700 font-medium"
          >
            Nhân viên QR
          </button>
          <button
            type="button"
            onClick={() => quickFill('admin@pickleball.vn', 'Admin@123')}
            className="text-xs px-2 py-1.5 rounded-lg border border-slate-200 hover:bg-emerald-50 text-slate-700 font-medium"
          >
            Admin Chủ sân
          </button>
        </div>
      </div>

      <p className="mt-5 text-center text-sm text-slate-600">
        Chưa có tài khoản?{' '}
        <Link to="/register" className="text-emerald-700 font-semibold hover:underline">
          Đăng ký thành viên
        </Link>
      </p>
    </div>
  );
};
