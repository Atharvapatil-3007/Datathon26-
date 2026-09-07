import { ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
}

const BASE =
  "inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-muted/60 focus-visible:ring-offset-1 focus-visible:ring-offset-bg disabled:opacity-50 disabled:pointer-events-none";

const VARIANT: Record<Variant, string> = {
  primary:
    "bg-brand-soft border border-brand-muted text-ink hover:bg-brand-muted/40",
  secondary:
    "bg-bg-soft border border-line text-ink hover:bg-bg-hover",
  ghost:
    "text-ink-muted hover:text-ink hover:bg-bg-hover",
  danger:
    "border border-bad/40 text-bad hover:bg-bad/10",
};

const SIZE: Record<Size, string> = {
  sm: "text-xs px-2.5 py-1.5",
  md: "text-sm px-3.5 py-2",
  lg: "text-sm px-4 py-2.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, block, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(BASE, VARIANT[variant], SIZE[size], block && "w-full", className)}
      {...rest}
    >
      {loading && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-70" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
        </span>
      )}
      {children}
    </button>
  );
});
