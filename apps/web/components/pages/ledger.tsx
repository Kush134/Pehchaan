"use client";
import Link from "next/link";
import CheckoutPanel from "./checkout";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useSummary } from "@/lib/hooks";
import { chartTooltip } from "./dashboard";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Camera,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  CreditCard,
  Download,
  FileSpreadsheet,
  Upload,
  ExternalLink,
  PackageCheck,
  ShieldCheck,
  Truck,
  X,
} from "lucide-react";
import { api, post } from "@/lib/api";
import { money } from "@/lib/utils";
import { useUI } from "@/store/ui";
import type { Order, Page } from "@/types";
import {
  Badge,
  Busy,
  Empty,
  ErrorState,
  Loading,
  Modal,
  PageTitle,
  Panel,
} from "../shared";
import { Button } from "../ui/button";
import "./utility.css";

type Transaction = {
  id: string;
  customer_token: string;
  amount: number;
  category: string;
  created_at: string;
  campaign_id: string | null;
  simulated: boolean;
};
type Timeline = { state: string; detail: string; created_at: string };
type LedgerOrder = Order & {
  packed: boolean;
  delivery_confirmed: boolean;
  inspection: {
    result?: string;
    provider?: string;
    human_confirmation_required?: boolean;
  } | null;
  timeline: Timeline[];
  payment_notice?: string;
  delivery_date?: string;
};
const steps = [
  "ORDER_CREATED",
  "PAYMENT_INITIATED",
  "AUTHORIZATION_SIMULATED",
  "DELIVERY_CONFIRMATION_PENDING",
  "SETTLEMENT_ELIGIBLE",
  "RELEASED_SIMULATED",
];
function dateLabel(value: string) {
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}
function stateLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (s) => s.toUpperCase());
}

