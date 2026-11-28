import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => (
  <div className="max-w-lg mx-auto px-4 py-16 text-center">
    <div className="bg-white rounded-2xl border border-[#CFCFC4] p-8 shadow-sm">
      <div className="text-xs font-mono font-bold uppercase tracking-widest text-terracotta">
        404 — Không tìm thấy trang
      </div>
      <h1 className="font-display mt-2 text-2xl font-extrabold text-charcoal">
        Đường dẫn không tồn tại
      </h1>
      <p className="mt-2 text-sm text-court-muted">
        Trang bạn đang tìm không có trong hệ thống đặt sân Pickleball SOA Arena.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 bg-court hover:bg-court-soft text-white font-semibold px-5 py-2.5 rounded-xl text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" aria-hidden="true" />
        Quay về trang chủ
      </Link>
    </div>
  </div>
);
