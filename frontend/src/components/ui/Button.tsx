import React from 'react';

type ButtonVariant = 'primary' | 'accent' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-court text-white hover:bg-court-soft disabled:bg-court/50',
  accent: 'bg-ball-lime text-court font-bold hover:bg-[#cbe844] disabled:opacity-50',
  secondary:
    'bg-white text-charcoal border border-[#D4D6CD] hover:bg-[#ECEBE2] disabled:opacity-50',
  danger: 'bg-[#B93829] text-white hover:bg-[#9E2D20] disabled:opacity-50',
  ghost: 'bg-transparent text-court hover:bg-court/10 disabled:opacity-50',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs rounded-lg',
  md: 'px-4 py-2.5 text-sm rounded-lg',
  lg: 'px-5 py-3 text-sm rounded-xl',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className = '',
  children,
  ...rest
}) => {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-court focus-visible:ring-offset-2 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
};
