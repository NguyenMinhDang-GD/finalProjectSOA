import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  Building2,
  Coins,
  Edit3,
  Mail,
  MapPin,
  PlusCircle,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react';
import { apiRequest, formatVND } from '../api/client';
import { useAuth } from '../context/AuthContext';
import {
  AdminStats,
  BookingOrder,
  BranchItem,
  Court,
  LocationItem,
  NotificationLog,
  PricingRule,
} from '../types';

export const AdminDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState<'courts' | 'pricing' | 'bookings' | 'emails'>('courts');
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState<string>('');
  const [selectedLocationId, setSelectedLocationId] = useState<string>('');
  const [courts, setCourts] = useState<Court[]>([]);
  const [rules, setRules] = useState<PricingRule[]>([]);
  const [bookings, setBookings] = useState<BookingOrder[]>([]);
  const [emails, setEmails] = useState<NotificationLog[]>([]);

  // Branch create / edit states
  const [newBranchNote, setNewBranchNote] = useState('');
  const [editingBranchId, setEditingBranchId] = useState<string | null>(null);
  const [editBranchNote, setEditBranchNote] = useState('');

  // Location create / edit states
  const [newLocationName, setNewLocationName] = useState('');
  const [newLocationAddress, setNewLocationAddress] = useState('');
  const [editingLocation, setEditingLocation] = useState<LocationItem | null>(null);

  // Court create / edit states
  const [newCourtName, setNewCourtName] = useState('');
  const [newCourtType, setNewCourtType] = useState<'INDOOR' | 'OUTDOOR'>('INDOOR');
  const [newCourtSurface, setNewCourtSurface] = useState('Acrylic 7 lớp chuẩn USAPA');
  const [newCourtDesc, setNewCourtDesc] = useState('');
  const [editingCourt, setEditingCourt] = useState<Court | null>(null);

  const [priceEdits, setPriceEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const notifyOk = (msg: string) => {
    setErrorMsg('');
    setMessage(msg);
  };

  const notifyErr = (err: unknown) => {
    setMessage('');
    setErrorMsg(err instanceof Error ? err.message : 'Thao tác thất bại');
  };

  const loadAll = useCallback(async () => {
    try {
      const [s, br, c, r, b, e] = await Promise.all([
        apiRequest<AdminStats>('/api/bookings/admin/stats'),
        apiRequest<BranchItem[]>('/api/branches'),
        apiRequest<Court[]>('/api/courts?include_inactive=true'),
        apiRequest<PricingRule[]>('/api/pricing-rules'),
        apiRequest<BookingOrder[]>('/api/bookings/admin/list'),
        apiRequest<NotificationLog[]>('/api/notifications/logs'),
      ]);
      setStats(s);
      setBranches(br);
      setCourts(c);
      setRules(r);
      setBookings(b);
      setEmails(e);

      const map: Record<string, string> = {};
      r.forEach((rule) => {
        map[rule.id] = String(rule.price_per_hour);
      });
      setPriceEdits(map);

      setSelectedBranchId((prev) => {
        if (prev && br.some((item) => item.id === prev)) return prev;
        return br[0]?.id || '';
      });
    } catch (err) {
      notifyErr(err);
    }
  }, []);

  useEffect(() => {
    if (user?.role === 'ADMIN') loadAll();
  }, [user, loadAll]);

  const activeBranch = branches.find((b) => b.id === selectedBranchId) || null;

  useEffect(() => {
    if (!activeBranch) {
      setSelectedLocationId('');
      return;
    }
    setSelectedLocationId((prev) => {
      if (prev && activeBranch.locations.some((loc) => loc.id === prev)) return prev;
      return activeBranch.locations[0]?.id || '';
    });
  }, [activeBranch]);

  const activeLocation = activeBranch?.locations.find((loc) => loc.id === selectedLocationId) || null;
  const locationCourts = courts.filter((c) => c.location_id === selectedLocationId);

  // -------- Branch Handlers --------
  const handleAddBranch = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await apiRequest<BranchItem>('/api/branches', {
        method: 'POST',
        body: JSON.stringify({ title_note: newBranchNote.trim() }),
      });
      setNewBranchNote('');
      await loadAll();
      setSelectedBranchId(created.id);
      setSelectedLocationId('');
      notifyOk(`Đã tạo tự động ${created.display_name}`);
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleSaveBranchNote = async (branchId: string) => {
    try {
      await apiRequest(`/api/branches/${branchId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title_note: editBranchNote.trim() }),
      });
      setEditingBranchId(null);
      notifyOk('Đã cập nhật thông tin chi nhánh');
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleDeleteBranch = async (branch: BranchItem) => {
    if (!window.confirm(`Xác nhận xóa "${branch.display_name}"?`)) return;
    try {
      const res = await apiRequest<{ message: string }>(`/api/branches/${branch.id}`, {
        method: 'DELETE',
      });
      notifyOk(res.message);
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  // -------- Location Handlers --------
  const handleAddLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBranchId || !newLocationName.trim() || !newLocationAddress.trim()) return;
    try {
      const created = await apiRequest<LocationItem>('/api/locations', {
        method: 'POST',
        body: JSON.stringify({
          branch_id: selectedBranchId,
          name: newLocationName.trim(),
          address: newLocationAddress.trim(),
        }),
      });
      setNewLocationName('');
      setNewLocationAddress('');
      await loadAll();
      setSelectedLocationId(created.id);
      notifyOk(`Đã thêm địa điểm "${created.name}"`);
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleSaveLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingLocation) return;
    try {
      await apiRequest(`/api/locations/${editingLocation.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editingLocation.name,
          address: editingLocation.address,
        }),
      });
      setEditingLocation(null);
      notifyOk('Đã cập nhật địa điểm');
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleDeleteLocation = async (loc: LocationItem) => {
    if (!window.confirm(`Xác nhận xóa địa điểm "${loc.name}"?`)) return;
    try {
      const res = await apiRequest<{ message: string }>(`/api/locations/${loc.id}`, {
        method: 'DELETE',
      });
      notifyOk(res.message);
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  // -------- Court Handlers --------
  const handleAddCourt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLocationId || !newCourtName.trim()) return;
    try {
      await apiRequest('/api/courts', {
        method: 'POST',
        body: JSON.stringify({
          location_id: selectedLocationId,
          name: newCourtName.trim(),
          court_type: newCourtType,
          surface: newCourtSurface.trim() || 'Acrylic 7 lớp chuẩn thi đấu',
          description: newCourtDesc.trim(),
        }),
      });
      setNewCourtName('');
      setNewCourtDesc('');
      notifyOk('Đã thêm sân mới vào địa điểm đã chọn');
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleSaveCourt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCourt) return;
    try {
      await apiRequest(`/api/courts/${editingCourt.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editingCourt.name,
          court_type: editingCourt.court_type,
          surface: editingCourt.surface,
          status: editingCourt.status,
          description: editingCourt.description,
        }),
      });
      setEditingCourt(null);
      notifyOk('Đã cập nhật thông tin sân');
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleToggleCourtStatus = async (court: Court) => {
    try {
      const nextStatus = court.status === 'ACTIVE' ? 'MAINTENANCE' : 'ACTIVE';
      await apiRequest(`/api/courts/${court.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      });
      notifyOk(`Đã chuyển sân "${court.name}" sang ${nextStatus}`);
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleDeleteCourt = async (court: Court) => {
    if (!window.confirm(`Xác nhận xóa sân "${court.name}"?`)) return;
    try {
      const res = await apiRequest<{ message: string }>(`/api/courts/${court.id}`, {
        method: 'DELETE',
      });
      notifyOk(res.message);
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleSavePrice = async (ruleId: string) => {
    const val = Number(priceEdits[ruleId]);
    if (!val || val <= 0) return;
    try {
      await apiRequest(`/api/pricing-rules/${ruleId}`, {
        method: 'PUT',
        body: JSON.stringify({ price_per_hour: val }),
      });
      notifyOk('Đã cập nhật bảng giá');
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  const handleAdminCancel = async (bookingCode: string) => {
    try {
      await apiRequest(`/api/bookings/admin/${bookingCode}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason: 'Admin hủy đơn ngoại lệ' }),
      });
      notifyOk(`Đã hủy đơn ${bookingCode}`);
      loadAll();
    } catch (err) {
      notifyErr(err);
    }
  };

  if (!user || user.role !== 'ADMIN') {
    return (
      <div className="max-w-xl mx-auto mt-10 bg-white p-6 rounded-2xl border border-red-200 text-center text-red-700 font-medium">
        Chỉ tài khoản Quản trị viên (ADMIN) mới có quyền truy cập trang này.
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-6 h-6 text-emerald-700" />
          <span>Bảng điều khiển Quản trị Sân (Admin)</span>
        </h1>
        {message && (
          <span className="text-xs font-semibold bg-emerald-100 text-emerald-800 px-3.5 py-1.5 rounded-full border border-emerald-200">
            {message}
          </span>
        )}
        {errorMsg && (
          <span className="text-xs font-semibold bg-red-100 text-red-700 px-3.5 py-1.5 rounded-full border border-red-200">
            {errorMsg}
          </span>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Tổng doanh thu (Đã thanh toán)</div>
            <div className="text-xl font-bold text-emerald-700 mt-1">{formatVND(stats.total_revenue)}</div>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Đơn đã thanh toán</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{stats.paid_bookings}</div>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Đơn chờ thanh toán</div>
            <div className="text-xl font-bold text-amber-600 mt-1">{stats.pending_bookings}</div>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
            <div className="text-xs text-slate-500">Tổng số sân đang hoạt động</div>
            <div className="text-xl font-bold text-slate-900 mt-1">{stats.active_courts}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setTab('courts')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'courts' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <Building2 className="w-4 h-4" /> Chi nhánh, Địa điểm & Sân
        </button>
        <button
          onClick={() => setTab('pricing')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'pricing' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <Coins className="w-4 h-4" /> Bảng giá Khung giờ
        </button>
        <button
          onClick={() => setTab('bookings')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'bookings' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <BarChart3 className="w-4 h-4" /> Danh sách Đơn đặt
        </button>
        <button
          onClick={() => setTab('emails')}
          className={`px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-1.5 ${
            tab === 'emails' ? 'bg-emerald-700 text-white' : 'bg-white text-slate-700 border'
          }`}
        >
          <Mail className="w-4 h-4" /> Nhật ký Email QR
        </button>
      </div>

      {tab === 'courts' && (
        <div className="space-y-6">
          {/* STEP 1: BRANCHES */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Bước 1: Chọn Chi nhánh (tự động đánh số thứ tự tăng dần)
                </h2>
                <p className="text-xs text-slate-500">
                  Tạo chi nhánh mới sẽ tự sinh <code>Chi nhánh {(branches[branches.length - 1]?.branch_number || 0) + 1}</code>. Địa điểm bên trong có thể thêm ngay hoặc thêm sau.
                </p>
              </div>
              <form onSubmit={handleAddBranch} className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  value={newBranchNote}
                  onChange={(e) => setNewBranchNote(e.target.value)}
                  placeholder="Ghi chú khu vực (tùy chọn, VD: Quận 3)..."
                  className="rounded-xl border border-slate-300 px-3 py-2 text-xs w-64"
                />
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 bg-emerald-700 hover:bg-emerald-800 text-white px-3.5 py-2 rounded-xl text-xs font-semibold"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Thêm Chi nhánh mới</span>
                </button>
              </form>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {branches.map((b) => {
                const isSelected = b.id === selectedBranchId;
                return (
                  <div
                    key={b.id}
                    onClick={() => setSelectedBranchId(b.id)}
                    className={`rounded-xl border p-3.5 cursor-pointer transition ${
                      isSelected
                        ? 'border-emerald-600 bg-emerald-50/70 ring-2 ring-emerald-500/20'
                        : 'border-slate-200 hover:border-emerald-300 bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-bold text-sm text-slate-900">{b.display_name}</div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          {b.locations.length} địa điểm
                        </div>
                      </div>
                      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingBranchId(b.id);
                            setEditBranchNote(b.title_note);
                          }}
                          className="p-1.5 text-slate-500 hover:text-emerald-700 rounded-lg hover:bg-white"
                          title="Sửa ghi chú chi nhánh"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteBranch(b)}
                          className="p-1.5 text-slate-500 hover:text-red-600 rounded-lg hover:bg-white"
                          title="Xóa chi nhánh"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {editingBranchId === b.id && (
                      <div
                        className="mt-2.5 pt-2.5 border-t border-emerald-200 flex items-center gap-1.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="text"
                          value={editBranchNote}
                          onChange={(e) => setEditBranchNote(e.target.value)}
                          placeholder="Mô tả khu vực..."
                          className="flex-1 rounded-lg border border-slate-300 px-2 py-1 text-xs bg-white"
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveBranchNote(b.id)}
                          className="bg-emerald-700 text-white px-2.5 py-1 rounded-lg text-xs font-semibold"
                        >
                          Lưu
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingBranchId(null)}
                          className="p-1 text-slate-500"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* STEP 2: LOCATIONS IN SELECTED BRANCH */}
          {activeBranch && (
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-emerald-700" />
                  <span>Bước 2: Chọn Địa điểm thuộc "{activeBranch.display_name}"</span>
                </h2>
                <p className="text-xs text-slate-500">
                  Chọn một địa điểm có sẵn bên dưới để quản lý các sân con, hoặc thêm địa điểm mới vào chi nhánh này.
                </p>
              </div>

              {activeBranch.locations.length === 0 ? (
                <div className="p-4 rounded-xl bg-amber-50 border border-dashed border-amber-300 text-xs text-amber-900">
                  <strong>{activeBranch.display_name}</strong> hiện chưa có địa điểm nào. Bạn có thể thêm địa điểm ngay ở biểu mẫu bên dưới (hoặc để trống và bổ sung sau).
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {activeBranch.locations.map((loc) => {
                    const isSelectedLoc = loc.id === selectedLocationId;
                    return (
                      <div
                        key={loc.id}
                        onClick={() => setSelectedLocationId(loc.id)}
                        className={`rounded-xl border p-3.5 cursor-pointer transition ${
                          isSelectedLoc
                            ? 'border-emerald-600 bg-emerald-50/70 ring-2 ring-emerald-500/20'
                            : 'border-slate-200 hover:border-emerald-300 bg-slate-50/40'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="font-bold text-sm text-slate-900">{loc.name}</div>
                            <div className="text-xs text-slate-600 mt-0.5">{loc.address}</div>
                            <div className="text-[11px] font-semibold text-emerald-700 mt-1">
                              Đang có {loc.court_count} sân
                            </div>
                          </div>
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              onClick={() => setEditingLocation({ ...loc })}
                              className="p-1.5 text-slate-500 hover:text-emerald-700 rounded-lg hover:bg-white"
                              title="Sửa địa điểm"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteLocation(loc)}
                              className="p-1.5 text-slate-500 hover:text-red-600 rounded-lg hover:bg-white"
                              title="Xóa địa điểm"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {editingLocation && editingLocation.branch_id === activeBranch.id && (
                <form
                  onSubmit={handleSaveLocation}
                  className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 flex flex-wrap items-center gap-2"
                >
                  <span className="text-xs font-bold text-emerald-900">Sửa địa điểm:</span>
                  <input
                    type="text"
                    required
                    value={editingLocation.name}
                    onChange={(e) => setEditingLocation({ ...editingLocation, name: e.target.value })}
                    placeholder="Tên địa điểm"
                    className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs bg-white flex-1 min-w-[180px]"
                  />
                  <input
                    type="text"
                    required
                    value={editingLocation.address}
                    onChange={(e) => setEditingLocation({ ...editingLocation, address: e.target.value })}
                    placeholder="Địa chỉ chi tiết"
                    className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs bg-white flex-[2] min-w-[240px]"
                  />
                  <button
                    type="submit"
                    className="bg-emerald-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold"
                  >
                    Lưu thay đổi
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingLocation(null)}
                    className="text-xs text-slate-600 px-2 py-1.5"
                  >
                    Hủy
                  </button>
                </form>
              )}

              <form onSubmit={handleAddLocation} className="pt-2 border-t border-slate-100 flex flex-wrap gap-2.5">
                <input
                  type="text"
                  required
                  value={newLocationName}
                  onChange={(e) => setNewLocationName(e.target.value)}
                  placeholder="Tên địa điểm mới (VD: Cơ sở Lê Văn Lương)..."
                  className="flex-1 min-w-[200px] rounded-xl border border-slate-300 px-3 py-2 text-xs"
                />
                <input
                  type="text"
                  required
                  value={newLocationAddress}
                  onChange={(e) => setNewLocationAddress(e.target.value)}
                  placeholder="Địa chỉ cụ thể (hiển thị trong Email gửi khách)..."
                  className="flex-[2] min-w-[260px] rounded-xl border border-slate-300 px-3 py-2 text-xs"
                />
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-xl text-xs font-semibold"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Thêm Địa điểm</span>
                </button>
              </form>
            </div>
          )}

          {/* STEP 3: COURTS CRUD FOR SELECTED LOCATION */}
          {activeLocation && (
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Bước 3: Quản lý Sân (Thêm / Sửa / Xóa) tại "{activeLocation.name}"
                </h2>
                <p className="text-xs text-slate-500">
                  {activeBranch?.display_name} • Địa chỉ: {activeLocation.address}
                </p>
              </div>

              {/* Add Court Form */}
              <form onSubmit={handleAddCourt} className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 grid grid-cols-1 md:grid-cols-5 gap-2.5">
                <input
                  type="text"
                  required
                  value={newCourtName}
                  onChange={(e) => setNewCourtName(e.target.value)}
                  placeholder="Tên sân (VD: Sân 01 - VIP)"
                  className="rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white"
                />
                <select
                  value={newCourtType}
                  onChange={(e) => setNewCourtType(e.target.value as 'INDOOR' | 'OUTDOOR')}
                  className="rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white"
                >
                  <option value="INDOOR">Trong nhà (INDOOR)</option>
                  <option value="OUTDOOR">Ngoài trời (OUTDOOR)</option>
                </select>
                <input
                  type="text"
                  value={newCourtSurface}
                  onChange={(e) => setNewCourtSurface(e.target.value)}
                  placeholder="Mặt sân"
                  className="rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white"
                />
                <input
                  type="text"
                  value={newCourtDesc}
                  onChange={(e) => setNewCourtDesc(e.target.value)}
                  placeholder="Mô tả ngắn..."
                  className="rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-1.5 bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-xl text-xs font-semibold"
                >
                  <PlusCircle className="w-4 h-4" /> Thêm sân
                </button>
              </form>

              {/* Edit Court Banner Form */}
              {editingCourt && (
                <form
                  onSubmit={handleSaveCourt}
                  className="p-4 rounded-xl bg-emerald-50 border border-emerald-300 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-900">
                      Chỉnh sửa thông tin sân: {editingCourt.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => setEditingCourt(null)}
                      className="text-xs text-slate-500 hover:text-slate-800"
                    >
                      Đóng
                    </button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-5 gap-2.5">
                    <input
                      type="text"
                      required
                      value={editingCourt.name}
                      onChange={(e) => setEditingCourt({ ...editingCourt, name: e.target.value })}
                      className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs bg-white"
                    />
                    <select
                      value={editingCourt.court_type}
                      onChange={(e) =>
                        setEditingCourt({
                          ...editingCourt,
                          court_type: e.target.value as 'INDOOR' | 'OUTDOOR',
                        })
                      }
                      className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs bg-white"
                    >
                      <option value="INDOOR">Trong nhà (INDOOR)</option>
                      <option value="OUTDOOR">Ngoài trời (OUTDOOR)</option>
                    </select>
                    <input
                      type="text"
                      value={editingCourt.surface}
                      onChange={(e) => setEditingCourt({ ...editingCourt, surface: e.target.value })}
                      placeholder="Mặt sân"
                      className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs bg-white"
                    />
                    <input
                      type="text"
                      value={editingCourt.description}
                      onChange={(e) => setEditingCourt({ ...editingCourt, description: e.target.value })}
                      placeholder="Mô tả"
                      className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs bg-white"
                    />
                    <button
                      type="submit"
                      className="bg-emerald-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold"
                    >
                      Lưu cập nhật
                    </button>
                  </div>
                </form>
              )}

              {/* Courts Table */}
              <div className="rounded-xl border border-slate-200 overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Tên sân</th>
                      <th className="px-4 py-3">Loại sân</th>
                      <th className="px-4 py-3">Mặt sân & Mô tả</th>
                      <th className="px-4 py-3">Trạng thái</th>
                      <th className="px-4 py-3 text-right">Thao tác (Sửa / Xóa)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {locationCourts.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-4 py-6 text-center text-xs text-slate-500">
                          Địa điểm này chưa có sân nào. Hãy thêm sân mới ở khung phía trên!
                        </td>
                      </tr>
                    ) : (
                      locationCourts.map((c) => (
                        <tr key={c.id} className="hover:bg-slate-50/70">
                          <td className="px-4 py-3 font-semibold text-slate-900">{c.name}</td>
                          <td className="px-4 py-3 text-xs font-medium">{c.court_type}</td>
                          <td className="px-4 py-3 text-xs text-slate-600">
                            <div className="font-medium text-slate-700">{c.surface}</div>
                            {c.description && <div className="text-slate-500">{c.description}</div>}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                                c.status === 'ACTIVE'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {c.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right space-x-3 whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => setEditingCourt({ ...c })}
                              className="text-xs font-semibold text-indigo-600 hover:underline"
                            >
                              Sửa
                            </button>
                            <button
                              type="button"
                              onClick={() => handleToggleCourtStatus(c)}
                              className="text-xs font-semibold text-emerald-700 hover:underline"
                            >
                              {c.status === 'ACTIVE' ? 'Bảo trì' : 'Mở lại'}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteCourt(c)}
                              className="text-xs font-semibold text-red-600 hover:underline"
                            >
                              Xóa
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'pricing' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Loại sân</th>
                <th className="px-4 py-3">Ngày áp dụng</th>
                <th className="px-4 py-3">Khung giờ</th>
                <th className="px-4 py-3">Loại giờ</th>
                <th className="px-4 py-3">Giá / giờ (VNĐ)</th>
                <th className="px-4 py-3">Lưu</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rules.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-3 font-semibold">{r.court_type}</td>
                  <td className="px-4 py-3">{r.is_weekend ? 'Cuối tuần (T7-CN)' : 'Ngày thường (T2-T6)'}</td>
                  <td className="px-4 py-3">
                    {String(r.start_hour).padStart(2, '0')}:00 - {String(r.end_hour).padStart(2, '0')}:00
                  </td>
                  <td className="px-4 py-3">{r.is_peak_hour ? 'Cao điểm' : 'Giờ thường'}</td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      value={priceEdits[r.id] || ''}
                      onChange={(e) => setPriceEdits({ ...priceEdits, [r.id]: e.target.value })}
                      className="w-32 rounded-lg border border-slate-300 px-2.5 py-1 text-sm"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleSavePrice(r.id)}
                      className="bg-emerald-700 text-white px-3 py-1 rounded-lg text-xs font-semibold"
                    >
                      Cập nhật
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'bookings' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Khách hàng</th>
                <th className="px-4 py-3">Chi nhánh / Địa điểm / Sân</th>
                <th className="px-4 py-3">Ngày & Giờ</th>
                <th className="px-4 py-3">Tổng tiền</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {bookings.map((b) => (
                <tr key={b.id}>
                  <td className="px-4 py-3 font-mono font-semibold">{b.booking_code}</td>
                  <td className="px-4 py-3">
                    <div>{b.customer_name}</div>
                    <div className="text-xs text-slate-500">{b.customer_email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-900">{b.court_name_snapshot}</div>
                    {(b.branch_name_snapshot || b.location_name_snapshot) && (
                      <div className="text-xs text-emerald-700">
                        {b.branch_name_snapshot} • {b.location_name_snapshot}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {b.play_date} ({String(b.start_hour).padStart(2, '0')}h–{String(b.end_hour).padStart(2, '0')}h)
                  </td>
                  <td className="px-4 py-3 font-semibold text-emerald-700">{formatVND(b.total_amount)}</td>
                  <td className="px-4 py-3">{b.status}</td>
                  <td className="px-4 py-3">
                    {(b.status === 'PENDING_PAYMENT' || b.status === 'PAID') && (
                      <button
                        onClick={() => handleAdminCancel(b.booking_code)}
                        className="text-xs text-red-600 font-semibold hover:underline"
                      >
                        Hủy ngoại lệ
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'emails' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 border-b text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Email nhận</th>
                <th className="px-4 py-3">Tiêu đề</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Retry</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {emails.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-3 font-mono font-semibold">{e.booking_code}</td>
                  <td className="px-4 py-3">{e.recipient_email}</td>
                  <td className="px-4 py-3">{e.subject}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                        e.status === 'SENT' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {e.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">{e.retry_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
