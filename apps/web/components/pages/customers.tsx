"use client";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Search,
  ShieldCheck,
  Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { useSummary } from "@/lib/hooks";
import { money, when } from "@/lib/utils";
import type { Customer, CustomerDetail, Page, Segment } from "@/types";
import {
  Badge,
  Busy,
  ErrorState,
  Loading,
  Modal,
  PageTitle,
  Panel,
} from "../shared";
import { Button } from "../ui/button";
import { chartTooltip } from "./dashboard";
const col = createColumnHelper<Customer>();
export default function Customers() {
  const [search, setSearch] = useState(() =>
    typeof window === "undefined"
      ? ""
      : new URLSearchParams(window.location.search).get("search") || "",
  );
  const [segment, setSegment] = useState("All");
  const [page, setPage] = useState(1);
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["customer-detail", selectedToken],
    queryFn: () =>
      api<CustomerDetail>(
        `/customers/${encodeURIComponent(selectedToken || "")}`,
      ),
    enabled: !!selectedToken,
  });
  const { data: summary } = useSummary();
  const { data: segments = [] } = useQuery({
    queryKey: ["segments"],
    queryFn: () => api<Segment[]>("/customers/segments"),
  });
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["customers", search, segment, page],
    queryFn: () =>
      api<Page<Customer>>(
        `/customers?search=${encodeURIComponent(search)}&segment=${encodeURIComponent(segment)}&page=${page}&page_size=12`,
      ),
  });
  const columns = useMemo(
    () => [
      col.accessor("customer_token", {
        header: "Customer",
        cell: (i) => (
          <button
            className="customer-token btn btn-ghost"
            aria-label={`View customer ${i.getValue()}`}
            onClick={() => setSelectedToken(i.getValue())}
          >
            <span>
              <Users size={13} />
            </span>
            {i.getValue()}
          </button>
        ),
      }),
      col.accessor("customer_segment", {
        header: "Segment",
        cell: (i) => (
          <Badge
            tone={
              i.getValue().includes("Risk") || i.getValue().includes("Lost")
                ? "amber"
                : i.getValue() === "Champions"
                  ? "green"
                  : "default"
            }
          >
            {i.getValue()}
          </Badge>
        ),
      }),
      col.accessor("total_transactions", { header: "Visits" }),
      col.accessor("lifetime_spend", {
        header: "Lifetime spend",
        cell: (i) => money(i.getValue()),
      }),
      col.accessor("recency_days", {
        header: "Last visit",
        cell: (i) => `${i.getValue()}d ago`,
      }),
      col.accessor("average_intervisit_interval", {
        header: "Usual cadence",
        cell: (i) =>
          i.getValue()
            ? `${Number(i.getValue()).toFixed(1)} days`
            : "Building history",
      }),
      col.accessor("risk_score", {
        header: "Risk score",
        cell: (i) => (
          <div className="risk-cell">
            <div>
              <span
                style={{
                  width: `${i.getValue()}%`,
                  background:
                    i.getValue() > 60
                      ? "var(--warning)"
                      : "var(--chart-primary)",
                }}
              />
            </div>
            <span>{Math.round(i.getValue())}</span>
          </div>
        ),
      }),
    ],
    [],
  );
  // TanStack Table deliberately exposes stable table functions; React Compiler skips this hook.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: data?.items || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <>
      <PageTitle
        eyebrow="CUSTOMER INTELLIGENCE"
        title="Recognize the people who return."
        description="Visit cadence, spend patterns, and customer health. All calculated from your own ledger."
      />
      <div className="privacy-strip">
        <ShieldCheck size={15} />
        <span>
          Privacy by design. Customer tokens are pseudonymous. No phone numbers
          or UPI IDs.
        </span>
      </div>
      <div className="segment-filters">
        <button
          className={segment === "All" ? "selected" : ""}
          onClick={() => {
            setSegment("All");
            setPage(1);
          }}
        >
          All customers
          <strong>{segments.reduce((n, s) => n + s.count, 0)}</strong>
        </button>
        {segments.map((s) => (
          <button
            key={s.segment}
            className={segment === s.segment ? "selected" : ""}
            onClick={() => {
              setSegment(s.segment);
              setPage(1);
            }}
          >
            <span
              className="segment-filter-dot"
              style={{ background: s.color }}
            />
            {s.segment}
            <strong>{s.count}</strong>
          </button>
        ))}
      </div>
      <Panel
        title="Customer directory"
        subtitle="Personalized inactivity detection with minimum history safeguards"
        action={
          <div className="table-search">
            <Search size={15} />
            <input
              aria-label="Search customer tokens"
              placeholder="Search customer token…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        }
      >
        {isLoading ? (
          <Loading />
        ) : error ? (
          <ErrorState error={error} retry={() => void refetch()} />
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  {table.getHeaderGroups().map((g) => (
                    <tr key={g.id}>
                      {g.headers.map((h) => (
                        <th key={h.id}>
                          {flexRender(
                            h.column.columnDef.header,
                            h.getContext(),
                          )}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((r) => (
                    <tr key={r.id}>
                      {r.getVisibleCells().map((c) => (
                        <td key={c.id}>
                          {flexRender(c.column.columnDef.cell, c.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data?.items.length && (
                <div className="empty-state">
                  <Search />
                  <h3>No customers match this filter</h3>
                  <p>Try another segment or customer token.</p>
                </div>
              )}
            </div>
            <div className="table-pagination">
              <span>
                {data?.total || 0} customers <span>·</span> Page {page} of{" "}
                {Math.max(1, Math.ceil((data?.total || 0) / 12))}
              </span>
              <div>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ArrowLeft size={13} />
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page * 12 >= (data?.total || 0)}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ArrowRight size={13} />
                </Button>
              </div>
            </div>
          </>
        )}
      </Panel>
      <div className="two-column">
        <Panel
          title="Returning customer activity"
          subtitle="Weekly repeat and first-time customer counts"
        >
          <div className="chart-container">
            <ResponsiveContainer>
              <AreaChart
                data={summary?.retention_trend || []}
                margin={{ left: -22, right: 8, top: 12 }}
              >
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis
                  dataKey="week"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
                />
                <Tooltip {...chartTooltip} />
                <Area
                  dataKey="returning"
                  name="Returning"
                  type="monotone"
                  stroke="var(--chart-primary)"
                  fill="var(--chart-primary)"
                  fillOpacity={0.1}
                />
                <Area
                  dataKey="new"
                  name="New"
                  type="monotone"
                  stroke="var(--chart-secondary)"
                  fill="var(--chart-secondary)"
                  fillOpacity={0.06}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel
          title="Customer activity cohorts"
          subtitle="First-purchase cohorts · Weekly observed activity · — means not yet observed"
        >
          <div className="cohort-table">
            <div className="cohort-row cohort-head">
              <span>First seen</span>
              {Array.from({ length: 6 }, (_, i) => (
                <span key={i}>W{i + 1}</span>
              ))}
            </div>
            {(summary?.cohorts || []).map((c) => (
              <div className="cohort-row" key={c.cohort}>
                <span>
                  {c.cohort}
                  {c.size !== undefined && (
                    <>
                      <br />
                      <small>n={c.size}</small>
                    </>
                  )}
                </span>
                {c.values.slice(0, 6).map((v, i) => (
                  <span
                    key={i}
                    style={{
                      background:
                        v === null
                          ? "var(--surface-soft)"
                          : `color-mix(in srgb, var(--chart-primary) ${8 + v * 0.6}%, white)`,
                      color: "var(--brand-navy)",
                    }}
                  >
                    {v === null ? "—" : `${Math.round(v)}%`}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Modal
        open={!!selectedToken}
        onOpenChange={(open) => {
          if (!open) setSelectedToken(null);
        }}
        title={`Customer ${selectedToken || ""}`}
        description="A pseudonymous profile calculated only from purchases at this store."
      >
        {detail.isPending ? (
          <div className="empty-state">
            <Busy>Loading customer history…</Busy>
          </div>
        ) : detail.error ? (
          <ErrorState
            error={detail.error}
            retry={() => void detail.refetch()}
          />
        ) : (
          detail.data && (
            <>
              <div className="variant-grid">
                <div className="variant-card">
                  <small>RECENCY</small>
                  <strong>{detail.data.rfm.recency_days} days</strong>
                  <span>Since the last stored purchase</span>
                </div>
                <div className="variant-card">
                  <small>FREQUENCY</small>
                  <strong>{detail.data.rfm.frequency}</strong>
                  <span>Stored transactions</span>
                </div>
                <div className="variant-card">
                  <small>MONETARY</small>
                  <strong>{money(detail.data.rfm.monetary)}</strong>
                  <span>Lifetime spend</span>
                </div>
              </div>
              <div className="notice compact">
                <ShieldCheck size={16} />
                <p>{detail.data.insights.description}</p>
              </div>
              <div className="campaign-detail-stats">
                <div>
                  <span>Customer segment</span>
                  <Badge>{detail.data.customer.customer_segment}</Badge>
                </div>
                <div>
                  <span>Average basket value</span>
                  <strong>
                    {money(detail.data.customer.average_transaction_value)}
                  </strong>
                </div>
                <div>
                  <span>Expected visit interval</span>
                  <strong>
                    {detail.data.insights.expected_interval_days === null
                      ? "Building history"
                      : `${detail.data.insights.expected_interval_days.toFixed(1)} days`}
                  </strong>
                </div>
                <div>
                  <span>Previous 30-day spend</span>
                  <strong>
                    {money(detail.data.customer.previous_30_day_spend)}
                  </strong>
                </div>
                <div>
                  <span>Current 30-day spend</span>
                  <strong>
                    {money(detail.data.customer.current_30_day_spend)}
                  </strong>
                </div>
                <div>
                  <span>Merchant spend change</span>
                  <strong>
                    {detail.data.insights.spend_change_percent === null
                      ? "Insufficient history"
                      : `${detail.data.insights.spend_change_percent > 0 ? "+" : ""}${detail.data.insights.spend_change_percent.toFixed(1)}%`}
                  </strong>
                </div>
              </div>
              <div className="section-toolbar">
                <h3>Purchase activity</h3>
                <Badge>SYNTHETIC RECORDS</Badge>
              </div>
              <div className="chart-container" style={{ height: 180 }}>
                <ResponsiveContainer>
                  <AreaChart
                    data={detail.data.spend_trend}
                    margin={{ left: -10, right: 5, top: 10 }}
                  >
                    <CartesianGrid
                      stroke="var(--chart-grid)"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) =>
                        new Date(String(value)).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          timeZone: "Asia/Kolkata",
                        })
                      }
                      tick={{ fill: "var(--chart-axis)", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      minTickGap={50}
                    />
                    <YAxis
                      tick={{ fill: "var(--chart-axis)", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(value) => `₹${value}`}
                    />
                    <Tooltip
                      {...chartTooltip}
                      formatter={(value) => money(Number(value))}
                    />
                    <Area
                      type="monotone"
                      dataKey="amount"
                      name="Purchases"
                      stroke="var(--chart-primary)"
                      fill="var(--chart-primary)"
                      fillOpacity={0.12}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="section-toolbar">
                <h3>Purchase history</h3>
                <span className="form-footnote">
                  Most recent stored purchases
                </span>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Category</th>
                      <th>Amount</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.data.transactions.map((transaction) => (
                      <tr key={transaction.id}>
                        <td>{when(transaction.created_at)}</td>
                        <td>{transaction.category}</td>
                        <td>{money(transaction.amount)}</td>
                        <td>
                          <Badge>
                            {transaction.campaign_id
                              ? "Campaign simulation"
                              : "Synthetic purchase"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )
        )}
      </Modal>
      <div className="notice">
        <ArrowDown size={18} />
        <p>
          <strong>Merchant Spend Decline Detection.</strong> A change in
          spending here can indicate a retention opportunity. This data cannot
          identify purchases at other businesses.
        </p>
      </div>
    </>
  );
}
