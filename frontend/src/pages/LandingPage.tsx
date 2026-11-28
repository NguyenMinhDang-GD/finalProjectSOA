import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Building2, CalendarCheck2, MapPin, QrCode, Search } from 'lucide-react';
import { apiRequest } from '../api/client';
import heroClubImg from '../assets/images/hero-club.webp';
import courtIndoorImg from '../assets/images/court-indoor.webp';
import courtOutdoorImg from '../assets/images/court-outdoor.webp';
import { StatusBadge } from '../components/ui/StatusBadge';
import { BranchItem, Court } from '../types';

export const LandingPage: React.FC = () => {
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [courts, setCourts] = useState<Court[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      apiRequest<BranchItem[]>('/api/branches'),
      apiRequest<Court[]>('/api/courts'),
    ])
      .then(([brRes, ctRes]) => {
        if (brRes.status === 'fulfilled') setBranches(brRes.value);
        if (ctRes.status === 'fulfilled') setCourts(ctRes.value);
      })
      .finally(() => setLoading(false));
  }, []);

  const indoorCount = courts.filter((c) => c.court_type === 'INDOOR').length;
  const outdoorCount = courts.filter((c) => c.court_type === 'OUTDOOR').length;

  return (
    <div className="bg-warm-white">
      {/* Editorial Asymmetric Hero */}
      <section className="bg-court text-white border-b border-[#23483D]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 lg:py-14 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-center">
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-court-deep border border-[#2D584B] text-[11px] font-bold uppercase tracking-[0.18em] text-ball-lime">
              <span>Contemporary Athletic Club</span>
            </div>

            <h1 className="font-display text-4xl sm:text-5xl lg:text-[56px] font-extrabold tracking-tight leading-[1.03] text-white">
              LÊN SÂN.
              <br />
              <span className="text-ball-lime">VÀO TRẬN.</span>
            </h1>

            <p className="text-base sm:text-lg text-[#D1DDD6] leading-relaxed max-w-xl">
              Đặt sân Pickleball chuẩn thi đấu theo chi nhánh và khung giờ thực tế. Giữ chỗ 15 phút, thanh toán VietQR và nhận vé check-in QR tức thì.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Link
                to="/book"
                className="inline-flex items-center gap-2 bg-ball-lime hover:bg-[#cde94b] text-court font-bold px-6 py-3.5 rounded-xl text-sm sm:text-base transition-colors shadow-sm"
              >
                <span>Đặt sân ngay</span>
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </Link>
              <a
                href="#branches"
                className="inline-flex items-center gap-2 border border-[#3B6D5E] hover:border-ball-lime text-white hover:text-ball-lime font-semibold px-5 py-3.5 rounded-xl text-sm sm:text-base transition-colors"
              >
                <span>Khám phá chi nhánh</span>
              </a>
              <Link
                to="/lookup"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[#B7C9BE] hover:text-white px-2 py-2"
              >
                <Search className="w-4 h-4" aria-hidden="true" />
                <span>Tra cứu vé</span>
              </Link>
            </div>

            {/* Real backend club summary */}
            {!loading && (branches.length > 0 || courts.length > 0) && (
              <div className="pt-5 border-t border-[#264C41] grid grid-cols-3 gap-4 max-w-md">
                <div>
                  <div className="font-display text-2xl font-extrabold text-white tabular-nums">
                    {branches.length}
                  </div>
                  <div className="text-xs text-[#A8BCB1]">Chi nhánh hoạt động</div>
                </div>
                <div>
                  <div className="font-display text-2xl font-extrabold text-ball-lime tabular-nums">
                    {indoorCount}
                  </div>
                  <div className="text-xs text-[#A8BCB1]">Sân trong nhà</div>
                </div>
                <div>
                  <div className="font-display text-2xl font-extrabold text-white tabular-nums">
                    {outdoorCount}
                  </div>
                  <div className="text-xs text-[#A8BCB1]">Sân ngoài trời</div>
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-6">
            <figure className="relative rounded-2xl overflow-hidden border border-[#2D584B] bg-court-deep shadow-2xl">
              <img
                src={heroClubImg}
                alt="Không gian sân Pickleball SOA Arena với mặt sân xanh chuẩn thi đấu"
                width={1376}
                height={768}
                className="w-full aspect-[16/10] object-cover block"
              />
              <figcaption className="absolute bottom-3 right-3 bg-court-deep/85 backdrop-blur-sm text-[#D6E1DA] text-[11px] px-2.5 py-1 rounded-md border border-[#335F52]">
                Hình ảnh minh họa
              </figcaption>
            </figure>
          </div>
        </div>
      </section>

      {/* Court Environments (Indoor / Outdoor) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12 lg:py-16">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-terracotta">
              Không gian thi đấu
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal mt-1">
              Sân Trong nhà &amp; Ngoài trời chuẩn câu lạc bộ
            </h2>
          </div>
          <Link
            to="/book"
            className="inline-flex items-center gap-1.5 text-sm font-bold text-court hover:underline"
          >
            <span>Xem lịch trống hôm nay</span>
            <ArrowRight className="w-4 h-4" aria-hidden="true" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <article className="bg-white rounded-2xl border border-[#DCDCD2] overflow-hidden flex flex-col">
            <div className="relative">
              <img
                src={courtIndoorImg}
                alt="Sân Pickleball trong nhà tại câu lạc bộ"
                width={960}
                height={717}
                loading="lazy"
                className="w-full aspect-[16/10] object-cover block"
              />
              <span className="absolute bottom-2.5 right-2.5 bg-court-deep/80 text-white text-[10px] px-2 py-0.5 rounded">
                Hình ảnh minh họa
              </span>
            </div>
            <div className="p-6 flex-1 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <StatusBadge status="INDOOR" />
                  <span className="text-xs font-semibold text-court-muted tabular-nums">
                    {indoorCount} sân hiện có
                  </span>
                </div>
                <h3 className="font-display text-xl font-bold text-charcoal mt-3">
                  Cụm sân Trong nhà (Indoor)
                </h3>
                <p className="text-sm text-court-muted mt-1.5 leading-relaxed">
                  Thi đấu ổn định bất kể thời tiết với mái che và hệ thống chiếu sáng đồng đều. Phù hợp tập luyện và thi đấu giao lưu cả ngày.
                </p>
              </div>
              <Link
                to="/book"
                className="inline-flex items-center gap-1.5 text-sm font-bold text-court hover:text-terracotta transition-colors"
              >
                <span>Chọn giờ sân trong nhà</span>
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </Link>
            </div>
          </article>

          <article className="bg-white rounded-2xl border border-[#DCDCD2] overflow-hidden flex flex-col">
            <div className="relative">
              <img
                src={courtOutdoorImg}
                alt="Sân Pickleball ngoài trời thoáng đãng"
                width={960}
                height={717}
                loading="lazy"
                className="w-full aspect-[16/10] object-cover block"
              />
              <span className="absolute bottom-2.5 right-2.5 bg-court-deep/80 text-white text-[10px] px-2 py-0.5 rounded">
                Hình ảnh minh họa
              </span>
            </div>
            <div className="p-6 flex-1 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <StatusBadge status="OUTDOOR" />
                  <span className="text-xs font-semibold text-court-muted tabular-nums">
                    {outdoorCount} sân hiện có
                  </span>
                </div>
                <h3 className="font-display text-xl font-bold text-charcoal mt-3">
                  Cụm sân Ngoài trời (Outdoor)
                </h3>
                <p className="text-sm text-court-muted mt-1.5 leading-relaxed">
                  Không gian thoáng đãng, ánh sáng tự nhiên ban ngày và đèn sân buổi tối. Vạch kẻ sân rõ nét, phù hợp nhóm bạn và giải đấu phong trào.
                </p>
              </div>
              <Link
                to="/book"
                className="inline-flex items-center gap-1.5 text-sm font-bold text-court hover:text-terracotta transition-colors"
              >
                <span>Chọn giờ sân ngoài trời</span>
                <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </Link>
            </div>
          </article>
        </div>
      </section>

      {/* Real Branches & Locations */}
      <section id="branches" className="bg-[#EFEFE6] border-y border-[#DCDCD2] py-12 lg:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="mb-8">
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-court">
              Hệ thống địa điểm thực tế
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal mt-1">
              Chi nhánh &amp; Cụm sân đang hoạt động
            </h2>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="h-36 rounded-2xl bg-[#E3E3D8] animate-pulse" />
              <div className="h-36 rounded-2xl bg-[#E3E3D8] animate-pulse" />
            </div>
          ) : branches.length === 0 ? (
            <div className="bg-white rounded-2xl border border-[#DCDCD2] p-6 text-sm text-court-muted">
              Chưa có chi nhánh nào được cấu hình trên hệ thống.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {branches.map((branch) => (
                <div
                  key={branch.id}
                  className="bg-white rounded-2xl border border-[#DCDCD2] p-6 flex flex-col justify-between gap-5"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded-xl bg-court text-ball-lime flex items-center justify-center shrink-0">
                          <Building2 className="w-4 h-4" aria-hidden="true" />
                        </div>
                        <div>
                          <h3 className="font-display text-lg font-bold text-charcoal">
                            {branch.display_name}
                          </h3>
                          {branch.title_note && (
                            <p className="text-xs text-court-muted">{branch.title_note}</p>
                          )}
                        </div>
                      </div>
                      <span className="text-xs font-semibold bg-[#E9EFEA] text-court px-2.5 py-1 rounded-md tabular-nums">
                        {branch.locations.length} địa điểm
                      </span>
                    </div>

                    <ul className="mt-4 space-y-2.5">
                      {branch.locations.map((loc) => (
                        <li
                          key={loc.id}
                          className="flex items-start justify-between gap-3 p-3 rounded-xl bg-warm-white border border-[#E5E5DC]"
                        >
                          <div className="flex items-start gap-2 min-w-0">
                            <MapPin className="w-4 h-4 text-terracotta shrink-0 mt-0.5" aria-hidden="true" />
                            <div className="min-w-0">
                              <div className="text-sm font-bold text-charcoal">{loc.name}</div>
                              <div className="text-xs text-court-muted break-words">{loc.address}</div>
                            </div>
                          </div>
                          <span className="text-xs font-bold text-court shrink-0 tabular-nums">
                            {loc.court_count} sân
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="pt-2 border-t border-[#ECEBE2] flex items-center justify-between">
                    <span className="text-xs text-court-muted">Đặt nhanh không cần tạo tài khoản</span>
                    <Link
                      to={`/book?branch_id=${branch.id}`}
                      className="inline-flex items-center gap-1.5 text-sm font-bold text-court hover:text-terracotta transition-colors"
                    >
                      <span>Đặt tại chi nhánh này</span>
                      <ArrowRight className="w-4 h-4" aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* 3-Step Booking Workflow */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12 lg:py-16">
        <div className="max-w-2xl mb-8">
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-court">
            Quy trình đơn giản
          </div>
          <h2 className="font-display text-2xl sm:text-3xl font-extrabold text-charcoal mt-1">
            Từ lúc chọn sân đến khi check-in trong 3 bước
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-white rounded-2xl border border-[#DCDCD2] p-6 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-terracotta">01</span>
              <CalendarCheck2 className="w-5 h-5 text-court" aria-hidden="true" />
            </div>
            <h3 className="font-display text-lg font-bold text-charcoal">
              Chọn sân &amp; khung giờ liên tiếp
            </h3>
            <p className="text-sm text-court-muted leading-relaxed">
              Lọc theo chi nhánh, ngày chơi và chọn từ 1 đến 6 khung giờ 60 phút liên tiếp với bảng giá hiển thị rõ từng giờ.
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-[#DCDCD2] p-6 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-terracotta">02</span>
              <Building2 className="w-5 h-5 text-court" aria-hidden="true" />
            </div>
            <h3 className="font-display text-lg font-bold text-charcoal">
              Giữ chỗ 15 phút &amp; VietQR
            </h3>
            <p className="text-sm text-court-muted leading-relaxed">
              Hệ thống khóa khung giờ trong 15 phút để bạn hoàn tất chuyển khoản VietQR. Trạng thái được đồng bộ tự động.
            </p>
          </div>

          <div className="bg-white rounded-2xl border border-[#DCDCD2] p-6 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs font-bold text-terracotta">03</span>
              <QrCode className="w-5 h-5 text-court" aria-hidden="true" />
            </div>
            <h3 className="font-display text-lg font-bold text-charcoal">
              Nhận vé QR &amp; Check-in tại sân
            </h3>
            <p className="text-sm text-court-muted leading-relaxed">
              Vé điện tử kèm mã QR ký số được gửi qua email và hiển thị trực tiếp để nhân viên quét nhanh khi bạn đến sân.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