export default function Ledger() {
  const { data: summary } = useSummary();
  const [tab, setTab] = useState<"orders" | "transactions">("orders");
  const [page, setPage] = useState(1);
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [approval, setApproval] = useState<LedgerOrder | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [voiding, setVoiding] = useState<LedgerOrder | null>(null);
  const [inspectionTarget, setInspectionTarget] = useState<string | null>(null);
  const photo = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const { notify } = useUI();
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<{ items: LedgerOrder[] }>("/orders"),
    refetchInterval: 5000,
  });
  const transactions = useQuery({
    queryKey: ["transactions", page],
    queryFn: () =>
      api<Page<Transaction>>(`/transactions?page=${page}&page_size=15`),
    enabled: tab === "transactions",
  });
  async function downloadTransactions(kind: "template" | "export") {
    setBusy(`download:${kind}`);
    try {
      const response = await fetch(`/api/v1/transactions/${kind}`);
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(
          error.detail || "The CSV download could not be prepared.",
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download =
        kind === "template"
          ? "pehchaan-transaction-template.csv"
          : "pehchaan-transactions.csv";
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      notify((error as Error).message, "error");
    } finally {
      setBusy(null);
    }
  }
  async function importTransactions() {
    if (!importFile) return;
    if (
      !importFile.name.toLowerCase().endsWith(".csv") ||
      importFile.size > 10 * 1024 * 1024
    ) {
      notify("Choose a transaction CSV file under 10 MB.", "error");
      return;
    }
    setBusy("import");
    try {
      const form = new FormData();
      form.append("file", importFile);
      const result = await api<{ imported: number; simulated: boolean }>(
        "/transactions/import",
        { method: "POST", body: form },
      );
      setImportOpen(false);
      setImportFile(null);
      setTab("transactions");
      setPage(1);
      await client.invalidateQueries();
      notify(
        `${result.imported} synthetic transactions imported. Customer intelligence has been recalculated.`,
      );
    } catch (error) {
      notify((error as Error).message, "error");
    } finally {
      setBusy(null);
    }
  }
  async function action(
    order: LedgerOrder,
    operation: "packed" | "delivery-confirm" | "release" | "void",
  ) {
    setBusy(`${order.id}:${operation}`);
    try {
      await post(
        `/orders/${order.id}/${operation}`,
        operation === "delivery-confirm" ? { confirmed: true } : {},
      );
      await client.invalidateQueries();
      setApproval(null);
      setVoiding(null);
      notify(
        operation === "packed"
          ? "Order marked packed."
          : operation === "delivery-confirm"
            ? "Human delivery confirmation saved."
            : operation === "release"
              ? "Simulated settlement released. No real money moved."
              : "Simulated order voided.",
      );
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy(null);
    }
  }
  async function uploadPhoto(file: File) {
    if (!inspectionTarget) return;
    if (file.size > 10 * 1024 * 1024) {
      notify("Packing images must be under 10 MB.", "error");
      return;
    }
    setBusy(`${inspectionTarget}:photo`);
    try {
      const body = new FormData();
      body.append("file", file);
      await api(`/orders/${inspectionTarget}/inspection`, {
        method: "POST",
        body,
      });
      await client.invalidateQueries({ queryKey: ["orders"] });
      notify(
        "Packing image reviewed as an advisory. Human delivery confirmation is still required.",
      );
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy(null);
      setInspectionTarget(null);
      if (photo.current) photo.current.value = "";
    }
  }
  if (orders.isPending) return <Loading />;
  if (orders.error)
    return (
      <ErrorState error={orders.error} retry={() => void orders.refetch()} />
    );
  const list = orders.data.items;
  const released = list.filter((o) => o.payment_state === "RELEASED_SIMULATED");
  const total = list
    .filter((o) => o.status !== "voided")
    .reduce((sum, o) => sum + o.total_amount, 0);
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE / AUDIT & SETTLEMENT"
        title="Transaction & order ledger"
        description="A complete record of merchant purchases and simulated bulk-order payments."
        actions={
          <>
            <Button
              variant="secondary"
              disabled={!!busy}
              onClick={() => {
                setImportFile(null);
                setImportOpen(true);
              }}
            >
              <Upload size={14} />
              Import transactions
            </Button>
            <Button
              variant="secondary"
              disabled={!!busy}
              onClick={() => void downloadTransactions("export")}
            >
              <Download size={14} />
              Export transactions
            </Button>
            <Badge tone="amber">
              <CreditCard size={12} />
              SIMULATED PAYMENTS ONLY
            </Badge>
          </>
        }
      />
      <CheckoutPanel />
      <div className="stats-grid utility-ledger-stats">
        <div className="stat">
          <div className="stat-label">
            Bulk orders <PackageCheck size={16} />
          </div>
          <div className="stat-value">{list.length}</div>
          <div className="stat-note">Confirmed through Haggle Arena</div>
        </div>
        <div className="stat">
          <div className="stat-label">
            Order value <CreditCard size={16} />
          </div>
          <div className="stat-value">{money(total)}</div>
          <div className="stat-note">Synthetic order value · INR</div>
        </div>
        <div className="stat">
          <div className="stat-label">
            Released settlements <CheckCircle2 size={16} />
          </div>
          <div className="stat-value">{released.length}</div>
          <div className="stat-note">No real money transferred</div>
        </div>
      </div>
      <Panel
        title="Bulk order performance"
        subtitle="Stored order value and order count by month"
      >
        <div className="chart-container" style={{ height: 180 }}>
          <ResponsiveContainer>
            <ComposedChart
              data={summary?.bulk_performance || []}
              margin={{ left: 0, right: 0, top: 5, bottom: 0 }}
            >
              <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
              <XAxis
                dataKey="month"
                stroke="var(--chart-axis)"
                axisLine={false}
                tickLine={false}
                fontSize={11}
              />
              <YAxis
                yAxisId="amount"
                tickFormatter={(value) => `₹${value / 1000}k`}
                stroke="var(--chart-axis)"
                axisLine={false}
                tickLine={false}
                fontSize={10}
              />
              <YAxis
                yAxisId="orders"
                orientation="right"
                allowDecimals={false}
                stroke="var(--chart-axis)"
                axisLine={false}
                tickLine={false}
                fontSize={10}
              />
              <Tooltip
                {...chartTooltip}
                formatter={(value, name) =>
                  name === "Order value" ? money(Number(value)) : value
                }
              />
              <Bar
                yAxisId="amount"
                dataKey="total"
                name="Order value"
                fill="var(--chart-primary)"
                maxBarSize={75}
                radius={[3, 3, 0, 0]}
                animationDuration={500}
              />
              <Line
                yAxisId="orders"
                dataKey="orders"
                name="Order count"
                stroke="var(--chart-secondary)"
                strokeWidth={2}
                animationDuration={500}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <div
        className="utility-ledger-tabs"
        role="tablist"
        aria-label="Ledger view"
      >
        <button
          role="tab"
          aria-selected={tab === "orders"}
          className={`utility-ledger-tab ${tab === "orders" ? "active" : ""}`}
          onClick={() => setTab("orders")}
        >
          Bulk orders <span>({list.length})</span>
        </button>
        <button
          role="tab"
          aria-selected={tab === "transactions"}
          className={`utility-ledger-tab ${tab === "transactions" ? "active" : ""}`}
          onClick={() => setTab("transactions")}
        >
          Merchant transactions
        </button>
      </div>
      {tab === "orders" ? (
        <>
          {list.length ? (
            <div className="utility-order-list">
              {list.map((order) => {
                const state =
                  order.payment_state ||
                  order.payment?.state ||
                  "ORDER_CREATED";
                const terminal =
                  state === "RELEASED_SIMULATED" ||
                  state === "VOIDED_SIMULATED" ||
                  state === "PAYMENT_FAILED";
                const activeIndex = steps.indexOf(state);
                return (
                  <article className="utility-order" key={order.id}>
                    <div className="utility-order-header">
                      <div>
                        <h3>
                          {order.seller_name || "Negotiated grocery order"}
                        </h3>
                        <p>
                          ORDER {order.id.slice(0, 8).toUpperCase()} ·{" "}
                          {dateLabel(order.created_at)}
                        </p>
                      </div>
                      <span className="utility-order-price">
                        {money(order.total_amount)}
                      </span>
                      <Badge
                        tone={
                          state === "RELEASED_SIMULATED"
                            ? "green"
                            : state === "VOIDED_SIMULATED"
                              ? "red"
                              : "amber"
                        }
                      >
                        {stateLabel(state)}
                      </Badge>
                    </div>
                    <div
                      className="utility-payment-track"
                      title={`Current state: ${stateLabel(state)}`}
                    >
                      {steps.map((s, i) => (
                        <span
                          key={s}
                          className={`utility-payment-step ${i <= activeIndex ? "complete" : ""}`}
                          title={stateLabel(s)}
                        />
                      ))}
                    </div>
                    <div className="utility-order-meta">
                      <span>
                        <strong>{order.items?.length || 0}</strong> product
                        lines
                      </span>
                      <span>
                        <Truck
                          size={13}
                          style={{
                            display: "inline",
                            verticalAlign: "middle",
                            marginRight: 5,
                          }}
                        />
                        {order.delivery_date || "Delivery schedule recorded"}
                      </span>
                      <span>
                        <ShieldCheck
                          size={13}
                          style={{
                            display: "inline",
                            verticalAlign: "middle",
                            marginRight: 5,
                          }}
                        />
                        Buyer and merchant confirmed
                      </span>
                      <span>
                        <strong>
                          {order.packed ? "Packed" : "Packing pending"}
                        </strong>
                      </span>
                    </div>
                    {order.inspection && (
                      <div className="utility-inspection">
                        <strong>
                          Image advisory ·{" "}
                          {order.inspection.provider || "local review"}
                        </strong>
                        <div>
                          {order.inspection.result ||
                            "Packing image received for human review."}
                        </div>
                        <div>
                          Human delivery confirmation{" "}
                          {order.delivery_confirmed ? "recorded" : "required"}.
                        </div>
                      </div>
                    )}
                    {expanded === order.id && (
                      <div style={{ margin: "18px 0" }}>
                        <div className="table-wrap">
                          <table className="data-table">
                            <thead>
                              <tr>
                                <th>Product</th>
                                <th>Quantity</th>
                                <th>Unit price</th>
                                <th>Line total</th>
                              </tr>
                            </thead>
                            <tbody>
                              {order.items?.map((item, i) => (
                                <tr key={i}>
                                  <td>{item.name}</td>
                                  <td>{item.quantity}</td>
                                  <td>{money(item.unit_price)}</td>
                                  <td>{money(item.total)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="utility-order-meta">
                          <span>
                            Subtotal{" "}
                            <strong>
                              {money(Number(order.subtotal || 0))}
                            </strong>
                          </span>
                          <span>
                            Delivery{" "}
                            <strong>
                              {money(Number(order.delivery_cost || 0))}
                            </strong>
                          </span>
                        </div>
                        <div className="utility-timeline">
                          {order.timeline?.map((event, i) => (
                            <div key={i}>
                              <Clock3 size={13} />
                              <div>
                                <strong>{stateLabel(event.state)}</strong>
                                <p>{event.detail}</p>
                                <time>{dateLabel(event.created_at)}</time>
                              </div>
                            </div>
                          ))}
                        </div>
                        <p
                          className="utility-body"
                          style={{ margin: "15px 0 0" }}
                        >
                          {order.payment_notice ||
                            "This ledger records an internal simulation. No real Paytm authorization, escrow, or payment occurs."}
                        </p>
                      </div>
                    )}
                    <div className="utility-order-controls">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() =>
                          setExpanded(expanded === order.id ? null : order.id)
                        }
                      >
                        {expanded === order.id
                          ? "Hide details"
                          : "View order & timeline"}
                        <ChevronRight size={13} />
                      </Button>
                      {!terminal && !order.packed && (
                        <Button
                          size="sm"
                          disabled={!!busy}
                          onClick={() => void action(order, "packed")}
                        >
                          {busy === `${order.id}:packed` ? (
                            <Busy>Saving…</Busy>
                          ) : (
                            <>
                              <PackageCheck size={14} />
                              Mark packed
                            </>
                          )}
                        </Button>
                      )}
                      {!terminal && (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={!!busy}
                          onClick={() => {
                            setInspectionTarget(order.id);
                            photo.current?.click();
                          }}
                        >
                          <Camera size={14} />
                          {busy === `${order.id}:photo`
                            ? "Reviewing image…"
                            : "Upload packing photo"}
                        </Button>
                      )}
                      {!terminal &&
                        order.packed &&
                        !order.delivery_confirmed && (
                          <Button
                            size="sm"
                            disabled={!!busy}
                            onClick={() => {
                              setConfirmed(false);
                              setApproval(order);
                            }}
                          >
                            <Truck size={14} />
                            Confirm delivery
                          </Button>
                        )}
                      {state === "SETTLEMENT_ELIGIBLE" && (
                        <Button
                          size="sm"
                          disabled={!!busy}
                          onClick={() => void action(order, "release")}
                        >
                          {busy === `${order.id}:release` ? (
                            "Releasing…"
                          ) : (
                            <>
                              <Check size={14} />
                              Release simulated settlement
                            </>
                          )}
                        </Button>
                      )}
                      {!terminal && (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={!!busy}
                          onClick={() => setVoiding(order)}
                        >
                          <X size={14} />
                          Void order
                        </Button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <Panel>
              <Empty
                title="Your next bulk order starts in Haggle Arena"
                description="Negotiate a basket, approve the eligible proposal, and confirm as buyer to create a simulated payment ledger."
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  paddingBottom: 24,
                }}
              >
                <Button asChild>
                  <Link href="/haggle">
                    Open Haggle Arena <ExternalLink size={14} />
                  </Link>
                </Button>
              </div>
            </Panel>
          )}
        </>
      ) : (
        <Panel
          title="Merchant transaction history"
          subtitle="Stored synthetic purchases · pseudonymous customer tokens"
        >
          {transactions.isPending ? (
            <Loading />
          ) : transactions.error ? (
            <ErrorState
              error={transactions.error}
              retry={() => void transactions.refetch()}
            />
          ) : (
            <>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Transaction</th>
                      <th>Customer token</th>
                      <th>Category</th>
                      <th>Amount</th>
                      <th>Date</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.data.items.map((t) => (
                      <tr key={t.id}>
                        <td className="mono">
                          {t.id.slice(0, 10).toUpperCase()}
                        </td>
                        <td className="mono">{t.customer_token}</td>
                        <td>{t.category}</td>
                        <td className="mono">{money(t.amount)}</td>
                        <td>{dateLabel(t.created_at)}</td>
                        <td>
                          <Badge tone={t.campaign_id ? "green" : "default"}>
                            {t.campaign_id
                              ? "Campaign simulation"
                              : "Synthetic seed"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="utility-pagination">
                <span>
                  {transactions.data.total.toLocaleString("en-IN")} stored
                  transactions · Page {page} of{" "}
                  {Math.max(1, Math.ceil(transactions.data.total / 15))}
                </span>
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                  >
                    <ChevronLeft size={13} />
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page * 15 >= transactions.data.total}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                    <ChevronRight size={13} />
                  </Button>
                </div>
              </div>
            </>
          )}
        </Panel>
      )}
      <input
        ref={photo}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        aria-label="Upload packing photo"
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void uploadPhoto(file);
        }}
      />
      <Modal
        open={importOpen}
        onOpenChange={setImportOpen}
        title="Import merchant transactions"
        description="Import synthetic purchases for known pseudonymous customer tokens. Prices, dates and every row are validated before saving."
      >
        <div className="utility-note">
          <FileSpreadsheet size={18} />
          <span>
            Use customer_token, amount, category and created_at columns.
            Existing customer tokens only; no phone numbers or UPI IDs. Imported
            purchases remain explicitly synthetic.
          </span>
        </div>
        <div
          className="utility-form-actions"
          style={{ justifyContent: "flex-start" }}
        >
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() => void downloadTransactions("template")}
          >
            <Download size={14} />
            Download transaction template
          </Button>
        </div>
        <label className="field">
          <span>Transaction CSV file</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setImportFile(event.target.files?.[0] || null)}
          />
        </label>
        <div className="utility-form-actions">
          <Button variant="secondary" onClick={() => setImportOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={!importFile || !!busy}
            onClick={() => void importTransactions()}
          >
            {busy === "import" ? (
              <Busy>Importing…</Busy>
            ) : (
              <>
                <Upload size={14} />
                Import CSV
              </>
            )}
          </Button>
        </div>
      </Modal>
      <Modal
        open={!!approval}
        onOpenChange={(open) => {
          if (!open) setApproval(null);
        }}
        title="Confirm delivery as a human"
        description="An image advisory alone cannot release a payment. Confirm that the demo order was delivered."
      >
        <label className="utility-human-check">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          <span>
            I have reviewed the demo delivery and confirm receipt of the ordered
            goods.
          </span>
        </label>
        <div className="utility-note">
          <ShieldCheck size={17} />
          <span>
            This marks the simulated settlement eligible. A separate release
            action is still required. No real money moves.
          </span>
        </div>
        <div className="utility-form-actions">
          <Button variant="secondary" onClick={() => setApproval(null)}>
            Cancel
          </Button>
          <Button
            disabled={!confirmed || !!busy}
            onClick={() => {
              if (approval) void action(approval, "delivery-confirm");
            }}
          >
            {busy ? "Confirming…" : "Confirm demo delivery"}
          </Button>
        </div>
      </Modal>
      <Modal
        open={!!voiding}
        onOpenChange={(open) => {
          if (!open) setVoiding(null);
        }}
        title="Void this simulated order?"
        description="The payment simulation will be marked void. This action does not contact a payment network."
      >
        <div className="utility-form-actions">
          <Button variant="secondary" onClick={() => setVoiding(null)}>
            Keep order
          </Button>
          <Button
            variant="destructive"
            disabled={!!busy}
            onClick={() => {
              if (voiding) void action(voiding, "void");
            }}
          >
            {busy ? "Voiding…" : "Void simulated order"}
          </Button>
        </div>
      </Modal>
    </>
  );
}
