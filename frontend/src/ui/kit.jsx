// Design-system primitives. Every screen is assembled from these so spacing,
// focus rings, touch targets and states are decided once.
//
//   Button      primary | secondary | ghost | danger, loading state, 44px touch target
//   Field       label + control + hint + error, wired to the control for screen readers
//   Card        surface with optional title / actions
//   PageHeader  page title, subtitle and actions that wrap on a phone
//   Badge       neutral | success | warn | danger | info
//   Notice      inline message with an icon (never colour alone)
//   EmptyState  what to do when there is nothing to show
//   Skeleton    loading placeholder that keeps the layout from jumping
//   CopyField   read-only value with a copy button and confirmation
//   Avatar      initials on a stable colour

import { cloneElement, useEffect, useId, useRef, useState } from "react";
import Icon from "./Icon";

export function Spinner({ size = 16 }) {
  return <span className="ui-spinner" style={{ width: size, height: size }} role="status" aria-label="অপেক্ষা করুন" />;
}

export function Button({
  variant = "primary", size = "md", block = false, loading = false, icon, children,
  className = "", disabled, type = "button", ...rest
}) {
  const classes = ["ui-btn", `ui-btn--${variant}`, size === "sm" && "ui-btn--sm", block && "ui-btn--block", className]
    .filter(Boolean).join(" ");
  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <Spinner /> : icon ? <Icon name={icon} size={size === "sm" ? 16 : 18} /> : null}
      {children && <span>{children}</span>}
    </button>
  );
}

// `children` is the control (input / select / textarea). It receives the id and
// aria wiring so the label, hint and error are announced with it.
export function Field({ label, hint, error, required, children }) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  const control = cloneElement(children, {
    id, required, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy,
  });
  return (
    <div className={`ui-field${error ? " ui-field--error" : ""}`}>
      <label htmlFor={id}>
        {label}
        {required && <span className="ui-field__req" aria-hidden="true"> *</span>}
      </label>
      {control}
      {hint && !error && <p className="ui-field__hint" id={`${id}-hint`}>{hint}</p>}
      {error && <p className="ui-field__error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "", pad = true }) {
  return (
    <section className={`ui-card${pad ? "" : " ui-card--flush"} ${className}`}>
      {(title || actions) && (
        <header className="ui-card__head">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className="ui-card__actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <header className="ui-pagehead">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="ui-pagehead__actions">{actions}</div>}
    </header>
  );
}

export function Badge({ tone = "neutral", children, icon }) {
  return (
    <span className={`ui-badge ui-badge--${tone}`}>
      {icon && <Icon name={icon} size={13} />}
      {children}
    </span>
  );
}

const NOTICE_ICON = { info: "info", success: "check", warn: "alert", danger: "alert" };

export function Notice({ tone = "info", title, children, action }) {
  return (
    <div className={`ui-notice ui-notice--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon name={NOTICE_ICON[tone]} size={18} />
      <div className="ui-notice__body">
        {title && <strong>{title}</strong>}
        {children && <div>{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ icon = "info", title, hint, action }) {
  return (
    <div className="ui-empty">
      <span className="ui-empty__icon"><Icon name={icon} size={26} /></span>
      <h4>{title}</h4>
      {hint && <p>{hint}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ lines = 3, height = 14 }) {
  return (
    <div className="ui-skeleton" aria-busy="true" aria-label="লোড হচ্ছে">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} style={{ height, width: `${100 - (i % 3) * 14}%` }} />
      ))}
    </div>
  );
}

export function CopyField({ value, label = "কপি করুন" }) {
  const [copied, setCopied] = useState(false);
  const input = useRef(null);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch {
      // Clipboard blocked (insecure origin): select the text so the user can copy by hand.
      input.current?.select();
    }
  }
  return (
    <div className="ui-copy">
      <input ref={input} readOnly value={value} onFocus={(e) => e.target.select()} aria-label={label} />
      <Button variant={copied ? "secondary" : "primary"} icon={copied ? "check" : "copy"} onClick={copy}>
        {copied ? "কপি হয়েছে" : "কপি"}
      </Button>
    </div>
  );
}

const AVATAR_TONES = ["#0a8754", "#2563eb", "#b45309", "#7c3aed", "#0e7490", "#be185d", "#4d7c0f"];

export function Avatar({ name = "?", size = 36, src = null }) {
  if (src) {
    return (
      <img
        className="ui-avatar ui-avatar-photo"
        src={src}
        alt=""
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
    );
  }
  const initials = name.trim().split(/\s+/).slice(0, 2).map((part) => Array.from(part)[0] || "").join("") || "?";
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return (
    <span className="ui-avatar" style={{ width: size, height: size, background: AVATAR_TONES[hash % AVATAR_TONES.length] }} aria-hidden="true">
      {initials}
    </span>
  );
}


// A dialog that traps focus, closes on Esc and returns focus (the native <dialog>
// does all three). Use for short, focused tasks; anything longer is a page.
export function Modal({ open, title, onClose, children, footer, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className={`ui-modal${wide ? " ui-modal--wide" : ""}`}
            onClose={onClose} onCancel={onClose}
            onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      {open && (
        <div className="ui-modal__panel">
          <header>
            <h3>{title}</h3>
            <button type="button" className="ui-toast__close" onClick={onClose} aria-label="বন্ধ করুন"><Icon name="x" size={18} /></button>
          </header>
          <div className="ui-modal__body">{children}</div>
          {footer && <footer>{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}

// A number that matters: label, value, a line of context. Clickable when it filters something.
export function Stat({ label, value, sub, tone = "neutral", onClick, active = false, icon }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag type={onClick ? "button" : undefined} onClick={onClick}
         className={`ui-stat ui-stat--${tone}${active ? " is-active" : ""}${onClick ? " is-clickable" : ""}`}>
      <span className="ui-stat__label">{icon && <Icon name={icon} size={15} />}{label}</span>
      <strong className="ui-stat__value">{value}</strong>
      {sub && <span className="ui-stat__sub">{sub}</span>}
    </Tag>
  );
}

// Pill tabs (filters). Keyboard and screen-reader friendly.
export function Segmented({ options, value, onChange, label }) {
  const move = (event, index) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + options.length) % options.length;
    onChange(options[next].value);
    window.requestAnimationFrame(() => event.currentTarget.parentElement?.querySelectorAll('[role="tab"]')?.[next]?.focus());
  };
  return (
    <div className="ui-seg" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" aria-selected={value === o.value}
                className={value === o.value ? "on" : ""} onClick={() => onChange(o.value)} onKeyDown={(event) => move(event, options.indexOf(o))}>
          {o.label}{o.count !== undefined && <span className="ui-seg__count">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

// − 3 + : the quantity control a till needs. Big targets, direct typing allowed.
export function Stepper({ value, onChange, min = 1, max, label, step = 1 }) {
  const n = Number(value) || 0;
  const clamp = (v) => Math.max(min, max === undefined ? v : Math.min(max, v));
  return (
    <div className="ui-stepper" role="group" aria-label={label}>
      <button type="button" onClick={() => onChange(clamp(n - step))} disabled={n <= min} aria-label="কমান"><Icon name="minus" size={16} /></button>
      <input type="number" inputMode="decimal" value={value} min={min} max={max} step={step}
             onChange={(e) => onChange(e.target.value === "" ? "" : clamp(Number(e.target.value)))} aria-label={label} />
      <button type="button" onClick={() => onChange(clamp(n + step))} disabled={max !== undefined && n >= max} aria-label="বাড়ান"><Icon name="plus" size={16} /></button>
    </div>
  );
}
