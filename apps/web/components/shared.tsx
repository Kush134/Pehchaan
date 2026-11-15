"use client";
import { motion, AnimatePresence } from "motion/react";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, Check, CircleAlert, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useUI } from "@/store/ui";
import { money, when } from "@/lib/utils";
import { Button } from "./ui/button";
import type { Event } from "@/types";
export function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="page-actions">{actions}</div>
    </div>
  );
}
export function Count({
  value,
  currency = false,
}: {
  value: number;
  currency?: boolean;
}) {
  const [n, setN] = useState(value);
  useEffect(() => {
    let frame = 0;
    const start = performance.now();
    const tick = (time: number) => {
      const progress = Math.min((time - start) / 550, 1);
      setN(value * (1 - Math.pow(1 - progress, 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <>{currency ? money(n) : Math.round(n).toLocaleString("en-IN")}</>;
}
export function Stat({
  label,
  value,
  currency = false,
  note,
  icon,
  accent,
}: {
  label: string;
  value: number;
  currency?: boolean;
  note: string;
  icon: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`stat ${accent ? "stat-accent" : ""}`}>
      <div className="stat-label">
        {label}
        <span>{icon}</span>
      </div>
      <div className="stat-value">
        <Count value={value} currency={currency} />
      </div>
      <div className="stat-note">{note}</div>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading-grid" role="status" aria-label="Loading workspace">
      {[1, 2, 3, 4].map((n) => (
        <div key={n} className="skeleton" />
      ))}
      <div className="skeleton skeleton-wide" />
      <span className="sr-only">Loading workspace</span>
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  return (
    <div className="empty-state">
      <CircleAlert size={30} />
      <h2>Couldn’t reach the workspace</h2>
      <p>{error.message}</p>
      <Button variant="secondary" onClick={retry}>
        Try again
      </Button>
    </div>
  );
}
export function Empty({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">
        <ArrowUpRight />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
export function Busy({ children }: { children: string }) {
  return (
    <>
      <Loader2 size={15} className="spin" />
      {children}
    </>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal-content">
          <div className="modal-heading">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>{description}</Dialog.Description>
            </div>
            <Dialog.Close
              className="btn btn-icon btn-ghost"
              aria-label="Close dialog"
            >
              <X size={18} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function EventFeed({
  events,
  limit = 6,
}: {
  events: Event[];
  limit?: number;
}) {
  return (
    <div className="event-feed">
      {events.length === 0 ? (
        <Empty
          title="Your workspace is ready"
          description="Run a workflow to see its execution events here."
        />
      ) : (
        events.slice(0, limit).map((e) => (
          <motion.div
            initial={{ opacity: 0, x: 5 }}
            animate={{ opacity: 1, x: 0 }}
            className="event-row"
            key={e.id}
          >
            <span
              className={`event-dot ${e.status === "blocked" || e.status === "error" ? "red" : e.status === "running" ? "amber" : ""}`}
            />
            <div>
              <strong>{e.title}</strong>
              <p>{e.detail}</p>
            </div>
            <time>{when(e.created_at)}</time>
          </motion.div>
        ))
      )}
    </div>
  );
}
export function Toasts() {
  const { toasts, dismiss } = useUI();
  return (
    <div className="toast-stack" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: 30 }}
            className={`toast ${t.kind}`}
          >
            <span>
              {t.kind === "success" ? (
                <Check size={18} />
              ) : (
                <CircleAlert size={18} />
              )}
            </span>
            {t.text}
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
            >
              <X size={15} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
