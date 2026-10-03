# Frontend Design System Specifications (FRONTEND_GUIDELINES.md) — Bharat FoodSafe

**App Name:** Bharat FoodSafe  
**Specification Version:** 1.5.0  
**Document Status:** Build-Locked Specification  
**Design Aesthetic:** High-Contrast, Tactile Mobile-First Operational UI (Kitchen Environment Optimized)  

---

## 1. Core Design Principles

1. **Glanceable Operational Status:** Kitchen staff operating under high-pressure shift conditions must identify safety status (`NORMAL` = Emerald Green, `DEVIATION` = Amber Yellow, `CRITICAL` = Crimson Red) within $< 100\text{ ms}$ at a distance of 1 meter.
2. **Tactile Touch Targets:** All interactive mobile buttons, form inputs, and camera triggers adhere to a minimum physical touch target of $48\times 48\text{ px}$ to accommodate single-handed kitchen operation with wet or gloved hands.
3. **Zero-Distraction Workflow:** Forms prioritize numeric keypads, direct camera launchers, and zero unnecessary decorative elements during shift task execution.
4. **Resilient High-Glare Readability:** High-contrast color pairings and crisp typography (Inter) guarantee legibility under harsh commercial kitchen fluorescent lighting.

---

## 2. Design Tokens

### 2.1 Color Palette & Hex Scales

#### Primary Palette — Emerald (Safety, Health & Verified SOPs)
Used for main brand elements, completed tasks, valid evidence badges, and primary action buttons.

```css
:root {
  --color-primary-50:  #ecfdf5;
  --color-primary-100: #d1fae5;
  --color-primary-200: #a7f3d0;
  --color-primary-300: #6ee7b7;
  --color-primary-400: #34d399;
  --color-primary-500: #10b981; /* Main Brand / Base Primary */
  --color-primary-600: #059669; /* Hover / Active Primary */
  --color-primary-700: #047857; /* Dark Primary */
  --color-primary-800: #065f46;
  --color-primary-900: #064e3b;
}
```

#### Neutral Palette — Slate (Backgrounds, Borders, Cards & Text)
Provides high contrast, neutral surfaces optimized for dark and light UI states.

```css
:root {
  --color-neutral-50:  #f8fafc; /* Main Page Background */
  --color-neutral-100: #f1f5f9; /* Surface Card Background */
  --color-neutral-200: #e2e8f0; /* Subtle Borders */
  --color-neutral-300: #cbd5e1; /* Input Borders */
  --color-neutral-400: #94a3b8; /* Muted Text / Icons */
  --color-neutral-500: #64748b; /* Secondary Text */
  --color-neutral-600: #475569; /* Label Text */
  --color-neutral-700: #334155; /* Dark Card Surface */
  --color-neutral-800: #1e293b; /* Primary Text (Light Mode) */
  --color-neutral-900: #0f172a; /* Deep Surface Background */
}
```

#### Semantic Status Colors
Strict color pairings for safety evaluation, incident status, and integrity review flags.

| Status Category | Status State | Hex Code | Background Hex | Tailwind Utility Class | Usage Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Success / Normal** | `NORMAL` / `VERIFIED` | `#059669` | `#ecfdf5` | `text-emerald-700 bg-emerald-50` | In-range measurements, verified evidence, verified CAPA. |
| **Warning / Deviation**| `DEVIATION` / `REVIEW` | `#d97706` | `#fffbeb` | `text-amber-700 bg-amber-50` | Minor out-of-range value, anomaly review signal, late entry. |
| **Error / Critical** | `CRITICAL` / `OVERDUE` | `#dc2626` | `#fef2f2` | `text-red-700 bg-red-50` | Critical safety breach, overdue task, active security alert. |
| **Info / Neutral** | `PENDING` / `DRAFT` | `#2563eb` | `#eff6ff` | `text-blue-700 bg-blue-50` | Pending assignment, draft task template, general system info. |

---

### 2.2 Typography Token System

Font Family: **Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif**

```css
:root {
  --font-sans: 'Inter', system-ui, sans-serif;

  /* Font Sizes & Line Heights */
  --text-xs:   0.75rem; /* 12px / line-height: 1.00rem */
  --text-sm:   0.875rem;/* 14px / line-height: 1.25rem */
  --text-base: 1.00rem; /* 16px / line-height: 1.50rem */
  --text-lg:   1.125rem;/* 18px / line-height: 1.75rem */
  --text-xl:   1.25rem; /* 20px / line-height: 1.75rem */
  --text-2xl:  1.50rem; /* 24px / line-height: 2.00rem */
  --text-3xl:  1.875rem;/* 30px / line-height: 2.25rem */

  /* Font Weights */
  --weight-regular:  400;
  --weight-medium:   500;
  --weight-semibold: 600;
  --weight-bold:     700;
}
```

