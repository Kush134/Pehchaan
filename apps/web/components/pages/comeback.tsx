"use client";
import { useState } from "react";
import SmsPanel from "./sms";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowRight,
  Check,
  FlaskConical,
  IndianRupee,
  Play,
  Plus,
  Sparkles,
  Square,
  Target,
  Users,
} from "lucide-react";
import { api, post } from "@/lib/api";
import { useSummary } from "@/lib/hooks";
import { money } from "@/lib/utils";
import { useUI } from "@/store/ui";
import type { Campaign } from "@/types";
import {
  Badge,
  Busy,
  Empty,
  ErrorState,
  Loading,
  Modal,
  PageTitle,
  Panel,
  Stat,
} from "../shared";
import { Button } from "../ui/button";
import { chartTooltip } from "./dashboard";
const schema = z
  .object({
    name: z
      .string()
      .min(3, "Give the campaign a name of at least 3 characters."),
    target_segment: z.string(),
    offer_amount: z.number().positive().max(100),
    minimum_bill: z.number().positive(),
    budget: z.number().positive().max(100000),
    max_customers: z.number().int().min(1).max(100),
    start_date: z.string(),
    end_date: z.string(),
    language: z.string(),
    ab_test: z.boolean(),
  })
  .refine((d) => d.end_date >= d.start_date, {
    message: "End date must follow the start date.",
    path: ["end_date"],
  })
  .refine((d) => d.offer_amount / d.minimum_bill <= 0.14, {
    message: "Discount cannot exceed 14% of the minimum bill.",
    path: ["offer_amount"],
  });
type Values = z.infer<typeof schema>;
const today = () => new Date().toISOString().slice(0, 10);
const nextWeek = () =>
  new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);
