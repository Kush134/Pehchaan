"use client";
import Link from "next/link";
import SmsPanel from "./sms";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDownUp,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  ChartNoAxesCombined,
  Check,
  ChevronRight,
  IndianRupee,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Zap,
} from "lucide-react";
import { useSummary } from "@/lib/hooks";
import { money, number } from "@/lib/utils";
import {
  Badge,
  ErrorState,
  EventFeed,
  Loading,
  PageTitle,
  Panel,
  Stat,
} from "../shared";
import { Button } from "../ui/button";
export const chartTooltip = {
  contentStyle: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: 7,
    color: "var(--ink)",
    fontSize: 12,
  },
  cursor: { stroke: "var(--chart-axis)", strokeDasharray: "4 4" },
};
const colors = [
  "var(--chart-primary)",
  "var(--chart-secondary)",
  "var(--chart-tertiary)",
  "var(--chart-fourth)",
  "var(--chart-fifth)",
  "var(--chart-sixth)",
  "var(--chart-seventh)",
];
export default function Dashboard({
  days,
  setDays,
  onDemo,
}: {
  days: number;
  setDays: (n: number) => void;
  onDemo: () => void;
}) {
  const { data: s, isLoading, error, refetch } = useSummary(days);
  if (isLoading) return <Loading />;
  if (error || !s)
    return (
      <ErrorState
        error={error || new Error("No summary returned")}
        retry={() => void refetch()}
      />
    );
  const m = s.metrics;
  return (
    <>
      <PageTitle
        eyebrow="YOUR MERCHANT GROWTH OS"
        title="Your merchant growth overview"
        description="A clearer view of your business. A smarter way to grow it."
        actions={
          <>
            <label className="range-select">
              <CalendarDays size={15} />
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                aria-label="Dashboard date range"
              >
                <option value={30}>Last 30 days</option>
                <option value={7}>Last 7 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </label>
            <Button onClick={onDemo}>
              <Play size={14} fill="currentColor" />
              Start walkthrough
            </Button>
          </>
        }
      />
      <div className="overview-context">
        <span>
          <span className="status-dot" />
          Sharma Kirana Store <span className="context-divider">/</span> Wakad,
          Pune
        </span>
        <span>
          {s.segments.reduce((count, segment) => count + segment.count, 0)}{" "}
          customer profiles <span className="context-divider">·</span> Updated
          from your ledger
        </span>
      </div>
      <div className="stats-grid">
        <Stat
          label="Merchant revenue"
          value={m.revenue}
          currency
          note={`${m.revenue_change >= 0 ? "+" : ""}${m.revenue_change.toFixed(1)}% vs previous ${days} days`}
          icon={<IndianRupee size={16} />}
        />
        <Stat
          label="Returning customers"
          value={m.returning_customers}
          note="Customers with repeat purchases"
          icon={<Users size={16} />}
        />
        <Stat
          label="Customers at risk"
          value={m.at_risk_customers}
          note="Outside their expected visit cadence"
          icon={<Target size={16} />}
          accent
        />
        <Stat
          label="Average basket value"
          value={m.average_basket}
          currency
          note={`Across ${number(m.transactions)} transactions`}
          icon={<ChartNoAxesCombined size={16} />}
        />
      </div>
      <SmsPanel compact />
      <div className="dashboard-main-grid">
        <Panel
          title="Revenue overview"
          subtitle="Your daily sales, from stored transactions"
          action={
            <Badge tone="green">
              <span className="status-dot" />
              LIVE DATA
            </Badge>
          }
          className="revenue-panel"
        >
          <div className="chart-summary">
            <strong>{money(m.revenue)}</strong>
            <span className={m.revenue_change >= 0 ? "positive" : "negative"}>
              <ArrowUpRight size={14} />
              {m.revenue_change.toFixed(1)}%
            </span>
            <small>in the last {days} days</small>
          </div>
          <div className="chart-container revenue-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={s.revenue_trend}
                margin={{ top: 15, right: 6, left: -17, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="revenue-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="0%"
                      stopColor="var(--chart-primary)"
                      stopOpacity={0.2}
                    />
                    <stop
                      offset="100%"
                      stopColor="var(--chart-primary)"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  stroke="var(--chart-grid)"
                  strokeDasharray="3 5"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  minTickGap={45}
                  tickFormatter={(v) =>
                    new Date(String(v)).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "short",
                    })
                  }
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
                  dy={10}
                />
                <YAxis
                  tickFormatter={(v) => `₹${v / 1000}k`}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
                />
                <Tooltip
                  {...chartTooltip}
                  formatter={(v) => money(Number(v))}
                  labelFormatter={(v) =>
                    new Date(String(v)).toLocaleDateString("en-IN", {
                      day: "numeric",
                      month: "long",
                    })
                  }
                />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  name="Revenue"
                  stroke="var(--chart-primary)"
                  strokeWidth={2}
                  fill="url(#revenue-fill)"
                  animationDuration={600}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-foot">
            <span>
              <i />
              Merchant revenue
            </span>
            <span>
              <ShieldCheck size={13} />
              All transactions are synthetic
            </span>
          </div>
        </Panel>
        <section className="recommendation-panel">
          <div className="recommendation-top">
            <span className="ai-mark">
              <Sparkles size={17} />
            </span>
            <span>YOUR NEXT BEST ACTION</span>
            <Badge tone="green">COMEBACK</Badge>
          </div>
          <h2>
            Give your regulars
            <br />a reason to return.
          </h2>
          <p>
            {s.recommendation.eligible_customers} customers are ready for a
            thoughtful nudge. Bring them back with an offer that protects your
            margin.
          </p>
          <div className="offer-preview">
            <div>
              <small>DISCOUNT</small>
              <strong>
                {money(s.recommendation.offer_amount)}
                <span> off</span>
              </strong>
            </div>
            <span className="offer-dash" />
            <div>
              <small>MINIMUM BILL</small>
              <strong>{money(s.recommendation.minimum_bill)}</strong>
            </div>
          </div>
          <div className="offer-projection">
            <span>Projected gross profit</span>
            <strong>{money(s.recommendation.projected_gross_profit)}</strong>
          </div>
          <Button asChild>
            <Link href="/comeback">
              Review campaign <ArrowRight size={15} />
            </Link>
          </Button>
          <small className="projection-note">
            Projection · Approval required before launch
          </small>
        </section>
      </div>
      <div className="dashboard-bottom-grid">
        <Panel
          title="Your agent network"
          subtitle="Purpose-built agents. One merchant mandate."
          action={
            <Link className="text-link" href="/agents">
              Open command center <ArrowUpRight size={13} />
            </Link>
          }
        >
          <div className="agent-orbit">
            <div className="orbit-lines" />
            <div className="orbit-agent side-agent">
              <span className="agent-mini cyan">
                <Users size={18} />
              </span>
              <strong>Intelligence</strong>
              <small>Finds opportunities</small>
            </div>
            <div className="orbit-agent center-agent">
              <span className="agent-mini mint">
                <Sparkles size={22} />
              </span>
              <strong>Comeback Agent</strong>
              <small>Turns insights into action</small>
            </div>
            <div className="orbit-agent side-agent">
              <span className="agent-mini amber">
                <ShieldCheck size={18} />
              </span>
              <strong>Firewall</strong>
              <small>Enforces your rules</small>
            </div>
          </div>
          <div className="network-summary">
            <span>
              <span className="status-dot" />
              {m.active_agents} agents executing
            </span>
            <span>
              <Check size={13} />
              Human approval required
            </span>
          </div>
        </Panel>
        <Panel
          title="Live activity"
          subtitle="A trace of what your workspace is doing"
          action={
            <span className="live-indicator">
              <RadioIcon />
              LIVE
            </span>
          }
        >
          <EventFeed events={s.recent_events} limit={4} />
          <Link className="panel-bottom-link" href="/agents">
            View execution timeline <ChevronRight size={14} />
          </Link>
        </Panel>
      </div>
      <div className="dashboard-third-grid">
        <Panel
          title="Customer health"
          subtitle="Calculated from purchase cadence and spend"
          action={
            <Link className="text-link" href="/customers">
              View customers <ArrowUpRight size={13} />
            </Link>
          }
        >
          <div className="segment-stacked">
            {s.segments.map((seg, i) => (
              <div
                key={seg.segment}
                style={{
                  width: `${seg.count}%`,
                  background: colors[i % colors.length],
                }}
                title={`${seg.segment}: ${seg.count}`}
              />
            ))}
          </div>
          <div className="segment-legend">
            {s.segments.map((seg, i) => (
              <div key={seg.segment}>
                <i style={{ background: colors[i % colors.length] }} />
                <span>{seg.segment}</span>
                <strong>{seg.count}</strong>
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title="Revenue by category"
          subtitle="A breakdown of your product sales"
        >
          <div className="chart-container category-chart">
            <ResponsiveContainer>
              <BarChart
                data={s.category_revenue}
                layout="vertical"
                margin={{ left: -20, right: 18, top: 0, bottom: 0 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  dataKey="category"
                  type="category"
                  width={105}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
                />
                <Tooltip
                  {...chartTooltip}
                  formatter={(v) => money(Number(v))}
                />
                <Bar
                  dataKey="revenue"
                  radius={[0, 3, 3, 0]}
                  barSize={13}
                  isAnimationActive={false}
                >
                  {s.category_revenue.map((x, i) => (
                    <Cell key={x.category} fill={colors[i % colors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel
          title="Growth, measured"
          subtitle="Observed results from your workspace"
        >
          <div className="growth-row">
            <span>
              <ArrowDownUp size={17} />
              Bulk orders
            </span>
            <strong>{m.bulk_orders}</strong>
          </div>
          <div className="growth-row">
            <span>
              <Zap size={17} />
              Campaign redemptions
            </span>
            <strong>{m.campaign_redemptions}</strong>
          </div>
          <div className="growth-row">
            <span>
              <IndianRupee size={17} />
              Discount expense
            </span>
            <strong>{money(m.discount_expense)}</strong>
          </div>
          <div className="growth-row">
            <span>
              <ChartNoAxesCombined size={17} />
              Incremental gross profit
            </span>
            <strong>
              {s.campaigns.some((c) => !c.stats.preliminary)
                ? money(m.incremental_gross_profit)
                : "Awaiting evidence"}
            </strong>
          </div>
          <div className="growth-note">
            <ShieldCheck size={16} />
            <span>
              Incremental impact is shown only when the experiment has enough
              observations.
            </span>
          </div>
        </Panel>
      </div>
    </>
  );
}
function RadioIcon() {
  return <span className="status-dot" />;
}