---

### 2.3 Spacing, Radii & Shadow Scale

```css
:root {
  /* Spacing Scale (4px Increments) */
  --space-1:  0.25rem;  /* 4px */
  --space-2:  0.50rem;  /* 8px */
  --space-3:  0.75rem;  /* 12px */
  --space-4:  1.00rem;  /* 16px */
  --space-6:  1.50rem;  /* 24px */
  --space-8:  2.00rem;  /* 32px */
  --space-12: 3.00rem;  /* 48px */
  --space-16: 4.00rem;  /* 64px */

  /* Border Radii */
  --radius-none: 0px;
  --radius-sm:   0.25rem; /* 4px */
  --radius-md:   0.375rem;/* 6px */
  --radius-lg:   0.50rem; /* 8px */
  --radius-xl:   0.75rem; /* 12px */
  --radius-full: 9999px;

  /* Elevation Shadows */
  --shadow-sm:  0 1px 2px 0 rgba(15, 23, 42, 0.05);
  --shadow-md:  0 4px 6px -1px rgba(15, 23, 42, 0.10), 0 2px 4px -2px rgba(15, 23, 42, 0.05);
  --shadow-lg:  0 10px 15px -3px rgba(15, 23, 42, 0.10), 0 4px 6px -4px rgba(15, 23, 42, 0.05);
  --shadow-xl:  0 20px 25px -5px rgba(15, 23, 42, 0.10), 0 8px 10px -6px rgba(15, 23, 42, 0.05);
}
```

---

## 3. Reusable Component Library Specification

### 3.1 Button Component (`src/components/ui/Button.tsx`)

```tsx
import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  children,
  className = '',
  ...props
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed touch-manipulation';

  const variantClasses = {
    primary:   'bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white focus:ring-emerald-500 shadow-sm',
    secondary: 'bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-800 focus:ring-slate-400',
    danger:    'bg-red-600 hover:bg-red-700 active:bg-red-800 text-white focus:ring-red-500 shadow-sm',
    outline:   'border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 focus:ring-emerald-500',
    ghost:     'bg-transparent hover:bg-slate-100 text-slate-700 focus:ring-slate-400',
  };

  const sizeClasses = {
    sm: 'text-xs px-3 py-2 min-h-[36px]',
    md: 'text-sm px-4 py-2.5 min-h-[44px]',
    lg: 'text-base px-6 py-3 min-h-[52px] w-full sm:w-auto',
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <>
          <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" />
          <span>Processing...</span>
        </>
      ) : (
        children
      )}
    </button>
  );
};
```

---

### 3.2 Form Input Component (`src/components/ui/Input.tsx`)

```tsx
import React, { forwardRef } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  helperText,
  id,
  className = '',
  disabled,
  ...props
}, ref) => {
  const inputId = id || props.name;

  return (
    <div className="w-full flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-sm font-semibold text-slate-700">
          {label}
        </label>
      )}
      <input
        id={inputId}
        ref={ref}
        disabled={disabled}
        className={`w-full px-3.5 py-2.5 text-base sm:text-sm bg-white border rounded-lg transition-colors focus:outline-none focus:ring-2 disabled:bg-slate-50 disabled:text-slate-500 ${
          error
            ? 'border-red-500 focus:ring-red-500 text-red-900'
            : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-500 text-slate-900'
        } ${className}`}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : helperText ? `${inputId}-helper` : undefined}
        {...props}
      />
      {error && (
        <p id={`${inputId}-error`} className="text-xs font-medium text-red-600">
          {error}
        </p>
      )}
      {!error && helperText && (
        <p id={`${inputId}-helper`} className="text-xs text-slate-500">
          {helperText}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
```

---

### 3.3 Card Component (`src/components/ui/Card.tsx`)

```tsx
import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick }) => {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-slate-200 rounded-xl p-4 sm:p-6 shadow-sm ${
        onClick ? 'cursor-pointer hover:border-slate-300 hover:shadow-md transition-all' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};
```

---

### 3.4 Modal Component (`src/components/ui/Modal.tsx`)

```tsx
import React, { useEffect } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, title, children }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div
        className="w-full max-w-lg bg-white rounded-2xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h3 id="modal-title" className="text-lg font-bold text-slate-900">
            {title}
          </h3>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            aria-label="Close Modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 max-h-[80vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  );
};
```