export default function Comeback() {
  const client = useQueryClient();
  const notify = useUI((s) => s.notify);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const { data: summary } = useSummary();
  const {
    data: campaigns = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api<Campaign[]>("/campaigns"),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "A little welcome back",
      target_segment: "At-Risk + Declining",
      offer_amount: 15,
      minimum_bill: 250,
      budget: 1500,
      max_customers: 30,
      start_date: today(),
      end_date: nextWeek(),
      language: "hi-IN",
      ab_test: true,
    },
  });
  const create = form.handleSubmit(async (values) => {
    setBusy("create");
    try {
      const c = await post<Campaign>("/campaigns", values);
      setSelected(c.id);
      setOpen(false);
      await client.invalidateQueries();
      notify("Campaign proposal created. Review and launch when ready.");
    } catch (e) {
      form.setError("root", { message: (e as Error).message });
    } finally {
      setBusy("");
    }
  });
  const act = async (c: Campaign, action: string) => {
    setBusy(`${c.id}-${action}`);
    try {
      await post(`/campaigns/${c.id}/${action}`);
      await client.invalidateQueries();
      notify(
        action === "launch"
          ? "Campaign launched. Check the call panel for notification delivery."
          : action === "stop"
            ? "Campaign stopped."
            : "Simulated redemptions recorded in the transaction ledger.",
      );
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy("");
    }
  };
  if (isLoading) return <Loading />;
  if (error) return <ErrorState error={error} retry={() => void refetch()} />;
  const current = campaigns.find((c) => c.id === selected) || campaigns[0];
  const totals = campaigns.reduce(
    (t, c) => ({
      allocated: t.allocated + c.stats.allocated,
      redeemed: t.redeemed + c.stats.redeemed,
      expense: t.expense + c.stats.discount_expense,
    }),
    { allocated: 0, redeemed: 0, expense: 0 },
  );
  return (
    <>
      <PageTitle
        eyebrow="COMEBACK ENGINE"
        title="Bring your regulars back."
        description="Find the right customers. Make an eligible offer. Measure what happens."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} />
            Create campaign
          </Button>
        }
      />
      <div className="insight-banner">
        <span className="insight-icon">
          <Sparkles size={22} />
        </span>
        <div>
          <strong>
            {summary?.recommendation.eligible_customers || 0} regular customers
            are outside their expected visit window.
          </strong>
          <p>
            Personalized visit cadence identifies an opportunity. Every offer is
            checked against your margins and campaign budget.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setOpen(true)}>
          Review {money(15)} offer <ArrowRight size={14} />
        </Button>
      </div>
      <div className="stats-grid">
        <Stat
          label="Eligible customers"
          value={summary?.recommendation.eligible_customers || 0}
          note="Based on purchase cadence"
          icon={<Target size={16} />}
        />
        <Stat
          label="Offers allocated"
          value={totals.allocated}
          note="Treatment and control assignments"
          icon={<Users size={16} />}
        />
        <Stat
          label="Offers redeemed"
          value={totals.redeemed}
          note="Simulated, recorded transactions"
          icon={<Check size={16} />}
        />
        <Stat
          label="Discount expense"
          value={totals.expense}
          currency
          note="Actual simulated offer spend"
          icon={<IndianRupee size={16} />}
        />
      </div>
      <SmsPanel campaignId={current?.status === "active" ? current.id : undefined} />
      <div className="two-column campaign-layout">
        <Panel
          title="Your campaigns"
          subtitle="Merchant-approved retention experiments"
          action={<Badge>{campaigns.length} TOTAL</Badge>}
        >
          {campaigns.length ? (
            campaigns.map((c) => (
              <button
                className={`campaign-list-item ${current?.id === c.id ? "selected" : ""}`}
                key={c.id}
                onClick={() => setSelected(c.id)}
              >
                <span className="campaign-list-icon">
                  <Target size={18} />
                </span>
                <span>
                  <strong>{c.name}</strong>
                  <small>
                    {money(c.offer_amount)} off · Minimum{" "}
                    {money(c.minimum_bill)}
                  </small>
                </span>
                <Badge tone={c.status === "active" ? "green" : "default"}>
                  {c.status}
                </Badge>
              </button>
            ))
          ) : (
            <Empty
              title="Your first comeback starts here"
              description="Create a campaign and review the offer before allocating it to customers."
            />
          )}
        </Panel>
        {current ? (
          <Panel
            title={current.name}
            subtitle={`${current.target_segment} · ${current.language}`}
            action={
              <Badge tone={current.status === "active" ? "green" : "amber"}>
                {current.status.toUpperCase()}
              </Badge>
            }
          >
            <div className="variant-grid">
              {current.variants.map((v) => (
                <div key={v.id} className="variant-card">
                  <small>{v.name}</small>
                  <strong>{money(v.offer_amount)} off</strong>
                  <span>On bills of {money(v.minimum_bill)}+</span>
                </div>
              ))}
              <div className="variant-card control">
                <FlaskConical size={19} />
                <strong>Control group</strong>
                <span>No offer. Same observation window.</span>
              </div>
            </div>
            <div className="campaign-detail-stats">
              <div>
                <span>Campaign budget</span>
                <strong>{money(current.budget)}</strong>
              </div>
              <div>
                <span>Conversion rate</span>
                <strong>{current.stats.conversion_rate.toFixed(1)}%</strong>
              </div>
              <div>
                <span>Incremental gross profit estimate</span>
                <strong>
                  {current.stats.preliminary
                    ? "Preliminary"
                    : money(current.stats.incremental_gross_profit || 0)}
                </strong>
              </div>
            </div>
            <div className="campaign-actions">
              {current.status === "draft" && (
                <Button
                  disabled={!!busy}
                  onClick={() => void act(current, "launch")}
                >
                  <Play size={15} />
                  Approve & launch campaign
                </Button>
              )}
              {current.status === "active" && (
                <>
                  <Button
                    disabled={!!busy}
                    onClick={() => void act(current, "simulate-redemptions")}
                  >
                    {busy.endsWith("simulate-redemptions") ? (
                      <Busy>Simulating…</Busy>
                    ) : (
                      <>
                        <FlaskConical size={16} />
                        Simulate redemptions
                      </>
                    )}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={!!busy}
                    onClick={() => void act(current, "stop")}
                  >
                    <Square size={13} />
                    Stop campaign
                  </Button>
                </>
              )}
            </div>
            <div className="notice compact">
              <FlaskConical size={15} />
              <p>
                {current.stats.preliminary
                  ? "Preliminary results. This experiment needs more observations before claiming measured incremental impact."
                  : "Controlled experiment comparison. All redemptions and transactions in this workspace are simulated."}
              </p>
            </div>
          </Panel>
        ) : (
          <Panel title="A controlled experiment">
            <div className="experiment-illustration">
              <span>A</span>
              <span>B</span>
              <span>C</span>
            </div>
            <Empty
              title="Two offers. One control group."
              description="Reproducible assignments let you compare offers without confusing projections with observed results."
            />
          </Panel>
        )}
      </div>
      {current && (
        <div className="two-column">
          <Panel
            title="Treatment vs. control"
            subtitle="Conversion from observed simulated events"
          >
            <div className="chart-container">
              <ResponsiveContainer>
                <BarChart
                  data={[
                    {
                      name: "Treatment",
                      conversion: current.stats.treatment_conversion_rate,
                    },
                    {
                      name: "Control",
                      conversion: current.stats.control_conversion_rate,
                    },
                  ]}
                  margin={{ left: -20 }}
                >
                  <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                  <XAxis
                    dataKey="name"
                    stroke="var(--chart-axis)"
                    axisLine={false}
                    tickLine={false}
                    fontSize={12}
                  />
                  <YAxis
                    stroke="var(--chart-axis)"
                    axisLine={false}
                    tickLine={false}
                    fontSize={11}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip {...chartTooltip} formatter={(v) => `${v}%`} />
                  <Bar
                    dataKey="conversion"
                    fill="var(--chart-primary)"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={80}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel
            title="Customer assignments"
            subtitle="Pseudonymous tokens · Reproducible A/B allocation"
          >
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Customer token</th>
                    <th>Group</th>
                    <th>Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {current.assignments.slice(0, 10).map((a) => (
                    <tr key={a.customer_token}>
                      <td className="mono">{a.customer_token}</td>
                      <td>{a.variant}</td>
                      <td>
                        <Badge tone={a.redeemed ? "green" : "default"}>
                          {a.redeemed ? "Redeemed" : "Assigned"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!current.assignments.length && (
                <Empty
                  title="Ready for allocation"
                  description="Approve and launch the campaign to assign eligible customers."
                />
              )}
            </div>
          </Panel>
        </div>
      )}
      <Modal
        open={open}
        onOpenChange={setOpen}
        title="Create a comeback campaign"
        description="A proposal first. Your approval launches the simulated campaign."
      >
        <form onSubmit={create} className="campaign-form">
          <div className="form-grid">
            <Field
              label="Campaign name"
              error={form.formState.errors.name?.message}
              full
            >
              <input {...form.register("name")} />
            </Field>
            <Field label="Target segment">
              <select {...form.register("target_segment")}>
                {[
                  "At-Risk + Declining",
                  "All Customers",
                  "At-Risk Customers",
                  "Declining Customers",
                  "Lost Customers",
                  "Loyal Customers",
                  "Champions",
                  "Potential Loyalists",
                  "New Customers",
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            <Field label="Language">
              <select {...form.register("language")}>
                <option value="hi-IN">Hindi</option>
                <option value="mr-IN">Marathi</option>
                <option value="en-IN">English</option>
              </select>
            </Field>
            <Field
              label="Offer amount (₹)"
              error={form.formState.errors.offer_amount?.message}
            >
              <input
                type="number"
                {...form.register("offer_amount", { valueAsNumber: true })}
              />
            </Field>
            <Field
              label="Minimum bill (₹)"
              error={form.formState.errors.minimum_bill?.message}
            >
              <input
                type="number"
                {...form.register("minimum_bill", { valueAsNumber: true })}
              />
            </Field>
            <Field
              label="Campaign budget (₹)"
              error={form.formState.errors.budget?.message}
            >
              <input
                type="number"
                {...form.register("budget", { valueAsNumber: true })}
              />
            </Field>
            <Field
              label="Maximum customers"
              error={form.formState.errors.max_customers?.message}
            >
              <input
                type="number"
                {...form.register("max_customers", { valueAsNumber: true })}
              />
            </Field>
            <Field label="Start date">
              <input type="date" {...form.register("start_date")} />
            </Field>
            <Field
              label="End date"
              error={form.formState.errors.end_date?.message}
            >
              <input type="date" {...form.register("end_date")} />
            </Field>
          </div>
          <label className="checkbox-field">
            <input type="checkbox" {...form.register("ab_test")} />
            <span>Enable A/B testing with a reproducible control group</span>
          </label>
          {form.formState.errors.root && (
            <p className="field-error">{form.formState.errors.root.message}</p>
          )}
          <div className="modal-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!!busy}>
              {busy === "create" ? (
                <Busy>Creating proposal…</Busy>
              ) : (
                <>
                  Create campaign <ArrowRight size={14} />
                </>
              )}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
export function Field({
  label,
  error,
  full,
  children,
}: {
  label: string;
  error?: string;
  full?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={`field ${full ? "field-full" : ""}`}>
      <span>{label}</span>
      {children}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}
