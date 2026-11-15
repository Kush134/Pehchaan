"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Play, X } from "lucide-react";
import { useUI } from "@/store/ui";
import { post } from "@/lib/api";
import type { Campaign, Session } from "@/types";
import { Button } from "./ui/button";
const scenes = [
  {
    name: "The disappearing regulars",
    description:
      "Inspect the at-risk and declining cohorts. Visit cadence is calculated from 90 days of synthetic transactions.",
    button: "Show comeback opportunity",
    route: "/comeback",
  },
  {
    name: "A reason to come back",
    description:
      "Approve a ₹15 discount on a ₹250 bill. Create a real campaign, allocate A/B groups, and record simulated redemptions.",
    button: "Approve demo campaign",
    route: "/soundbox",
  },
  {
    name: "Your business, in your words",
    description:
      "Try a Hindi or Marathi command. Read the proposed change and explicitly approve it. Then send a basket to three seller agents.",
    button: "Start live negotiation",
    route: "/haggle",
  },
  {
    name: "Three agents. Four rounds.",
    description:
      "Watch seller counteroffers and firewall checks. Open the Command Center to inspect real execution events.",
    button: "Test the mandate firewall",
    route: "/firewall",
  },
  {
    name: "Your mandate holds",
    description:
      "Send a rogue ₹95,000 proposal against a ₹40,000 buyer budget. The same deterministic policy engine blocks it.",
    button: "Block rogue proposal",
    route: "/haggle",
  },
  {
    name: "The next payment",
    description:
      "Review the best eligible deal and confirm both approvals in the arena. In the ledger, pack, confirm delivery, and release the simulated settlement.",
    button: "Open simulated ledger",
    route: "/ledger",
  },
  {
    name: "More returning customers. Better deals.",
    description:
      "Your campaign and simulated bulk order now appear in the growth dashboard. Pehchaan helps merchants earn their next payment.",
    button: "Finish walkthrough",
    route: "/dashboard",
  },
];
export function JudgeDemo() {
  const { demoScene, setDemoScene, notify } = useUI();
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const router = useRouter();
  const scene = scenes[demoScene];
  const next = async () => {
    if (!scene) return;
    setBusy(true);
    try {
      if (demoScene === 1) {
        const start = new Date().toISOString().slice(0, 10);
        const end = new Date(Date.now() + 7 * 86400000)
          .toISOString()
          .slice(0, 10);
        const c = await post<Campaign>("/campaigns", {
          name: "Judge demo · Welcome back",
          target_segment: "At-Risk + Declining",
          offer_amount: 15,
          minimum_bill: 250,
          budget: 1500,
          max_customers: 30,
          start_date: start,
          end_date: end,
          language: "hi-IN",
          ab_test: true,
        });
        await post(`/campaigns/${c.id}/launch`);
        await post(`/campaigns/${c.id}/simulate-redemptions`);
        notify("Approved campaign allocated. Simulated transactions recorded.");
      }
      if (demoScene === 2) {
        const s = await post<Session>("/haggle/sessions", {
          requirement:
            "Office event groceries and snacks. Deliver within the coming week.",
          budget: 40000,
        });
        await post(`/haggle/sessions/${s.id}/start`);
        localStorage.setItem("pehchaan-session", s.id);
        notify("Live LangGraph negotiation started.");
      }
      if (demoScene === 4) {
        await post("/firewall/validate", {
          amount: 95000,
          budget: 40000,
          seller_id: "seller-a",
          round_number: 1,
          operation: "quote",
        });
        notify(
          "₹95,000 rogue bid blocked. Decision recorded in the audit trail.",
        );
      }
      await client.invalidateQueries();
      router.push(scene.route);
      setDemoScene(demoScene === scenes.length - 1 ? -1 : demoScene + 1);
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <AnimatePresence>
      {scene && (
        <motion.aside
          className="judge-demo"
          initial={{ opacity: 0, y: 80 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 80 }}
        >
          <div className="demo-scene-mark">
            <Play size={17} fill="currentColor" />
          </div>
          <div className="demo-scene-text">
            <small>
              WORKSPACE WALKTHROUGH{" "}
              <span>
                {demoScene + 1} / {scenes.length}
              </span>
            </small>
            <strong>{scene.name}</strong>
            <p>{scene.description}</p>
          </div>
          <div className="demo-scene-controls">
            <div className="demo-dots">
              {scenes.map((_, i) => (
                <i key={i} className={i <= demoScene ? "complete" : ""} />
              ))}
            </div>
            <Button disabled={busy} onClick={() => void next()}>
              {busy ? "Running workflow…" : scene.button}
              <ArrowRight size={14} />
            </Button>
          </div>
          <button
            className="demo-close btn btn-icon btn-ghost"
            aria-label="Close walkthrough"
            onClick={() => setDemoScene(-1)}
          >
            <X size={17} />
          </button>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