---

### 3.5 Alert & Toast Banner Component (`src/components/ui/Alert.tsx`)

```tsx
import React from 'react';
import { CheckCircle2, AlertTriangle, AlertOctagon, Info } from 'lucide-react';

interface AlertProps {
  variant: 'success' | 'warning' | 'error' | 'info';
  title?: string;
  message: string;
}

export const Alert: React.FC<AlertProps> = ({ variant, title, message }) => {
  const styles = {
    success: { container: 'bg-emerald-50 border-emerald-200 text-emerald-900', icon: CheckCircle2, iconColor: 'text-emerald-600' },
    warning: { container: 'bg-amber-50 border-amber-200 text-amber-900', icon: AlertTriangle, iconColor: 'text-amber-600' },
    error:   { container: 'bg-red-50 border-red-200 text-red-900', icon: AlertOctagon, iconColor: 'text-red-600' },
    info:    { container: 'bg-blue-50 border-blue-200 text-blue-900', icon: Info, iconColor: 'text-blue-600' },
  };

  const { container, icon: Icon, iconColor } = styles[variant];

  return (
    <div className={`flex items-start p-4 border rounded-xl gap-3 ${container}`} role="alert">
      <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${iconColor}`} />
      <div className="flex-1 text-sm">
        {title && <h4 className="font-bold mb-0.5">{title}</h4>}
        <p className="leading-relaxed">{message}</p>
      </div>
    </div>
  );
};
```

---

### 3.6 Loading Skeleton Component (`src/components/ui/Skeleton.tsx`)

```tsx
import React from 'react';

interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = '' }) => {
  return (
    <div className={`animate-pulse bg-slate-200 rounded-md ${className}`} aria-hidden="true" />
  );
};
```

---

### 3.7 Empty State Component (`src/components/ui/EmptyState.tsx`)

```tsx
import React from 'react';
import { ClipboardX } from 'lucide-react';
import { Button } from './Button';

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
      <div className="p-4 mb-4 bg-white rounded-full shadow-sm text-slate-400">
        <ClipboardX className="w-8 h-8" />
      </div>
      <h3 className="text-base font-bold text-slate-900 mb-1">{title}</h3>
      <p className="text-sm text-slate-500 max-w-sm mb-6">{description}</p>
      {actionLabel && onAction && (
        <Button variant="primary" size="md" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
```

---

## 4. Layout System & Responsive Grid

### 4.1 Responsive Breakpoints
- **Mobile (`sm`):** `640px` (Staff task execution & camera capture focus)
- **Tablet (`md`):** `768px`
- **Desktop (`lg`):** `1024px` (Manager dashboards & multi-column tables)
- **Wide (`xl`):** `1280px` (Platform Admin overview)

### 4.2 App Shell Layout Pattern (`src/layouts/AppShell.tsx`)

```tsx
import React from 'react';
import { Outlet } from 'react-router-dom';

export const AppShell: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col antialiased">
      {/* Top Header */}
      <header className="h-16 bg-white border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <span className="font-extrabold text-lg text-emerald-700 tracking-tight">Bharat FoodSafe</span>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <Outlet />
      </main>

      {/* Mobile Bottom Navigation (Visible < 768px) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 bg-white border-t border-slate-200 flex justify-around items-center z-40">
        {/* Navigation Items */}
      </nav>
    </div>
  );
};
```

---

## 5. Accessibility (WCAG 2.1 AA Compliance)

1. **Color Contrast:** All text elements adhere to a minimum contrast ratio of `4.5:1` for body text and `3.0:1` for large heading text against background surfaces.
2. **Keyboard Focus Indicators:** Every focusable element features a high-contrast focus ring (`focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2`).
3. **Screen Reader Semantics:** Interactive elements use proper ARIA roles (`role="dialog"`, `role="alert"`, `aria-invalid`, `aria-describedby`).
4. **Form Association:** All form input controls have explicitly matching `<label htmlFor="...">` attributes.

---

## 6. Animation & Motion Standards

```css
/* Animation Duration Tokens */
--duration-fast:   150ms;
--duration-normal: 250ms;
--duration-slow:   400ms;

/* Timing Curve */
--ease-standard: cubic-bezier(0.4, 0.0, 0.2, 1.0);
```

- **Allowed Motion:** Modal fade-in/scale, toast slide-in, micro-hover scale ($1.02\times$).
- **Reduced Motion Support:** Respects `prefers-reduced-motion: reduce` by disabling non-essential layout animations for users with vestibular sensitivities.
