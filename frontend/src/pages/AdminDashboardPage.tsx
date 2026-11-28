import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  Building2,
  Coins,
  Edit3,
  Mail,
  MapPin,
  PlusCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Users,
  X,
} from 'lucide-react';
import { apiRequest, formatDateVN, formatHourRange, formatVND } from '../api/client';
import { Button } from '../components/ui/Button';
import {
  AlertBanner,
  ConfirmDialog,
  EmptyState,
  LoadingSkeleton,
} from '../components/ui/FeedbackStates';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAuth } from '../context/AuthContext';
import {
  AdminStats,
  BookingOrder,
  BranchItem,
  Court,
  FinancialAuditLog,
  LocationItem,
  NotificationLog,
  PaymentTransaction,
  PricingRule,
  ReconciliationCase,
  RefundTransaction,
  User,
  UserRole,
} from '../types';

type AdminTab =
  | 'courts'
  | 'pricing'
  | 'bookings'
  | 'transactions'
  | 'reconciliation'
  | 'refunds'
  | 'audit'
  | 'emails'
  | 'users';

export const AdminDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState<AdminTab>('courts');
  const [loading, setLoading] = useState(true);
  const [partialErrors, setPartialErrors] = useState<string[]>([]);

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState<string>('');
  const [selectedLocationId, setSelectedLocationId] = useState<string>('');
  const [courts, setCourts] = useState<Court[]>([]);
  const [rules, setRules] = useState<PricingRule[]>([]);
  const [bookings, setBookings] = useState<BookingOrder[]>([]);
  const [transactions, setTransactions] = useState<PaymentTransaction[]>([]);
  const [reconciliationCases, setReconciliationCases] = useState<ReconciliationCase[]>([]);
  const [refunds, setRefunds] = useState<RefundTransaction[]>([]);
  const [auditLogs, setAuditLogs] = useState<FinancialAuditLog[]>([]);
  const [emails, setEmails] = useState<NotificationLog[]>([]);
  const [usersList, setUsersList] = useState<User[]>([]);

  // Branch create / edit
  const [newBranchNote, setNewBranchNote] = useState('');
  const [editingBranchId, setEditingBranchId] = useState<string | null>(null);
  const [editBranchNote, setEditBranchNote] = useState('');

  // Location create / edit
  const [newLocationName, setNewLocationName] = useState('');
  const [newLocationAddress, setNewLocationAddress] = useState('');
  const [editingLocation, setEditingLocation] = useState<LocationItem | null>(null);

  // Court create / edit
  const [newCourtName, setNewCourtName] = useState('');
  const [newCourtType, setNewCourtType] = useState<'INDOOR' | 'OUTDOOR'>('INDOOR');
  const [newCourtSurface, setNewCourtSurface] = useState('Acrylic 7 lớp chuẩn USAPA');
  const [newCourtDesc, setNewCourtDesc] = useState('');
  const [editingCourt, setEditingCourt] = useState<Court | null>(null);

  // User create
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserName, setNewUserName] = useState('');
  const [newUserPhone, setNewUserPhone] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [newUserRole, setNewUserRole] = useState<UserRole>('STAFF');

  const [priceEdits, setPriceEdits] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [busyAction, setBusyAction] = useState(false);

  const [confirmState, setConfirmState] = useState<{
    open: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    onConfirm: () => Promise<void>;
  } | null>(null);

  const notifyOk = (msg: string) => {
    setErrorMsg('');
    setMessage(msg);
  };

  const notifyErr = (err: unknown) => {
    setMessage('');
    setErrorMsg(err instanceof Error ? err.message : 'Thao tác thất bại');
  };

  const loadAll = useCallback(async () => {
    setLoading(true);
    const failedParts: string[] = [];
    const results = await Promise.allSettled([
      apiRequest<AdminStats>('/api/bookings/admin/stats'),
      apiRequest<BranchItem[]>('/api/branches'),
      apiRequest<Court[]>('/api/courts?include_inactive=true'),
      apiRequest<PricingRule[]>('/api/pricing-rules'),
      apiRequest<BookingOrder[]>('/api/bookings/admin/list'),
      apiRequest<NotificationLog[]>('/api/notifications/logs'),
      apiRequest<User[]>('/api/auth/users'),
      apiRequest<PaymentTransaction[]>('/api/payments/admin/transactions'),
      apiRequest<ReconciliationCase[]>('/api/payments/admin/reconciliation'),
      apiRequest<RefundTransaction[]>('/api/payments/admin/refunds'),
      apiRequest<FinancialAuditLog[]>('/api/payments/admin/audit-logs'),
    ]);

    const labels = [
      'Thống kê',
      'Chi nhánh',
      'Danh sách sân',
      'Bảng giá',
      'Đơn đặt sân',
      'Email log',
      'Người dùng',
      'Giao dịch',
      'Đối soát',
      'Hoàn tiền',
      'Nhật ký tài chính',
    ];

    results.forEach((res, idx) => {
      if (res.status === 'rejected') {
        failedParts.push(`${labels[idx]}: ${res.reason instanceof Error ? res.reason.message : 'Lỗi'}`);
      }
    });

    if (results[0].status === 'fulfilled') setStats(results[0].value);
    if (results[1].status === 'fulfilled') {
      const br = results[1].value;
      setBranches(br);
      setSelectedBranchId((prev) => (prev && br.some((item) => item.id === prev) ? prev : br[0]?.id || ''));
    }
    if (results[2].status === 'fulfilled') setCourts(results[2].value);
    if (results[3].status === 'fulfilled') {
      const r = results[3].value;
      setRules(r);
      const map: Record<string, string> = {};
      r.forEach((rule) => {
        map[rule.id] = String(rule.price_per_hour);
      });
      setPriceEdits(map);
    }
    if (results[4].status === 'fulfilled') setBookings(results[4].value);
    if (results[5].status === 'fulfilled') setEmails(results[5].value);
    if (results[6].status === 'fulfilled') setUsersList(results[6].value);
    if (results[7].status === 'fulfilled') setTransactions(results[7].value);
    if (results[8].status === 'fulfilled') setReconciliationCases(results[8].value);
    if (results[9].status === 'fulfilled') setRefunds(results[9].value);
    if (results[10].status === 'fulfilled') setAuditLogs(results[10].value);

    setPartialErrors(failedParts);
    setLoading(false);
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
    setSelectedLocationId((prev) =>
      prev && activeBranch.locations.some((loc) => loc.id === prev)
        ? prev
        : activeBranch.locations[0]?.id || ''
    );
  }, [activeBranch]);

  const activeLocation =
    activeBranch?.locations.find((loc) => loc.id === selectedLocationId) || null;
  const locationCourts = courts.filter((c) => c.location_id === selectedLocationId);

  // -------- Branch Handlers --------
  const handleAddBranch = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusyAction(true);
    try {
      const created = await apiRequest<BranchItem>('/api/branches', {
        method: 'POST',
        body: JSON.stringify({ title_note: newBranchNote.trim() }),
      });
      setNewBranchNote('');
      await loadAll();
      setSelectedBranchId(created.id);
      setSelectedLocationId('');
      notifyOk(`Đã tạo ${created.display_name}`);
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const handleSaveBranchNote = async (branchId: string) => {
    setBusyAction(true);
    try {
      await apiRequest(`/api/branches/${branchId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title_note: editBranchNote.trim() }),
      });
      setEditingBranchId(null);
      notifyOk('Đã cập nhật thông tin chi nhánh');
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const askDeleteBranch = (branch: BranchItem) => {
    setConfirmState({
      open: true,
      title: `Xóa "${branch.display_name}"?`,
      description: 'Thao tác này sẽ xóa hoặc ẩn chi nhánh nếu chưa có lịch đặt sắp tới.',
      confirmLabel: 'Xóa chi nhánh',
      onConfirm: async () => {
        const res = await apiRequest<{ message: string }>(`/api/branches/${branch.id}`, {
          method: 'DELETE',
        });
        notifyOk(res.message);
        await loadAll();
      },
    });
  };

  // -------- Location Handlers --------
  const handleAddLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBranchId || !newLocationName.trim() || !newLocationAddress.trim()) return;
    setBusyAction(true);
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
    } finally {
      setBusyAction(false);
    }
  };

  const handleSaveLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingLocation) return;
    setBusyAction(true);
    try {
      await apiRequest(`/api/locations/${editingLocation.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editingLocation.name.trim(),
          address: editingLocation.address.trim(),
        }),
      });
      setEditingLocation(null);
      notifyOk('Đã cập nhật địa điểm');
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const askDeleteLocation = (loc: LocationItem) => {
    setConfirmState({
      open: true,
      title: `Xóa địa điểm "${loc.name}"?`,
      description: 'Địa điểm sẽ bị xóa hoặc ẩn nếu không có đơn đặt sân sắp tới.',
      confirmLabel: 'Xóa địa điểm',
      onConfirm: async () => {
        const res = await apiRequest<{ message: string }>(`/api/locations/${loc.id}`, {
          method: 'DELETE',
        });
        notifyOk(res.message);
        await loadAll();
      },
    });
  };

  // -------- Court Handlers --------
  const handleAddCourt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLocationId || !newCourtName.trim()) return;
    setBusyAction(true);
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
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const handleSaveCourt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingCourt) return;
    setBusyAction(true);
    try {
      await apiRequest(`/api/courts/${editingCourt.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editingCourt.name.trim(),
          court_type: editingCourt.court_type,
          surface: editingCourt.surface.trim(),
          status: editingCourt.status,
          description: editingCourt.description.trim(),
        }),
      });
      setEditingCourt(null);
      notifyOk('Đã cập nhật thông tin sân');
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const handleToggleCourtStatus = async (court: Court) => {
    setBusyAction(true);
    try {
      const nextStatus = court.status === 'ACTIVE' ? 'MAINTENANCE' : 'ACTIVE';
      await apiRequest(`/api/courts/${court.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      });
      notifyOk(`Đã chuyển sân "${court.name}" sang ${nextStatus}`);
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const askDeleteCourt = (court: Court) => {
    setConfirmState({
      open: true,
      title: `Xóa sân "${court.name}"?`,
      description: 'Sân sẽ bị xóa hoặc ẩn nếu không có lịch đặt sắp tới.',
      confirmLabel: 'Xóa sân',
      onConfirm: async () => {
        const res = await apiRequest<{ message: string }>(`/api/courts/${court.id}`, {
          method: 'DELETE',
        });
        notifyOk(res.message);
        await loadAll();
      },
    });
  };

  const handleSavePrice = async (ruleId: string) => {
    const val = Number(priceEdits[ruleId]);
    if (!val || val <= 0) {
      notifyErr(new Error('Giá mỗi giờ phải lớn hơn 0'));
      return;
    }
    setBusyAction(true);
    try {
      await apiRequest(`/api/pricing-rules/${ruleId}`, {
        method: 'PUT',
        body: JSON.stringify({ price_per_hour: val }),
      });
      notifyOk('Đã cập nhật bảng giá');
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  const askAdminCancel = (bookingCode: string) => {
    setConfirmState({
      open: true,
      title: `Hủy đơn ${bookingCode}?`,
      description: 'Đơn đặt sân sẽ chuyển sang trạng thái CANCELLED và giải phóng khung giờ.',
      confirmLabel: 'Xác nhận hủy đơn',
      onConfirm: async () => {
        await apiRequest(`/api/bookings/admin/${bookingCode}/cancel`, {
          method: 'POST',
          body: JSON.stringify({ reason: 'Admin hủy đơn ngoại lệ' }),
        });
        notifyOk(`Đã hủy đơn ${bookingCode}`);
        await loadAll();
      },
    });
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusyAction(true);
    try {
      await apiRequest<User>('/api/auth/users', {
        method: 'POST',
        body: JSON.stringify({
          email: newUserEmail.trim(),
          full_name: newUserName.trim(),
          phone: newUserPhone.trim(),
          password: newUserPassword,
          role: newUserRole,
        }),
      });
      setNewUserEmail('');
      setNewUserName('');
      setNewUserPhone('');
      setNewUserPassword('');
      notifyOk('Đã tạo tài khoản mới');
      await loadAll();
    } catch (err) {
      notifyErr(err);
    } finally {
      setBusyAction(false);
    }
  };

  if (!user || user.role !== 'ADMIN') {
    return (
      <div className="max-w-xl mx-auto px-4 py-12">
        <AlertBanner tone="error" title="Không có quyền truy cập">
          Chỉ tài khoản Quản trị viên (ADMIN) mới được truy cập bảng điều khiển quản trị.
        </AlertBanner>
      </div>
    );
  }

  const navGroups: Array<{
    group: string;
    items: Array<{ key: AdminTab; label: string; icon: React.ComponentType<{ className?: string }> }>;
  }> = [
    {
      group: 'Cơ sở & Hạ tầng',
      items: [
        { key: 'courts', label: 'Chi nhánh & Sân', icon: Building2 },
        { key: 'pricing', label: 'Bảng giá theo giờ', icon: Coins },
      ],
    },
    {
      group: 'Vận hành đặt sân',
      items: [
        { key: 'bookings', label: `Đơn đặt (${bookings.length})`, icon: BarChart3 },
        { key: 'emails', label: `Email Log (${emails.length})`, icon: Mail },
      ],
    },
    {
      group: 'Tài chính & Hoàn tiền',
      items: [
        { key: 'transactions', label: `Giao dịch (${transactions.length})`, icon: Coins },
        { key: 'reconciliation', label: `Đối soát (${reconciliationCases.length})`, icon: ShieldCheck },
        { key: 'refunds', label: `Hoàn tiền (${refunds.length})`, icon: RefreshCw },
        { key: 'audit', label: `Nhật ký tài chính (${auditLogs.length})`, icon: BarChart3 },
      ],
    },
    {
      group: 'Hệ thống',
      items: [{ key: 'users', label: `Tài khoản (${usersList.length})`, icon: Users }],
    },
  ];

  const activeNavLabel =
    navGroups.flatMap((g) => g.items).find((item) => item.key === tab)?.label || 'Quản trị';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        {/* Responsive Operational Sidebar */}
        <aside
          aria-label="Danh mục quản trị"
          className="w-full lg:w-64 shrink-0 bg-court text-white rounded-2xl border border-[#23483D] p-4 space-y-5 lg:sticky lg:top-20"
        >
          <div className="pb-3 border-b border-[#264C41]">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-ball-lime">
              Admin Console
            </div>
            <div className="font-display text-base font-extrabold mt-0.5 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-ball-lime shrink-0" aria-hidden="true" />
              <span>Điều hành câu lạc bộ</span>
            </div>
          </div>

          <nav className="space-y-4" role="tablist" aria-label="Danh mục quản trị">
            {navGroups.map((grp) => (
              <div key={grp.group} className="space-y-1.5">
                <div className="px-2.5 text-[10px] font-bold uppercase tracking-[0.16em] text-[#9DB3A6]">
                  {grp.group}
                </div>
                <div className="flex lg:flex-col gap-1.5 overflow-x-auto pb-1 lg:pb-0">
                  {grp.items.map(({ key, label, icon: Icon }) => {
                    const active = tab === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        onClick={() => setTab(key)}
                        className={`inline-flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs sm:text-sm font-semibold whitespace-nowrap transition-colors text-left lg:w-full ${
                          active
                            ? 'bg-ball-lime text-court font-bold'
                            : 'text-[#D6E1DA] hover:bg-court-soft hover:text-white'
                        }`}
                      >
                        <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
                        <span>{label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        {/* Main Operational Workspace */}
        <div className="flex-1 min-w-0 w-full space-y-6">
          {/* Topbar with Breadcrumb & Refresh */}
          <header className="bg-white rounded-2xl border border-[#CFCFC4] px-5 py-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-xs text-court-muted font-medium">
                Quản trị <span className="mx-1">/</span>{' '}
                <span className="text-court font-semibold">{activeNavLabel}</span>
              </div>
              <h1 className="font-display text-xl sm:text-2xl font-extrabold text-charcoal mt-0.5">
                {activeNavLabel}
              </h1>
            </div>
            <Button type="button" variant="primary" size="md" onClick={loadAll} loading={loading}>
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              Làm mới dữ liệu
            </Button>
          </header>

          {/* KPI Summary Cards */}
          {stats && (
            <section aria-label="Thống kê tổng quan" className="grid grid-cols-2 xl:grid-cols-4 gap-4">
              <div className="bg-white rounded-2xl border border-[#CFCFC4] p-4">
                <div className="text-xs font-semibold text-court-muted flex items-center gap-1.5">
                  <BarChart3 className="w-4 h-4 text-court" aria-hidden="true" /> Tổng đơn đặt
                </div>
                <div className="font-mono text-2xl font-bold text-charcoal mt-1 tabular-nums">
                  {stats.total_bookings}
                </div>
                <div className="text-[11px] text-court-muted mt-1">
                  Sân hoạt động: <strong className="text-charcoal">{stats.active_courts}</strong>
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-[#CFCFC4] p-4">
                <div className="text-xs font-semibold text-court-muted">Đơn đã thanh toán</div>
                <div className="font-mono text-2xl font-bold text-[#14532D] mt-1 tabular-nums">
                  {stats.paid_bookings}
                </div>
                <div className="text-[11px] text-court-muted mt-1">
                  Hủy / Hết hạn:{' '}
                  <strong className="text-charcoal">{stats.cancelled_or_expired}</strong>
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-[#CFCFC4] p-4">
                <div className="text-xs font-semibold text-court-muted">Chờ thanh toán</div>
                <div className="font-mono text-2xl font-bold text-amber-800 mt-1 tabular-nums">
                  {stats.pending_bookings}
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-[#CFCFC4] p-4">
                <div className="text-xs font-semibold text-court-muted">Doanh thu ghi nhận</div>
                <div className="font-mono text-xl sm:text-2xl font-bold text-court mt-1 tabular-nums">
                  {formatVND(stats.total_revenue)}
                </div>
              </div>
            </section>
          )}

          {partialErrors.length > 0 && (
            <AlertBanner tone="warning" title="Một số dữ liệu chưa tải được" onRetry={loadAll}>
              {partialErrors.join(' • ')}
            </AlertBanner>
          )}

          {message && <AlertBanner tone="success">{message}</AlertBanner>}
          {errorMsg && <AlertBanner tone="error">{errorMsg}</AlertBanner>}

          {loading && branches.length === 0 ? (
            <LoadingSkeleton rows={4} />
          ) : (
            <>
      {/* TAB 1: BRANCHES -> LOCATIONS -> COURTS */}
      {tab === 'courts' && (
        <div className="space-y-6">
          {/* Step 1: Branches */}
          <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-bold text-charcoal flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-court" aria-hidden="true" />
                  <span>Bước 1: Quản lý Chi nhánh (Đánh số tự động)</span>
                </h2>
                <p className="text-xs text-court-muted mt-0.5">
                  Tạo mới tự động tăng số Chi nhánh 1, 2, 3... Bấm chọn chi nhánh để quản lý địa điểm bên dưới.
                </p>
              </div>
              <form onSubmit={handleAddBranch} className="flex flex-wrap items-center gap-2">
                <label htmlFor="new-branch-note" className="sr-only">
                  Tên gợi nhớ chi nhánh
                </label>
                <input
                  id="new-branch-note"
                  value={newBranchNote}
                  onChange={(e) => setNewBranchNote(e.target.value)}
                  placeholder="Tên gợi nhớ (VD: Khu vực Bình Thạnh)"
                  className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm w-64 focus:ring-2 focus:ring-court focus:outline-none"
                />
                <Button type="submit" variant="primary" size="md" loading={busyAction}>
                  <PlusCircle className="w-4 h-4" aria-hidden="true" /> Thêm chi nhánh
                </Button>
              </form>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {branches.map((b) => {
                const isSelected = b.id === selectedBranchId;
                return (
                  <div
                    key={b.id}
                    className={`rounded-xl border p-4 transition-colors ${
                      isSelected
                        ? 'border-court bg-[#F1F5F2] ring-2 ring-court/20'
                        : 'border-[#D4D6CD] bg-white'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedBranchId(b.id)}
                        aria-pressed={isSelected}
                        className="text-left flex-1 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-court"
                      >
                        <div className="text-xs font-bold text-court uppercase">
                          Chi nhánh {b.branch_number}
                        </div>
                        <div className="font-bold text-charcoal text-sm mt-0.5">
                          {b.title_note || 'Chưa đặt tên gợi nhớ'}
                        </div>
                        <div className="text-xs text-court-muted mt-1">
                          {b.locations.length} địa điểm
                        </div>
                      </button>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingBranchId(b.id);
                            setEditBranchNote(b.title_note);
                          }}
                          className="p-1.5 rounded-lg hover:bg-white text-court-muted hover:text-court"
                          aria-label={`Sửa ${b.display_name}`}
                        >
                          <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          onClick={() => askDeleteBranch(b)}
                          className="p-1.5 rounded-lg hover:bg-red-50 text-court-muted hover:text-[#B93829]"
                          aria-label={`Xóa ${b.display_name}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
                      </div>
                    </div>

                    {editingBranchId === b.id && (
                      <div className="mt-3 pt-3 border-t border-[#D4D6CD] flex gap-1.5">
                        <label htmlFor={`edit-branch-${b.id}`} className="sr-only">
                          Tên gợi nhớ mới
                        </label>
                        <input
                          id={`edit-branch-${b.id}`}
                          value={editBranchNote}
                          onChange={(e) => setEditBranchNote(e.target.value)}
                          className="flex-1 rounded-lg border border-[#D4D6CD] px-2.5 py-1 text-xs bg-white"
                          placeholder="Tên gợi nhớ..."
                        />
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => handleSaveBranchNote(b.id)}
                          disabled={busyAction}
                        >
                          Lưu
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => setEditingBranchId(null)}
                        >
                          Hủy
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Step 2: Locations */}
          {activeBranch && (
            <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 space-y-4">
              <div>
                <h2 className="font-bold text-charcoal flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-court" aria-hidden="true" />
                  <span>Bước 2: Địa điểm thuộc {activeBranch.display_name}</span>
                </h2>
                <p className="text-xs text-court-muted mt-0.5">
                  Mỗi địa điểm chứa tên cơ sở và địa chỉ thực tế (được đính kèm trong vé QR gửi khách).
                </p>
              </div>

              <form onSubmit={handleAddLocation} className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label htmlFor="new-loc-name" className="sr-only">
                    Tên địa điểm
                  </label>
                  <input
                    id="new-loc-name"
                    required
                    value={newLocationName}
                    onChange={(e) => setNewLocationName(e.target.value)}
                    placeholder="Tên địa điểm (VD: Cơ sở Thảo Điền)"
                    className="w-full rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
                  />
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="new-loc-address" className="sr-only">
                    Địa chỉ
                  </label>
                  <input
                    id="new-loc-address"
                    required
                    value={newLocationAddress}
                    onChange={(e) => setNewLocationAddress(e.target.value)}
                    placeholder="Địa chỉ (VD: 45 Quốc Hương, TP. Thủ Đức)"
                    className="w-full rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
                  />
                </div>
                <Button type="submit" variant="primary" size="md" loading={busyAction}>
                  <PlusCircle className="w-4 h-4" aria-hidden="true" /> Thêm địa điểm
                </Button>
              </form>

              {activeBranch.locations.length === 0 ? (
                <EmptyState title="Chi nhánh này chưa có địa điểm nào" />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {activeBranch.locations.map((loc) => {
                    const isSelected = loc.id === selectedLocationId;
                    return (
                      <div
                        key={loc.id}
                        className={`rounded-xl border p-4 transition-colors ${
                          isSelected
                            ? 'border-court bg-[#F1F5F2] ring-2 ring-court/20'
                            : 'border-[#D4D6CD] bg-white'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedLocationId(loc.id)}
                            aria-pressed={isSelected}
                            className="text-left flex-1 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-court"
                          >
                            <div className="font-bold text-charcoal text-sm">{loc.name}</div>
                            <div className="text-xs text-court-muted mt-0.5">{loc.address}</div>
                            <div className="text-xs text-court font-semibold mt-1">
                              {loc.court_count} sân
                            </div>
                          </button>
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              type="button"
                              onClick={() => setEditingLocation(loc)}
                              className="p-1.5 rounded-lg hover:bg-white text-court-muted hover:text-court"
                              aria-label={`Sửa địa điểm ${loc.name}`}
                            >
                              <Edit3 className="w-3.5 h-3.5" aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              onClick={() => askDeleteLocation(loc)}
                              className="p-1.5 rounded-lg hover:bg-red-50 text-court-muted hover:text-[#B93829]"
                              aria-label={`Xóa địa điểm ${loc.name}`}
                            >
                              <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                            </button>
                          </div>
                        </div>

                        {editingLocation?.id === loc.id && (
                          <form
                            onSubmit={handleSaveLocation}
                            className="mt-3 pt-3 border-t border-[#D4D6CD] space-y-2"
                          >
                            <input
                              required
                              aria-label="Tên địa điểm"
                              value={editingLocation.name}
                              onChange={(e) =>
                                setEditingLocation({ ...editingLocation, name: e.target.value })
                              }
                              className="w-full rounded-lg border border-[#D4D6CD] px-2.5 py-1.5 text-xs bg-white"
                            />
                            <input
                              required
                              aria-label="Địa chỉ địa điểm"
                              value={editingLocation.address}
                              onChange={(e) =>
                                setEditingLocation({ ...editingLocation, address: e.target.value })
                              }
                              className="w-full rounded-lg border border-[#D4D6CD] px-2.5 py-1.5 text-xs bg-white"
                            />
                            <div className="flex gap-2">
                              <Button type="submit" size="sm" disabled={busyAction}>
                                Lưu địa điểm
                              </Button>
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                onClick={() => setEditingLocation(null)}
                              >
                                Hủy
                              </Button>
                            </div>
                          </form>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* Step 3: Courts */}
          {activeLocation && (
            <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5 space-y-4">
              <div>
                <h2 className="font-bold text-charcoal">
                  Bước 3: Danh sách sân tại {activeLocation.name} ({activeBranch?.display_name})
                </h2>
                <p className="text-xs text-court-muted">{activeLocation.address}</p>
              </div>

              <form onSubmit={handleAddCourt} className="grid grid-cols-1 md:grid-cols-5 gap-3">
                <input
                  required
                  aria-label="Tên sân mới"
                  value={newCourtName}
                  onChange={(e) => setNewCourtName(e.target.value)}
                  placeholder="Tên sân (VD: Sân 05)"
                  className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
                />
                <select
                  aria-label="Loại sân"
                  value={newCourtType}
                  onChange={(e) => setNewCourtType(e.target.value as 'INDOOR' | 'OUTDOOR')}
                  className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm bg-white"
                >
                  <option value="INDOOR">INDOOR (Trong nhà)</option>
                  <option value="OUTDOOR">OUTDOOR (Ngoài trời)</option>
                </select>
                <input
                  aria-label="Bề mặt sân"
                  value={newCourtSurface}
                  onChange={(e) => setNewCourtSurface(e.target.value)}
                  placeholder="Bề mặt sân"
                  className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
                />
                <input
                  aria-label="Mô tả sân"
                  value={newCourtDesc}
                  onChange={(e) => setNewCourtDesc(e.target.value)}
                  placeholder="Mô tả thêm"
                  className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
                />
                <Button type="submit" variant="primary" size="md" loading={busyAction}>
                  <PlusCircle className="w-4 h-4" aria-hidden="true" /> Thêm sân
                </Button>
              </form>

              {locationCourts.length === 0 ? (
                <EmptyState title="Địa điểm này chưa có sân nào" />
              ) : (
                <div className="space-y-3">
                  {locationCourts.map((c) => (
                    <div
                      key={c.id}
                      className="rounded-xl border border-[#D4D6CD] p-4 flex flex-col gap-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-charcoal">{c.name}</span>
                            <StatusBadge status={c.court_type} />
                            <StatusBadge status={c.status} />
                          </div>
                          <div className="text-xs text-court-muted mt-1">
                            {c.surface} {c.description ? `• ${c.description}` : ''}
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleToggleCourtStatus(c)}
                            disabled={busyAction}
                          >
                            {c.status === 'ACTIVE' ? 'Bảo trì' : 'Kích hoạt'}
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => setEditingCourt(c)}
                          >
                            <Edit3 className="w-3.5 h-3.5" aria-hidden="true" /> Sửa
                          </Button>
                          <Button
                            type="button"
                            variant="danger"
                            size="sm"
                            onClick={() => askDeleteCourt(c)}
                          >
                            <Trash2 className="w-3.5 h-3.5" aria-hidden="true" /> Xóa
                          </Button>
                        </div>
                      </div>

                      {editingCourt?.id === c.id && (
                        <form
                          onSubmit={handleSaveCourt}
                          className="pt-3 border-t border-[#ECEBE2] grid grid-cols-1 md:grid-cols-5 gap-2"
                        >
                          <input
                            required
                            aria-label="Tên sân"
                            value={editingCourt.name}
                            onChange={(e) =>
                              setEditingCourt({ ...editingCourt, name: e.target.value })
                            }
                            className="rounded-lg border border-[#D4D6CD] px-3 py-1.5 text-sm"
                          />
                          <select
                            aria-label="Loại sân"
                            value={editingCourt.court_type}
                            onChange={(e) =>
                              setEditingCourt({
                                ...editingCourt,
                                court_type: e.target.value as 'INDOOR' | 'OUTDOOR',
                              })
                            }
                            className="rounded-lg border border-[#D4D6CD] px-3 py-1.5 text-sm bg-white"
                          >
                            <option value="INDOOR">INDOOR</option>
                            <option value="OUTDOOR">OUTDOOR</option>
                          </select>
                          <input
                            aria-label="Bề mặt sân"
                            value={editingCourt.surface}
                            onChange={(e) =>
                              setEditingCourt({ ...editingCourt, surface: e.target.value })
                            }
                            className="rounded-lg border border-[#D4D6CD] px-3 py-1.5 text-sm"
                          />
                          <input
                            aria-label="Mô tả sân"
                            value={editingCourt.description}
                            onChange={(e) =>
                              setEditingCourt({ ...editingCourt, description: e.target.value })
                            }
                            className="rounded-lg border border-[#D4D6CD] px-3 py-1.5 text-sm"
                          />
                          <div className="flex gap-1.5">
                            <Button type="submit" size="sm" className="flex-1" disabled={busyAction}>
                              Lưu
                            </Button>
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              onClick={() => setEditingCourt(null)}
                              aria-label="Đóng chỉnh sửa"
                            >
                              <X className="w-4 h-4" />
                            </Button>
                          </div>
                        </form>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {/* TAB 2: PRICING */}
      {tab === 'pricing' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
              <tr>
                <th className="px-4 py-3">Loại sân</th>
                <th className="px-4 py-3">Ngày áp dụng</th>
                <th className="px-4 py-3">Khung giờ</th>
                <th className="px-4 py-3">Loại giờ</th>
                <th className="px-4 py-3">Giá mỗi giờ (VNĐ)</th>
                <th className="px-4 py-3">Lưu</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {rules.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-3">
                    <StatusBadge status={r.court_type} />
                  </td>
                  <td className="px-4 py-3">{r.is_weekend ? 'Cuối tuần (T7–CN)' : 'Ngày thường (T2–T6)'}</td>
                  <td className="px-4 py-3 font-mono tabular-nums">
                    {formatHourRange(r.start_hour, r.end_hour)}
                  </td>
                  <td className="px-4 py-3">{r.is_peak_hour ? 'Cao điểm' : 'Bình thường'}</td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      min={1000}
                      max={5000000}
                      step={1000}
                      aria-label={`Giá mỗi giờ cho ${r.court_type} ${r.start_hour}-${r.end_hour}`}
                      value={priceEdits[r.id] || ''}
                      onChange={(e) => setPriceEdits({ ...priceEdits, [r.id]: e.target.value })}
                      className="w-36 rounded-lg border border-[#D4D6CD] px-2.5 py-1.5 text-sm font-mono tabular-nums"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      onClick={() => handleSavePrice(r.id)}
                      disabled={busyAction}
                    >
                      Cập nhật
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* TAB 3: BOOKINGS */}
      {tab === 'bookings' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          {bookings.length === 0 ? (
            <div className="p-6">
              <EmptyState title="Chưa có đơn đặt sân nào" />
            </div>
          ) : (
            <table className="w-full text-sm text-left">
              <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
                <tr>
                  <th className="px-4 py-3">Mã đơn</th>
                  <th className="px-4 py-3">Khách hàng</th>
                  <th className="px-4 py-3">Chi nhánh &amp; Sân</th>
                  <th className="px-4 py-3">Ngày &amp; Giờ</th>
                  <th className="px-4 py-3">Tổng tiền</th>
                  <th className="px-4 py-3">Trạng thái</th>
                  <th className="px-4 py-3">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ECEBE2]">
                {bookings.map((b) => (
                  <tr key={b.id} className="hover:bg-warm-white/60">
                    <td className="px-4 py-3 font-mono font-bold whitespace-nowrap">{b.booking_code}</td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-charcoal">{b.customer_name}</div>
                      <div className="text-xs text-court-muted">{b.customer_email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold">{b.court_name_snapshot}</div>
                      {b.branch_name_snapshot && (
                        <div className="text-xs text-court-muted">
                          {b.branch_name_snapshot} • {b.location_name_snapshot}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 tabular-nums whitespace-nowrap">
                      {formatDateVN(b.play_date)} ({formatHourRange(b.start_hour, b.end_hour)})
                    </td>
                    <td className="px-4 py-3 font-bold text-court tabular-nums whitespace-nowrap">
                      {formatVND(b.total_amount)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={b.status} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {(b.status === 'PENDING_PAYMENT' || b.status === 'PAID') && (
                        <Button
                          type="button"
                          variant="danger"
                          size="sm"
                          onClick={() => askAdminCancel(b.booking_code)}
                        >
                          Hủy đơn
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* TAB 4: EMAILS */}
      {tab === 'emails' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          {emails.length === 0 ? (
            <div className="p-6">
              <EmptyState title="Chưa có nhật ký gửi email nào" />
            </div>
          ) : (
            <table className="w-full text-sm text-left">
              <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
                <tr>
                  <th className="px-4 py-3">Mã đơn</th>
                  <th className="px-4 py-3">Email nhận</th>
                  <th className="px-4 py-3">Tiêu đề</th>
                  <th className="px-4 py-3">Trạng thái</th>
                  <th className="px-4 py-3">Retry</th>
                  <th className="px-4 py-3">Lỗi (nếu có)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ECEBE2]">
                {emails.map((em) => (
                  <tr key={em.id}>
                    <td className="px-4 py-3 font-mono font-bold whitespace-nowrap">{em.booking_code}</td>
                    <td className="px-4 py-3">{em.recipient_email}</td>
                    <td className="px-4 py-3">{em.subject}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={em.status} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{em.retry_count}</td>
                    <td className="px-4 py-3 text-xs text-[#B93829]">{em.error_message || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* TAB 5: USERS (ADMIN) */}
      {tab === 'users' && (
        <div className="space-y-4">
          <section className="bg-white rounded-2xl border border-[#D4D6CD] p-5">
            <h2 className="font-bold text-charcoal mb-3">Tạo tài khoản Nhân viên / Quản trị</h2>
            <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-6 gap-3">
              <input
                required
                type="email"
                aria-label="Email tài khoản"
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
                placeholder="Email"
                className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
              />
              <input
                required
                minLength={2}
                aria-label="Họ tên"
                value={newUserName}
                onChange={(e) => setNewUserName(e.target.value)}
                placeholder="Họ và tên"
                className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
              />
              <input
                aria-label="Số điện thoại"
                value={newUserPhone}
                onChange={(e) => setNewUserPhone(e.target.value)}
                placeholder="Số điện thoại"
                className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
              />
              <input
                required
                minLength={6}
                type="password"
                aria-label="Mật khẩu"
                value={newUserPassword}
                onChange={(e) => setNewUserPassword(e.target.value)}
                placeholder="Mật khẩu (>=6 ký tự)"
                className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm"
              />
              <select
                aria-label="Vai trò"
                value={newUserRole}
                onChange={(e) => setNewUserRole(e.target.value as UserRole)}
                className="rounded-lg border border-[#D4D6CD] px-3 py-2 text-sm bg-white"
              >
                <option value="STAFF">STAFF</option>
                <option value="ADMIN">ADMIN</option>
                <option value="CUSTOMER">CUSTOMER</option>
              </select>
              <Button type="submit" variant="primary" size="md" loading={busyAction}>
                <PlusCircle className="w-4 h-4" aria-hidden="true" /> Tạo mới
              </Button>
            </form>
          </section>

          <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
                <tr>
                  <th className="px-4 py-3">Họ và tên</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Số điện thoại</th>
                  <th className="px-4 py-3">Vai trò</th>
                  <th className="px-4 py-3">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ECEBE2]">
                {usersList.map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3 font-semibold text-charcoal">{u.full_name}</td>
                    <td className="px-4 py-3">{u.email}</td>
                    <td className="px-4 py-3 tabular-nums">{u.phone || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs font-bold text-court">{u.role}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={u.is_active ? 'ACTIVE' : 'CANCELLED'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
      {tab === 'transactions' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Cần thu</th>
                <th className="px-4 py-3">Đã nhận</th>
                <th className="px-4 py-3">Đã hoàn</th>
                <th className="px-4 py-3">Đối soát</th>
                <th className="px-4 py-3">Chế độ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {transactions.map((tx) => (
                <tr key={tx.id}>
                  <td className="px-4 py-3 font-mono font-bold text-charcoal">{tx.booking_code}</td>
                  <td className="px-4 py-3"><StatusBadge status={tx.status} /></td>
                  <td className="px-4 py-3 font-mono">{formatVND(tx.expected_amount || tx.amount)}</td>
                  <td className="px-4 py-3 font-mono text-court font-semibold">{formatVND(tx.received_amount)}</td>
                  <td className="px-4 py-3 font-mono text-terracotta">{formatVND(tx.refunded_amount)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{tx.reconciliation_status || 'NONE'}</td>
                  <td className="px-4 py-3 font-mono text-xs">{tx.payment_mode}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'reconciliation' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
              <tr>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Loại sai lệch</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3">Chênh lệch</th>
                <th className="px-4 py-3">Ghi chú</th>
                <th className="px-4 py-3 text-right">Xử lý</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {reconciliationCases.map((rc) => (
                <tr key={rc.id}>
                  <td className="px-4 py-3 font-mono font-bold text-charcoal">{rc.booking_code}</td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold">{rc.case_type}</td>
                  <td className="px-4 py-3 font-mono text-xs">{rc.status}</td>
                  <td className="px-4 py-3 font-mono">{formatVND(rc.discrepancy_amount)}</td>
                  <td className="px-4 py-3 text-xs text-court-muted max-w-xs">{rc.resolution_note || '—'}</td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    {rc.status === 'OPEN' && (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={busyAction}
                        onClick={async () => {
                          setBusyAction(true);
                          try {
                            await apiRequest(`/api/payments/admin/reconciliation/${rc.id}`, {
                              method: 'POST',
                              body: JSON.stringify({
                                status: 'IN_REVIEW',
                                resolution_note: 'Admin đang kiểm tra hồ sơ đối soát',
                              }),
                            });
                            notifyOk(`Đã chuyển ${rc.booking_code} sang IN_REVIEW`);
                            await loadAll();
                          } catch (err) {
                            notifyErr(err);
                          } finally {
                            setBusyAction(false);
                          }
                        }}
                      >
                        Đánh dấu Đang xử lý
                      </Button>
                    )}
                    {rc.status !== 'RESOLVED' && (
                      <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        disabled={busyAction}
                        onClick={async () => {
                          setBusyAction(true);
                          try {
                            await apiRequest(`/api/payments/admin/reconciliation/${rc.id}`, {
                              method: 'POST',
                              body: JSON.stringify({
                                status: 'RESOLVED',
                                resolution_action: 'MANUAL_WRITE_OFF',
                                resolution_note: 'Admin đã đối soát thủ công và xác nhận xử lý xong',
                              }),
                            });
                            notifyOk(`Đã đóng đối soát ${rc.booking_code}`);
                            await loadAll();
                          } catch (err) {
                            notifyErr(err);
                          } finally {
                            setBusyAction(false);
                          }
                        }}
                      >
                        Đóng đối soát
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'refunds' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
              <tr>
                <th className="px-4 py-3">Mã hoàn tiền</th>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Chính sách</th>
                <th className="px-4 py-3">Số tiền</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {refunds.map((rf) => (
                <tr key={rf.id}>
                  <td className="px-4 py-3 font-mono font-bold text-charcoal">{rf.refund_code}</td>
                  <td className="px-4 py-3 font-mono">{rf.booking_code}</td>
                  <td className="px-4 py-3 font-mono text-xs">{rf.policy_tier} ({rf.policy_percent}%)</td>
                  <td className="px-4 py-3 font-mono font-bold text-court">{formatVND(rf.requested_amount)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{rf.status}</td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    {rf.status === 'REQUESTED' && (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          variant="primary"
                          disabled={busyAction}
                          onClick={async () => {
                            setBusyAction(true);
                            try {
                              await apiRequest(`/api/payments/admin/refunds/${rf.id}/approve`, {
                                method: 'POST',
                                body: JSON.stringify({ note: 'Admin phê duyệt hoàn tiền' }),
                              });
                              notifyOk(`Đã duyệt ${rf.refund_code}`);
                              await loadAll();
                            } catch (err) {
                              notifyErr(err);
                            } finally {
                              setBusyAction(false);
                            }
                          }}
                        >
                          Duyệt
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          disabled={busyAction}
                          onClick={async () => {
                            setBusyAction(true);
                            try {
                              await apiRequest(`/api/payments/admin/refunds/${rf.id}/reject`, {
                                method: 'POST',
                                body: JSON.stringify({ rejection_reason: 'Không đủ điều kiện hoàn tiền' }),
                              });
                              notifyOk(`Đã từ chối ${rf.refund_code}`);
                              await loadAll();
                            } catch (err) {
                              notifyErr(err);
                            } finally {
                              setBusyAction(false);
                            }
                          }}
                        >
                          Từ chối
                        </Button>
                      </>
                    )}
                    {(rf.status === 'APPROVED' || rf.status === 'FAILED') && (
                      <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        disabled={busyAction}
                        onClick={async () => {
                          setBusyAction(true);
                          try {
                            await apiRequest(`/api/payments/admin/refunds/${rf.id}/execute`, {
                              method: 'POST',
                              body: JSON.stringify({ outcome: 'SUCCEEDED' }),
                            });
                            notifyOk(`Đã thực thi hoàn tiền ${rf.refund_code}`);
                            await loadAll();
                          } catch (err) {
                            notifyErr(err);
                          } finally {
                            setBusyAction(false);
                          }
                        }}
                      >
                        {rf.status === 'FAILED' ? 'Thử lại hoàn tiền' : 'Thực thi hoàn tiền'}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {tab === 'audit' && (
        <section className="bg-white rounded-2xl border border-[#D4D6CD] overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-warm-white border-b border-[#D4D6CD] text-xs uppercase text-court-muted">
              <tr>
                <th className="px-4 py-3">Thời gian</th>
                <th className="px-4 py-3">Mã đơn</th>
                <th className="px-4 py-3">Hành động</th>
                <th className="px-4 py-3">Chuyển trạng thái</th>
                <th className="px-4 py-3">Số tiền</th>
                <th className="px-4 py-3">Người thực hiện</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ECEBE2]">
              {auditLogs.map((al) => (
                <tr key={al.id}>
                  <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">{new Date(al.created_at).toLocaleString('vi-VN')}</td>
                  <td className="px-4 py-3 font-mono font-bold text-charcoal">{al.booking_code}</td>
                  <td className="px-4 py-3 font-mono text-xs">{al.action}</td>
                  <td className="px-4 py-3 font-mono text-xs">{al.previous_state || '—'} → {al.new_state || '—'}</td>
                  <td className="px-4 py-3 font-mono">{formatVND(al.amount_vnd)}</td>
                  <td className="px-4 py-3 text-xs">{al.actor} ({al.actor_role})</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

        </>
      )}
        </div>
      </div>

      {confirmState && (
        <ConfirmDialog
          open={confirmState.open}
          title={confirmState.title}
          description={confirmState.description}
          confirmLabel={confirmState.confirmLabel}
          loading={busyAction}
          onConfirm={async () => {
            setBusyAction(true);
            try {
              await confirmState.onConfirm();
              setConfirmState(null);
            } catch (err) {
              setConfirmState(null);
              notifyErr(err);
            } finally {
              setBusyAction(false);
            }
          }}
          onCancel={() => setConfirmState(null)}
        />
      )}
    </div>
  );
};
