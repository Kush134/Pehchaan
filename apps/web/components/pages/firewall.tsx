"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  Check,
  CircleCheck,
  Fingerprint,
  LockKeyhole,
  Play,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, post } from "@/lib/api";
import { money, when } from "@/lib/utils";
import { useUI } from "@/store/ui";
import type { Decision } from "@/types";
import { Badge, Busy, Empty, PageTitle, Panel } from "../shared";
import { Button } from "../ui/button";
import { Field } from "./comeback";
export default function Firewall() {
  const [amount, setAmount] = useState(95000);
  const [round, setRound] = useState(1);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  const notify = useUI((s) => s.notify);
  const client = useQueryClient();
  const { data: audit = [] } = useQuery({
    queryKey: ["firewall-audit"],
    queryFn: () => api<Decision[]>("/firewall/audit"),
  });
  const validate = async (value = amount) => {
    setAmount(value);
    setBusy(true);
    try {
      const d = await post<Decision>("/firewall/validate", {
        amount: value,
        budget: 40000,
        seller_id: "seller-a",
        round_number: round,
        operation: "quote",
        merchant_approved: false,
        buyer_confirmed: false,
        quantity_available: true,
        delivery_feasible: true,
        discount_percent: 0,
      });
      setDecision(d);
      await client.invalidateQueries();
      notify(
        d.status.toLowerCase() === "blocked"
          ? "Proposal blocked by the deterministic mandate firewall."
          : "Proposal evaluated. Required approvals are still enforced.",
      );
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="DETERMINISTIC SECURITY"
        title="Your mandate is the final word."
        description="AI agents can propose. Your rules decide what happens next."
        actions={
          <Badge tone="green">
            <ShieldCheck size={12} />
            PYTHON POLICY ENGINE
          </Badge>
        }
      />
      <div className="firewall-banner">
        <div className="firewall-emblem">
          <ShieldCheck size={30} />
        </div>
        <div>
          <h2>Every financial action passes through here.</h2>
          <p>
            Deterministic checks, signed mandates, explicit approvals, and a
            persistent audit trail.
          </p>
        </div>
        <div className="firewall-banner-stat">
          <strong>
            {audit.filter((d) => d.status.toLowerCase() === "blocked").length}
          </strong>
          <span>proposals blocked</span>
        </div>
      </div>
      <div className="two-column firewall-layout">
        <Panel
          title="Test the mandate"
          subtitle="Submit a synthetic proposal to the same policy engine"
        >
          <div className="scenario-buttons">
            <button
              className={amount === 95000 ? "selected" : ""}
              onClick={() => setAmount(95000)}
            >
              <ShieldAlert size={17} />
              <strong>Rogue proposal</strong>
              <span>{money(95000)}</span>
            </button>
            <button
              className={amount === 34000 ? "selected" : ""}
              onClick={() => setAmount(34000)}
            >
              <LockKeyhole size={17} />
              <strong>Merchant mandate</strong>
              <span>{money(34000)}</span>
            </button>
            <button
              className={amount === 36500 ? "selected" : ""}
              onClick={() => setAmount(36500)}
            >
              <CircleCheck size={17} />
              <strong>Eligible proposal</strong>
              <span>{money(36500)}</span>
            </button>
          </div>
          <div className="form-grid">
            <Field label="Proposed amount (₹)">
              <input
                type="number"
                value={amount}
                min={1}
                onChange={(e) => setAmount(Number(e.target.value))}
              />
            </Field>
            <Field label="Negotiation round">
              <input
                type="number"
                min={1}
                max={10}
                value={round}
                onChange={(e) => setRound(Number(e.target.value))}
              />
            </Field>
          </div>
          <div className="mandate-row">
            <span>Authorized buyer budget</span>
            <strong>{money(40000)}</strong>
          </div>
          <div className="mandate-row">
            <span>Seller pricing policy</span>
            <Badge>
              <LockKeyhole size={11} />
              CONFIDENTIAL
            </Badge>
          </div>
          <div className="mandate-row">
            <span>Merchant + buyer approval</span>
            <strong>Required</strong>
          </div>
          <Button
            className="wide-button"
            disabled={busy || !Number.isFinite(amount) || amount <= 0}
            onClick={() => void validate()}
          >
            {busy ? (
              <Busy>Validating proposal…</Busy>
            ) : (
              <>
                <Play size={14} />
                Run firewall check
              </>
            )}
          </Button>
          <p className="form-footnote">
            No LLM makes this security decision. Financial limits are enforced
            in Python.
          </p>
        </Panel>
        <Panel
          title="Policy decision"
          subtitle="Exact rules. Clear outcomes. No private pricing leaks."
        >
          {decision ? (
            <motion.div
              key={decision.id}
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <div
                className={`decision-result ${decision.status.toLowerCase() === "blocked" ? "blocked" : "eligible"}`}
              >
                {decision.status.toLowerCase() === "blocked" ? (
                  <ShieldAlert size={35} />
                ) : (
                  <ShieldCheck size={35} />
                )}
                <strong>
                  {decision.status.toUpperCase().replaceAll("_", " ")}
                </strong>
                <span>{money(decision.amount)} proposal</span>
                <p>{decision.reasons.join(" ")}</p>
              </div>
              <div className="rules-list">
                {decision.rules.map((r) => (
                  <div key={r.rule}>
                    <span className={r.passed ? "positive" : "negative"}>
                      {r.passed ? <Check size={14} /> : <X size={14} />}
                    </span>
                    <strong>{r.rule.replaceAll("_", " ")}</strong>
                    <small>{r.passed ? "Passed" : "Rejected"}</small>
                  </div>
                ))}
              </div>
            </motion.div>
          ) : (
            <Empty
              title="The firewall is ready"
              description="Run a proposal to inspect its validation results. Merchant pricing floors remain confidential."
            />
          )}
        </Panel>
      </div>
      <div className="security-properties">
        {[
          {
            icon: Fingerprint,
            title: "Signed mandates",
            text: "HMAC-SHA256 with constant-time verification",
          },
          {
            icon: LockKeyhole,
            title: "Replay protection",
            text: "Unique nonces, expiry, and persistent idempotency",
          },
          {
            icon: ShieldCheck,
            title: "Role-based permissions",
            text: "Tool actions stay within the authorized operation",
          },
        ].map((p) => (
          <div key={p.title}>
            <p.icon size={21} />
            <div>
              <strong>{p.title}</strong>
              <span>{p.text}</span>
            </div>
          </div>
        ))}
      </div>
      <Panel
        title="Decision audit trail"
        subtitle="Persisted policy decisions from this demonstration"
        action={<Badge>{audit.length} DECISIONS</Badge>}
      >
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Decision</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Outcome</th>
                <th>Recorded</th>
              </tr>
            </thead>
            <tbody>
              {audit.slice(0, 15).map((d) => (
                <tr key={d.id}>
                  <td className="mono">{d.id.slice(0, 12)}</td>
                  <td>{money(d.amount)}</td>
                  <td>
                    <Badge
                      tone={
                        d.status.toLowerCase() === "blocked" ? "red" : "green"
                      }
                    >
                      {d.status.replaceAll("_", " ")}
                    </Badge>
                  </td>
                  <td className="audit-reason">{d.reasons.join(" ")}</td>
                  <td>{when(d.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!audit.length && (
            <Empty
              title="A clean audit trail"
              description="Every validation you run will be recorded here."
            />
          )}
        </div>
      </Panel>
    </>
  );
}
