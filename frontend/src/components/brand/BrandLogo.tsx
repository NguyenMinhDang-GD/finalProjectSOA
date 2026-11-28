import React from 'react';

interface BrandMarkProps {
  variant?: 'dark' | 'light' | 'lime';
  className?: string;
}

/**
 * Original geometric brand mark inspired by a pickleball paddle silhouette
 * intersecting the court non-volley line and a perforated ball.
 */
export const BrandMark: React.FC<BrandMarkProps> = ({
  variant = 'lime',
  className = 'w-9 h-9',
}) => {
  const bg =
    variant === 'lime'
      ? '#D9F45C'
      : variant === 'dark'
      ? '#142D26'
      : '#F6F5EE';
  const fg =
    variant === 'lime'
      ? '#142D26'
      : variant === 'dark'
      ? '#D9F45C'
      : '#142D26';
  const lineOpacity = variant === 'dark' ? '0.28' : '0.22';

  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect width="64" height="64" rx="16" fill={bg} />
      <rect
        x="8"
        y="8"
        width="48"
        height="48"
        rx="11"
        stroke={fg}
        strokeWidth="2.4"
        strokeOpacity={lineOpacity}
      />
      <line
        x1="8"
        y1="32"
        x2="56"
        y2="32"
        stroke={fg}
        strokeWidth="2"
        strokeOpacity={lineOpacity}
      />
      <path
        d="M22 18C22 15.7909 23.7909 14 26 14H38C40.2091 14 42 15.7909 42 18V33C42 38.5228 37.5228 43 32 43C26.4772 43 22 38.5228 22 33V18Z"
        fill={fg}
      />
      <rect x="29.5" y="42" width="5" height="10" rx="2.5" fill={fg} />
      <circle cx="32" cy="25" r="5" fill={bg} />
      <circle cx="30" cy="24" r="1.15" fill={fg} />
      <circle cx="34" cy="24" r="1.15" fill={fg} />
      <circle cx="32" cy="27.2" r="1.15" fill={fg} />
    </svg>
  );
};

interface BrandLockupProps {
  theme?: 'dark' | 'light';
  compact?: boolean;
}

export const BrandLockup: React.FC<BrandLockupProps> = ({
  theme = 'dark',
  compact = false,
}) => {
  const titleColor = theme === 'dark' ? 'text-white' : 'text-court';
  const subColor = theme === 'dark' ? 'text-[#B7C9BE]' : 'text-court-muted';

  return (
    <div className="inline-flex items-center gap-3 select-none">
      <BrandMark
        variant={theme === 'dark' ? 'lime' : 'dark'}
        className={compact ? 'w-8 h-8 shrink-0' : 'w-9 h-9 shrink-0'}
      />
      <div className="leading-none">
        <div
          className={`font-display font-extrabold tracking-tight ${titleColor} ${
            compact ? 'text-sm' : 'text-base sm:text-[17px]'
          }`}
        >
          PICKLEBALL <span className={theme === 'dark' ? 'text-ball-lime' : 'text-terracotta'}>SOA</span> ARENA
        </div>
        {!compact && (
          <div className={`text-[10px] font-semibold uppercase tracking-[0.18em] mt-1 ${subColor}`}>
            Athletic Club &amp; Court Booking
          </div>
        )}
      </div>
    </div>
  );
};
