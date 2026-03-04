"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-win98-silver bevel-outset text-win98-black active:bevel-pressed active:translate-x-px active:translate-y-px",
  secondary:
    "bg-win98-silver bevel-outset text-win98-black active:bevel-pressed active:translate-x-px active:translate-y-px",
  danger:
    "bg-win98-silver bevel-outset text-win98-red active:bevel-pressed active:translate-x-px active:translate-y-px",
  ghost:
    "bg-transparent text-win98-black hover:bg-win98-silver active:translate-x-px active:translate-y-px",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", loading, className = "", children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-bold uppercase tracking-wide focus:outline-dotted focus:outline-2 focus:outline-win98-black disabled:opacity-50 disabled:cursor-not-allowed ${variantStyles[variant]} ${className}`}
        {...props}
      >
        {loading && (
          <svg
            className="h-4 w-4 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
