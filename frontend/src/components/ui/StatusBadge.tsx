import React from 'react';
import { AlertTriangle, Ban, CheckCircle2, Clock, Wrench } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
}

const STATUS_MAP: Record<
  string,
  { label: string; classes: string; icon?: React.ReactNode }
> = {
  PENDING_PAYMENT: {
    label: 'Chờ thanh toán',
    classes: 'bg-amber-50 text-amber-900 border-amber-300',
    icon: <Clock className="w-3 h-3" aria-hidden="true" />,
  },
  PENDING: {
    label: 'Đang chờ',
    classes: 'bg-amber-50 text-amber-900 border-amber-300',
    icon: <Clock className="w-3 h-3" aria-hidden="true" />,
  },
  PAID: {
    label: 'Đã thanh toán',
    classes: 'bg-[#E6F4EC] text-[#14532D] border-[#A7D7BA]',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  SUCCEEDED: {
    label: 'Thành công',
    classes: 'bg-[#E6F4EC] text-[#14532D] border-[#A7D7BA]',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  VALID: {
    label: 'Vé hợp lệ',
    classes: 'bg-[#E6F4EC] text-[#14532D] border-[#A7D7BA]',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  CHECKED_IN: {
    label: 'Đã check-in',
    classes: 'bg-sky-50 text-sky-900 border-sky-300',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  SENT: {
    label: 'Đã gửi',
    classes: 'bg-[#E6F4EC] text-[#14532D] border-[#A7D7BA]',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  CANCELLED: {
    label: 'Đã hủy',
    classes: 'bg-red-50 text-red-900 border-red-200',
    icon: <Ban className="w-3 h-3" aria-hidden="true" />,
  },
  REVOKED: {
    label: 'Đã thu hồi',
    classes: 'bg-red-50 text-red-900 border-red-200',
    icon: <Ban className="w-3 h-3" aria-hidden="true" />,
  },
  FAILED: {
    label: 'Thất bại',
    classes: 'bg-red-50 text-red-900 border-red-200',
    icon: <AlertTriangle className="w-3 h-3" aria-hidden="true" />,
  },
  COMPENSATION_REQUIRED: {
    label: 'Cần đối soát',
    classes: 'bg-amber-50 text-amber-950 border-amber-400',
    icon: <AlertTriangle className="w-3 h-3" aria-hidden="true" />,
  },
  EXPIRED: {
    label: 'Hết hạn',
    classes: 'bg-[#ECEBE2] text-[#4B524D] border-[#D4D6CD]',
    icon: <Clock className="w-3 h-3" aria-hidden="true" />,
  },
  ACTIVE: {
    label: 'Hoạt động',
    classes: 'bg-[#E6F4EC] text-[#14532D] border-[#A7D7BA]',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  MAINTENANCE: {
    label: 'Bảo trì',
    classes: 'bg-amber-50 text-amber-900 border-amber-300',
    icon: <Wrench className="w-3 h-3" aria-hidden="true" />,
  },
  INDOOR: {
    label: 'Trong nhà',
    classes: 'bg-[#E9EFEA] text-court border-[#C3D1C7]',
  },
  OUTDOOR: {
    label: 'Ngoài trời',
    classes: 'bg-[#FDF1EB] text-[#8F4324] border-[#E8C1B0]',
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const cfg = STATUS_MAP[status] || {
    label: status,
    classes: 'bg-[#ECEBE2] text-charcoal border-[#D4D6CD]',
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md border text-xs font-semibold whitespace-nowrap ${cfg.classes}`}
    >
      {cfg.icon}
      <span>{cfg.label}</span>
    </span>
  );
};
