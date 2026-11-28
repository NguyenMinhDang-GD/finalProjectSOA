import React from 'react';
import { AlertCircle, CheckCircle2, Info } from 'lucide-react';
import { Button } from './Button';

interface AlertBannerProps {
  tone?: 'error' | 'success' | 'warning' | 'info';
  title?: string;
  children: React.ReactNode;
  onRetry?: () => void;
}

const TONE_MAP = {
  error: {
    wrap: 'bg-red-50 border-red-200 text-red-900',
    icon: <AlertCircle className="w-4 h-4 text-red-700 shrink-0 mt-0.5" aria-hidden="true" />,
  },
  success: {
    wrap: 'bg-[#E6F4EC] border-[#A7D7BA] text-[#14532D]',
    icon: <CheckCircle2 className="w-4 h-4 text-[#14532D] shrink-0 mt-0.5" aria-hidden="true" />,
  },
  warning: {
    wrap: 'bg-amber-50 border-amber-200 text-amber-950',
    icon: <AlertCircle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" aria-hidden="true" />,
  },
  info: {
    wrap: 'bg-[#E9EFEA] border-[#C3D1C7] text-court',
    icon: <Info className="w-4 h-4 text-court shrink-0 mt-0.5" aria-hidden="true" />,
  },
};

export const AlertBanner: React.FC<AlertBannerProps> = ({
  tone = 'info',
  title,
  children,
  onRetry,
}) => {
  const cfg = TONE_MAP[tone];
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`rounded-xl border px-4 py-3 text-sm flex items-start justify-between gap-3 ${cfg.wrap}`}
    >
      <div className="flex items-start gap-2.5">
        {cfg.icon}
        <div>
          {title && <div className="font-bold mb-0.5">{title}</div>}
          <div>{children}</div>
        </div>
      </div>
      {onRetry && (
        <Button type="button" variant="secondary" size="sm" onClick={onRetry}>
          Thử lại
        </Button>
      )}
    </div>
  );
};

export const LoadingSkeleton: React.FC<{ rows?: number }> = ({ rows = 3 }) => (
  <div className="space-y-3 animate-pulse" aria-busy="true" aria-label="Đang tải dữ liệu">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="h-16 rounded-xl bg-[#E7E6DC]" />
    ))}
  </div>
);

export const EmptyState: React.FC<{
  title: string;
  description?: string;
  action?: React.ReactNode;
}> = ({ title, description, action }) => (
  <div className="rounded-xl border border-dashed border-[#C9CBC1] bg-white px-6 py-10 text-center">
    <p className="text-sm font-bold text-charcoal">{title}</p>
    {description && <p className="text-xs text-court-muted mt-1 max-w-md mx-auto">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const ConfirmDialog: React.FC<{
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({
  open,
  title,
  description,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Quay lại',
  loading = false,
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="w-full max-w-md rounded-2xl bg-white border border-[#D4D6CD] p-6 shadow-xl">
        <h2 id="confirm-dialog-title" className="text-base font-bold text-charcoal">
          {title}
        </h2>
        <p className="mt-2 text-sm text-court-muted">{description}</p>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button type="button" variant="danger" onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};
