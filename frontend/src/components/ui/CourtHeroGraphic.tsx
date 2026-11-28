import React from 'react';

export const CourtEmblem: React.FC<{ className?: string }> = ({ className = 'w-6 h-6' }) => (
  <svg
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
  >
    <rect x="3" y="5" width="26" height="22" rx="3" stroke="currentColor" strokeWidth="2.2" />
    <line x1="16" y1="5" x2="16" y2="27" stroke="currentColor" strokeWidth="1.8" strokeDasharray="2 2" />
    <line x1="10" y1="5" x2="10" y2="27" stroke="currentColor" strokeWidth="1.5" />
    <line x1="22" y1="5" x2="22" y2="27" stroke="currentColor" strokeWidth="1.5" />
    <line x1="3" y1="16" x2="10" y2="16" stroke="currentColor" strokeWidth="1.5" />
    <line x1="22" y1="16" x2="29" y2="16" stroke="currentColor" strokeWidth="1.5" />
    <circle cx="24.5" cy="10.5" r="3" fill="currentColor" />
  </svg>
);

export const CourtLinesBackdrop: React.FC = () => (
  <svg
    viewBox="0 0 420 220"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className="absolute right-0 top-0 h-full w-auto opacity-15 pointer-events-none select-none"
    aria-hidden="true"
  >
    <rect x="20" y="20" width="380" height="180" rx="8" stroke="#D9F45C" strokeWidth="2.5" />
    <line x1="210" y1="20" x2="210" y2="200" stroke="#D9F45C" strokeWidth="2" strokeDasharray="6 6" />
    <line x1="135" y1="20" x2="135" y2="200" stroke="#D9F45C" strokeWidth="2" />
    <line x1="285" y1="20" x2="285" y2="200" stroke="#D9F45C" strokeWidth="2" />
    <line x1="20" y1="110" x2="135" y2="110" stroke="#D9F45C" strokeWidth="2" />
    <line x1="285" y1="110" x2="400" y2="110" stroke="#D9F45C" strokeWidth="2" />
    <circle cx="330" cy="70" r="14" stroke="#D9F45C" strokeWidth="2" />
  </svg>
);
