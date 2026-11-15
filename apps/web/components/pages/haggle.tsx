"use client";
import { useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  ArrowDown,
  ArrowRight,
  Check,
  CircleCheck,
  FileImage,
  Loader2,
  Package,
  Pause,
  Play,
  Plus,
  Sparkles,
  RotateCcw,
  ShieldCheck,
  ShoppingBasket,
  Square,
  Truck,
  Upload,
  X,
} from "lucide-react";
import { api, post } from "@/lib/api";
import { useUI } from "@/store/ui";
import { money } from "@/lib/utils";
import type { ParsedBuyerRequest, Session } from "@/types";
import { Badge, Busy, Empty, Modal, PageTitle, Panel } from "../shared";
import { Button } from "../ui/button";
import { Field } from "./comeback";
const defaultItems = [
  { product_id: "rice", name: "Rice", quantity: 100, unit: "kg" },
  { product_id: "atta", name: "Wheat flour", quantity: 100, unit: "kg" },
  { product_id: "oil", name: "Cooking oil", quantity: 80, unit: "litre" },
  { product_id: "snacks", name: "Snacks", quantity: 200, unit: "pack" },
  { product_id: "tea", name: "Tea", quantity: 20, unit: "kg" },
];
const subscribeSession = (notify: () => void) => {
  window.addEventListener("storage", notify);
  window.addEventListener("pehchaan-session-change", notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener("pehchaan-session-change", notify);
  };
};
const readSession = () => localStorage.getItem("pehchaan-session");
const emptySession = () => null;
function writeSession(id: string | null) {
  if (id) localStorage.setItem("pehchaan-session", id);
  else localStorage.removeItem("pehchaan-session");
  window.dispatchEvent(new Event("pehchaan-session-change"));
}
export default function Haggle() {
  const sessionId = useSyncExternalStore(
    subscribeSession,
    readSession,
    emptySession,
  );
  const setSessionId = writeSession;
  const [requirement, setRequirement] = useState(
    "Grocery items and snacks for an office event. Delivery required by Friday.",
  );
  const [budget, setBudget] = useState(40000);
  const [delivery, setDelivery] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() + ((5 - date.getDay() + 7) % 7 || 7));
    return date.toISOString().slice(0, 10);
  });
  const [items, setItems] = useState(defaultItems);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [merchant, setMerchant] = useState(false);
  const [buyer, setBuyer] = useState(false);
  const [documentNotice, setDocumentNotice] = useState("");
  const [parsedRequest, setParsedRequest] = useState<ParsedBuyerRequest | null>(
    null,
  );
  const upload = useRef<HTMLInputElement>(null);
  const notify = useUI((s) => s.notify);
  const client = useQueryClient();
  const { data: s, error: sessionError } = useQuery({
    queryKey: ["haggle", sessionId],
    queryFn: () => api<Session>(`/haggle/sessions/${sessionId}`),
    enabled: !!sessionId,
    refetchInterval: (query) =>
      query.state.data &&
      [
        "awaiting_approval",
        "no_deal",
        "confirmed",
        "cancelled",
        "failed",
      ].includes(query.state.data.status)
        ? false
        : 1200,
  });
  const parseRequest = async () => {
    setBusy("parse");
    setError("");
    try {
      const parsed = await post<ParsedBuyerRequest>(
        "/haggle/parse-requirement",
        { requirement, language: "en-IN" },
      );
      setParsedRequest(parsed);
      if (parsed.items.length) setItems(parsed.items);
      if (parsed.budget !== null) setBudget(parsed.budget);
      if (parsed.delivery_date) setDelivery(parsed.delivery_date);
      notify(
        parsed.items.length
          ? "Request parsed. Review the basket, budget and delivery date before starting."
          : "No supported products were parsed. Edit the basket manually.",
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy("");
    }
  };
  const start = async () => {
    setBusy("start");
    setError("");
    try {
      const session = await post<Session>("/haggle/sessions", {
        requirement,
        budget,
        delivery_date: delivery,
        items,
      });
      setSessionId(session.id);
      localStorage.setItem("pehchaan-session", session.id);
      await post(`/haggle/sessions/${session.id}/start`);
      await client.invalidateQueries();
      notify(
        "Buyer dispatched. Three seller agents are reviewing the request.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const action = async (name: string) => {
    if (!sessionId) return;
    setBusy(name);
    try {
      await post(`/haggle/sessions/${sessionId}/${name}`);
      await client.invalidateQueries();
      notify(
        `Negotiation ${name === "pause" ? "paused" : name === "resume" ? "resumed" : "cancelled"}.`,
      );
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy("");
    }
  };
  const confirmOrder = async () => {
    if (!sessionId) return;
    setBusy("confirm");
    try {
      await post(`/haggle/sessions/${sessionId}/confirm`, {
        merchant_approved: merchant,
        buyer_confirmed: buyer,
      });
      setConfirm(false);
      await client.invalidateQueries();
      notify(
        "Order confirmed. Simulated authorization recorded in the ledger.",
      );
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy("");
    }
  };
  const extract = async (file: File) => {
    setBusy("upload");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("language", "en-IN");
      const result = await api<{
        items: {
          product_id?: string;
          name: string;
          quantity: number;
          unit?: string;
        }[];
        provider: string;
        demo: boolean;
        error?: string;
      }>("/documents/extract", { method: "POST", body: form });
      if (result.items.length)
        setItems(
          result.items.map((item) => ({
            product_id: item.product_id || "",
            name: item.name,
            quantity: item.quantity,
            unit: item.unit || "kg",
          })),
        );
      setDocumentNotice(
        `${result.demo ? "DEMO EXTRACTION" : "SARVAM DOCUMENT EXTRACTION"} · Review and correct every item before starting. ${result.error || ""}`,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const quotes = s?.quotes || [];
  const best = s?.best_deal;
  const running = s?.status === "running" || s?.status === "negotiating";
  const reset = async () => {
    if (s && ["paused", "created", "running"].includes(s.status)) {
      try {
        await post(`/haggle/sessions/${s.id}/cancel`);
      } catch (e) {
        notify((e as Error).message, "error");
        return;
      }
    }
    setSessionId(null);
    setError("");
  };
  return (
    <>
      <PageTitle
        eyebrow="MULTI-AGENT PROCUREMENT"
        title="Haggle Arena"
        description="One buyer. Three sellers. A better deal within your mandate."
        actions={
          <>
            <Badge tone="green">
              <ShieldCheck size={12} />
              MANDATE PROTECTED
            </Badge>
            {s && (
              <Button
                variant="secondary"
                onClick={() => void reset()}
                disabled={running}
              >
                <RotateCcw size={14} />
                Reset arena
              </Button>
            )}
          </>
        }
      />
      {!s ? (
        <div className="haggle-setup">
          <Panel
            title="What does your buyer need?"
            subtitle="A real negotiation workflow with four bounded rounds"
          >
            <div className="form-grid">
              <Field label="Buyer requirement" full>
                <textarea
                  rows={3}
                  value={requirement}
                  onChange={(e) => setRequirement(e.target.value)}
                />
              </Field>
              <div className="field-full">
                <Button
                  variant="secondary"
                  disabled={!!busy || !requirement.trim()}
                  onClick={() => void parseRequest()}
                >
                  {busy === "parse" ? (
                    <Busy>Reading request…</Busy>
                  ) : (
                    <>
                      <Sparkles size={14} />
                      Parse request
                    </>
                  )}
                </Button>
                <p className="form-footnote" style={{ textAlign: "left" }}>
                  Convert a written request into an editable basket. No seller
                  is contacted until you start negotiation.
                </p>
              </div>
              <Field label="Maximum budget (₹)">
                <input
                  type="number"
                  min={1}
                  max={1000000}
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                />
              </Field>
              <Field label="Delivery required by">
                <input
                  type="date"
                  value={delivery}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={(e) => setDelivery(e.target.value)}
                />
              </Field>
            </div>
            {parsedRequest && (
              <div className="notice compact">
                <ShieldCheck size={16} />
                <div>
                  <strong>Review parsed request</strong>{" "}
                  <Badge tone={parsedRequest.demo ? "amber" : "green"}>
                    {parsedRequest.demo ? "LOCAL PARSING" : "SARVAM AI"}
                  </Badge>
                  <p>
                    {parsedRequest.status === "unavailable"
                      ? "Automatic parsing is unavailable. Keep editing the fields manually."
                      : "Review every product, quantity, budget and date before starting."}
                  </p>
                  {parsedRequest.missing_fields.length > 0 && (
                    <p>
                      Not specified: {parsedRequest.missing_fields.join(", ")}.
                      The existing form values remain editable.
                    </p>
                  )}
                  {parsedRequest.unmatched_items.length > 0 && (
                    <p>
                      Unmatched products:{" "}
                      {parsedRequest.unmatched_items
                        .map((item) => `${item.name} (${item.reason})`)
                        .join("; ")}
                    </p>
                  )}
                  {parsedRequest.error && <p>{parsedRequest.error}</p>}
                </div>
              </div>
            )}
            <div className="section-toolbar">
              <h3>Review your basket</h3>
              <Button
                size="sm"
                variant="secondary"
                disabled={!!busy}
                onClick={() => upload.current?.click()}
              >
                <Upload size={14} />
                Upload parchi
              </Button>
              <input
                ref={upload}
                className="hidden"
                type="file"
                accept="image/jpeg,image/png,application/pdf"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void extract(f);
                  e.target.value = "";
                }}
              />
            </div>
            {documentNotice && (
              <div className="notice compact">
                <FileImage size={15} />
                <p>{documentNotice}</p>
              </div>
            )}
            <div className="basket-list">
              {items.map((item, i) => (
                <div className="basket-row" key={i}>
                  <span className="basket-icon">
                    <Package size={16} />
                  </span>
                  <select
                    aria-label={`Product ${i + 1}: ${item.name}`}
                    value={item.product_id}
                    onChange={(e) =>
                      setItems((old) =>
                        old.map((x, j) =>
                          j === i
                            ? {
                                ...x,
                                ...defaultItems.find(
                                  (d) => d.product_id === e.target.value,
                                ),
                                quantity: x.quantity,
                              }
                            : x,
                        ),
                      )
                    }
                  >
                    <option value="" disabled>
                      Map: {item.name}
                    </option>
                    {defaultItems.map((d) => (
                      <option
                        key={d.product_id}
                        value={d.product_id}
                        disabled={
                          d.product_id !== item.product_id &&
                          items.some(
                            (other) => other.product_id === d.product_id,
                          )
                        }
                      >
                        {d.name}
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label={`${item.name} quantity`}
                    type="number"
                    min={1}
                    value={item.quantity}
                    onChange={(e) =>
                      setItems((old) =>
                        old.map((x, j) =>
                          j === i
                            ? { ...x, quantity: Number(e.target.value) }
                            : x,
                        ),
                      )
                    }
                  />
                  <span>{item.unit}</span>
                  <button
                    aria-label={`Remove ${item.name}`}
                    className="btn btn-ghost btn-icon"
                    onClick={() =>
                      setItems((old) => old.filter((_, j) => i !== j))
                    }
                  >
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
            <Button
              variant="ghost"
              size="sm"
              disabled={
                !!busy ||
                defaultItems.every((product) =>
                  items.some((item) => item.product_id === product.product_id),
                )
              }
              onClick={() => {
                const next = defaultItems.find(
                  (product) =>
                    !items.some(
                      (item) => item.product_id === product.product_id,
                    ),
                );
                if (next)
                  setItems((current) => [...current, { ...next, quantity: 1 }]);
              }}
            >
              <Plus size={14} />
              Add item
            </Button>
            {error && (
              <p role="alert" className="field-error">
                {error}
              </p>
            )}
            {sessionError && (
              <p className="field-error">
                {sessionError.message}
                <button onClick={() => void reset()}>
                  Reset stale session
                </button>
              </p>
            )}
            <Button
              className="wide-button"
              disabled={
                !!busy ||
                !items.length ||
                items.some((item) => !item.product_id || item.quantity <= 0) ||
                budget <= 0 ||
                !requirement.trim()
              }
              onClick={() => void start()}
            >
              {busy ? (
                <Busy>Preparing negotiation…</Busy>
              ) : (
                <>
                  <Play size={15} fill="currentColor" />
                  Start negotiation
                </>
              )}
            </Button>
            <p className="form-footnote">
              The final deal requires merchant approval and buyer confirmation.
              Payments are simulated.
            </p>
          </Panel>
          <section className="arena-intro">
            <div className="arena-intro-grid" />
            <div className="intro-buyer">
              <ShoppingBasket size={28} />
              <span>BUYER AGENT</span>
            </div>
            <div className="intro-connectors" />
            <div className="intro-sellers">
              {["Sharma Wholesale", "Pune Grocery", "Sai Suppliers"].map(
                (name, i) => (
                  <div key={name}>
                    <span className={`seller-avatar seller-${i}`}>
                      {String.fromCharCode(65 + i)}
                    </span>
                    <strong>{name}</strong>
                    <small>Independent seller strategy</small>
                  </div>
                ),
              )}
            </div>
            <div className="intro-firewall">
              <ShieldCheck size={20} />
              <div>
                <strong>Every offer passes the firewall.</strong>
                <p>Budget · Stock · Delivery · Merchant mandate</p>
              </div>
            </div>
            <div className="arena-stack">
              <Badge>LANGGRAPH</Badge>
              <Badge>4 ROUNDS MAX</Badge>
              <Badge>HUMAN APPROVAL</Badge>
            </div>
          </section>
        </div>
      ) : (
        <>
          <div className="arena-session-bar">
            <div>
              <span className={`status-dot ${running ? "" : "muted-dot"}`} />
              <strong>{s.status.replaceAll("_", " ")}</strong>
              <span className="mono">{s.id.slice(0, 12)}</span>
            </div>
            <div>
              <span>
                Round <strong>{s.round_number} / 4</strong>
              </span>
              <span>
                Budget <strong>{money(s.budget)}</strong>
              </span>
              <Badge tone={s.provider === "sarvam" ? "green" : "amber"}>
                {s.provider === "sarvam" ? "SARVAM AI" : "DEMO REASONING"}
              </Badge>
            </div>
            <div>
              {running && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!!busy}
                  onClick={() => void action("pause")}
                >
                  <Pause size={13} />
                  Pause
                </Button>
              )}
              {s.status === "paused" && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!!busy}
                  onClick={() => void action("resume")}
                >
                  <Play size={13} />
                  Resume
                </Button>
              )}
              {["running", "paused", "created", "negotiating"].includes(
                s.status,
              ) && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!!busy}
                  onClick={() => void action("cancel")}
                >
                  <Square size={12} />
                  Cancel
                </Button>
              )}
            </div>
          </div>
          <div className="negotiation-progress">
            {[1, 2, 3, 4].map((round) => (
              <div
                className={s.round_number >= round ? "complete" : ""}
                key={round}
              >
                <span>
                  {s.round_number > round ? <Check size={14} /> : round}
                </span>
                <div>
                  <strong>Round {round}</strong>
                  <small>
                    {
                      [
                        "Opening quotes",
                        "Buyer evaluation",
                        "Counteroffers",
                        "Final optimization",
                      ][round - 1]
                    }
                  </small>
                </div>
                {s.round_number === round && running && (
                  <Loader2 className="spin" size={15} />
                )}
              </div>
            ))}
          </div>
          <div className="seller-grid">
            {["seller-a", "seller-b", "seller-c"].map((id, i) => {
              const quote = [...quotes]
                .filter((q) => q.seller_id === id)
                .sort((a, b) => b.round_number - a.round_number)[0];
              const name = [
                "Sharma Wholesale Mart",
                "Pune Grocery Distributors",
                "Sai General Suppliers",
              ][i];
              const previous = (s?.rounds.flatMap((r) => r.quotes) || [])
                .filter(
                  (q) =>
                    q.seller_id === id &&
                    q.round_number < (quote?.round_number || 0),
                )
                .sort((a, b) => b.round_number - a.round_number)[0];
              return (
                <motion.section
                  key={id}
                  animate={{
                    borderColor:
                      best?.seller_id === id
                        ? "var(--chart-primary)"
                        : "var(--border)",
                  }}
                  className={`panel seller-card ${best?.seller_id === id ? "winning" : ""}`}
                >
                  <div className="seller-card-head">
                    <span className={`seller-avatar seller-${i}`}>
                      {String.fromCharCode(65 + i)}
                    </span>
                    <div>
                      <h2>{name}</h2>
                      <span>MERCHANT AGENT {String.fromCharCode(65 + i)}</span>
                    </div>
                    {best?.seller_id === id && (
                      <CircleCheck size={20} className="positive" />
                    )}
                  </div>
                  <div className="seller-bid">
                    <small>{quote ? "CURRENT QUOTE" : "AWAITING QUOTE"}</small>
                    <motion.strong
                      key={quote?.total_amount}
                      initial={{ opacity: 0.4, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      {quote ? money(quote.total_amount) : "—"}
                    </motion.strong>
                    {previous && (
                      <span>
                        <ArrowDown size={12} />
                        {money(
                          previous.total_amount - quote!.total_amount,
                        )}{" "}
                        below previous round
                      </span>
                    )}
                  </div>
                  <div className="seller-terms">
                    <span>
                      <Package size={14} />
                      {quote?.products.length || items.length} product lines
                    </span>
                    <span>
                      <Truck size={14} />
                      {quote?.delivery_date || delivery}
                    </span>
                  </div>
                  <p className="seller-response">
                    {quote?.summary ||
                      "This agent will evaluate stock, delivery, and its own confidential pricing mandate."}
                  </p>
                  <div className="seller-status">
                    <Badge
                      tone={
                        quote?.status === "eligible"
                          ? "green"
                          : quote
                            ? "amber"
                            : "default"
                      }
                    >
                      {quote?.status?.replaceAll("_", " ") || "Waiting"}
                    </Badge>
                    <span>Round {quote?.round_number || 0}</span>
                  </div>
                </motion.section>
              );
            })}
          </div>
          <div className="two-column">
            <Panel
              title="Negotiation timeline"
              subtitle="Structured decisions and tool events, as they happen"
            >
              {s.rounds.length ? (
                s.rounds.map((r) => (
                  <motion.div
                    initial={{ opacity: 0, y: 7 }}
                    animate={{ opacity: 1, y: 0 }}
                    key={r.round_number}
                    className="round-event"
                  >
                    <span>{r.round_number}</span>
                    <div>
                      <strong>Round {r.round_number} completed</strong>
                      <p>{r.summary}</p>
                      <div className="round-quotes">
                        {r.quotes.map((q) => (
                          <span key={q.seller_id}>
                            {q.seller_name.split(" ")[0]}{" "}
                            <strong>{money(q.total_amount)}</strong>
                          </span>
                        ))}
                      </div>
                    </div>
                    <ShieldCheck size={17} />
                  </motion.div>
                ))
              ) : (
                <Empty
                  title="Agents are reviewing the basket"
                  description="Quote collection and policy checks will appear here as the workflow runs."
                />
              )}
            </Panel>
            <Panel
              title={best ? "Best eligible deal" : "Final bundle"}
              subtitle={
                best
                  ? "Deterministically optimized within stock, budget, and delivery constraints"
                  : "The supervisor selects only eligible proposals"
              }
              action={
                best ? (
                  <Badge tone="green">
                    <ShieldCheck size={12} />
                    VALIDATED
                  </Badge>
                ) : undefined
              }
            >
              {best ? (
                <>
                  <div className="best-deal-total">
                    <span>{best.seller_name}</span>
                    <strong>{money(best.total_amount)}</strong>
                    <small>
                      {money(s.budget - best.total_amount)} within your
                      authorized budget
                    </small>
                  </div>
                  {s.optimization_explanation && (
                    <div className="notice compact">
                      <ShieldCheck size={15} />
                      <p>{s.optimization_explanation}</p>
                    </div>
                  )}
                  <div className="deal-items">
                    {best.products.map((p) => (
                      <div key={p.product_id}>
                        <span>
                          {p.name} <small>× {p.quantity}</small>
                        </span>
                        <strong>{money(p.total)}</strong>
                      </div>
                    ))}
                    <div>
                      <span>Delivery</span>
                      <strong>{money(best.delivery_cost)}</strong>
                    </div>
                  </div>
                  {s.status === "confirmed" ? (
                    <Link
                      href="/ledger"
                      className="btn btn-primary wide-button"
                    >
                      View simulated order <ArrowRight size={14} />
                    </Link>
                  ) : (
                    <Button
                      className="wide-button"
                      onClick={() => setConfirm(true)}
                    >
                      Review & confirm order <ArrowRight size={14} />
                    </Button>
                  )}
                </>
              ) : (
                <Empty
                  title={
                    running
                      ? "Finding a better deal…"
                      : "Ready when the agents are"
                  }
                  description="The final recommendation will appear after the four-round negotiation."
                />
              )}
            </Panel>
          </div>
        </>
      )}
      <Modal
        open={confirm}
        onOpenChange={setConfirm}
        title="Confirm the eligible order"
        description="Both parties must approve. This creates a simulated payment authorization."
      >
        <div className="confirm-amount">
          <span>Order total</span>
          <strong>{money(best?.total_amount || 0)}</strong>
        </div>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={merchant}
            onChange={(e) => setMerchant(e.target.checked)}
          />
          <span>I approve this order as the merchant.</span>
        </label>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={buyer}
            onChange={(e) => setBuyer(e.target.checked)}
          />
          <span>I confirm the selected bundle as the buyer.</span>
        </label>
        <div className="notice">
          <ShieldCheck size={18} />
          <p>
            No real payment is authorized or moved. The ledger records a local
            simulation.
          </p>
        </div>
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setConfirm(false)}>
            Keep reviewing
          </Button>
          <Button
            disabled={!merchant || !buyer || !!busy}
            onClick={() => void confirmOrder()}
          >
            {busy === "confirm" ? (
              <Busy>Confirming…</Busy>
            ) : (
              <>
                Confirm simulated order <Check size={15} />
              </>
            )}
          </Button>
        </div>
      </Modal>
    </>
  );
}
