"use client";
import { useState } from "react";
import {
  Check,
  ChevronRight,
  Copy,
  Database,
  ExternalLink,
  Globe2,
  KeyRound,
  Languages,
  Radio,
  RefreshCw,
  ShieldCheck,
  Store,
  Wallet,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Health } from "@/types";
import { useUI } from "@/store/ui";
import { Badge, ErrorState, Loading, PageTitle, Panel } from "../shared";
import { Button } from "../ui/button";
import "./utility.css";

export default function Settings({ onReset }: { onReset: () => void }) {
  const health = useQuery({
    queryKey: ["settings-integrations"],
    queryFn: () =>
      api<Health & { merchant_language: string }>("/settings/integrations"),
  });
  const client = useQueryClient();
  const [language, setLanguage] = useState<string | null>(null);
  const [savingLanguage, setSavingLanguage] = useState(false);
  const [languageSaved, setLanguageSaved] = useState(false);
  const [languageError, setLanguageError] = useState("");
  const { notify } = useUI();
  const [copied, setCopied] = useState(false);
  if (health.isPending) return <Loading />;
  if (health.error)
    return (
      <ErrorState error={health.error} retry={() => void health.refetch()} />
    );
  const h = health.data;
  async function saveLanguage() {
    if (!language) return;
    setSavingLanguage(true);
    setLanguageError("");
    setLanguageSaved(false);
    try {
      await api("/settings/merchant", {
        method: "PATCH",
        body: JSON.stringify({ language }),
      });
      await client.invalidateQueries({ queryKey: ["settings-integrations"] });
      setLanguageSaved(true);
      notify("Default assistant language saved.");
    } catch (error) {
      setLanguageError((error as Error).message);
      notify((error as Error).message, "error");
    } finally {
      setSavingLanguage(false);
    }
  }
  async function copyConfiguration() {
    try {
      await navigator.clipboard.writeText(
        "SARVAM_API_KEY=your_subscription_key\nSARVAM_CHAT_MODEL=sarvam-105b\nSARVAM_STT_MODEL=saaras:v4\nSARVAM_TTS_MODEL=bulbul:v4-flash",
      );
      setCopied(true);
      notify(
        "Configuration template copied. Add your key only to the backend .env.",
      );
      setTimeout(() => setCopied(false), 3000);
    } catch {
      notify(
        "Clipboard access is unavailable. The template is shown below.",
        "error",
      );
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE / CONFIGURATION"
        title="Settings & integrations"
        description="Your merchant workspace, connected services, and sample data."
        actions={
          <Button
            variant="secondary"
            onClick={() => void health.refetch()}
            disabled={health.isFetching}
          >
            <RefreshCw size={15} className={health.isFetching ? "spin" : ""} />
            Refresh status
          </Button>
        }
      />
      <div className="utility-settings-grid">
        <Panel
          title="Merchant workspace"
          subtitle="A reproducible, synthetic business scenario"
        >
          <div className="utility-merchant">
            <span className="utility-merchant-icon">
              <Store size={26} />
            </span>
            <div>
              <h3>Sharma Kirana Store</h3>
              <p>Wakad, Pune, Maharashtra</p>
            </div>
            <Badge tone="green">SAMPLE MERCHANT</Badge>
          </div>
          <dl className="utility-definition">
            <div>
              <dt>
                <Store size={14} />
                Business category
              </dt>
              <dd>Kirana / Grocery</dd>
            </div>
            <div>
              <dt>
                <Wallet size={14} />
                Currency
              </dt>
              <dd>INR · Indian Rupee</dd>
            </div>
            <div>
              <dt>
                <Languages size={14} />
                Languages
              </dt>
              <dd>हिन्दी · मराठी · English</dd>
            </div>
            <div>
              <dt>
                <ShieldCheck size={14} />
                Customer identity
              </dt>
              <dd>Pseudonymous tokens only</dd>
            </div>
          </dl>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void saveLanguage();
            }}
          >
            <label className="field" style={{ marginTop: 18 }}>
              <span>Default assistant language</span>
              <select
                value={language || h.merchant_language || "hi-IN"}
                onChange={(event) => {
                  setLanguage(event.target.value);
                  setLanguageSaved(false);
                  setLanguageError("");
                }}
              >
                <option value="hi-IN">Hindi · हिन्दी</option>
                <option value="mr-IN">Marathi · मराठी</option>
                <option value="en-IN">English</option>
              </select>
            </label>
            {languageError && (
              <p role="alert" className="field-error">
                {languageError}
              </p>
            )}
            {languageSaved && (
              <p
                role="status"
                className="utility-body"
                style={{ marginTop: 12 }}
              >
                Default language saved. New conversations will use this
                preference.
              </p>
            )}
            <Button
              type="submit"
              variant="secondary"
              disabled={
                savingLanguage || !language || language === h.merchant_language
              }
              style={{ marginTop: 14 }}
            >
              {savingLanguage ? "Saving language…" : "Save language"}
            </Button>
          </form>
        </Panel>
        <Panel
          title="Environment status"
          subtitle="Reported by the running FastAPI backend"
        >
          <div className="utility-service">
            <span className="utility-service-icon">
              <Database size={18} />
            </span>
            <div>
              <strong>Database</strong>
              <small>{h.database}</small>
            </div>
            <Badge tone="green">CONNECTED</Badge>
          </div>
          <div className="utility-service">
            <span className="utility-service-icon">
              <Radio size={18} />
            </span>
            <div>
              <strong>Event distribution</strong>
              <small>
                {h.redis === "connected"
                  ? "Redis connected · persistent audit events"
                  : h.redis.replaceAll("_", " ")}
              </small>
            </div>
            <Badge tone={h.redis === "connected" ? "green" : "amber"}>
              {h.redis === "connected" ? "LIVE" : "FALLBACK"}
            </Badge>
          </div>
          <div className="utility-service">
            <span className="utility-service-icon">
              <Wallet size={18} />
            </span>
            <div>
              <strong>Payment provider</strong>
              <small>No real money moves</small>
            </div>
            <Badge tone="amber">{h.payment_provider.toUpperCase()}</Badge>
          </div>
          <div className="utility-service">
            <span className="utility-service-icon">
              <Globe2 size={18} />
            </span>
            <div>
              <strong>API health</strong>
              <small>Versioned API · /api/v1</small>
            </div>
            <Badge tone={h.status === "ok" ? "green" : "amber"}>
              {h.status.toUpperCase()}
            </Badge>
          </div>
        </Panel>
        <Panel
          title="Sarvam AI"
          subtitle="Speech, language, and document intelligence"
          action={
            <Badge tone={h.sarvam.configured ? "green" : "amber"}>
              {h.sarvam.configured ? "KEY CONFIGURED" : "DEMO RESPONSES"}
            </Badge>
          }
        >
          <p className="utility-body">
            {h.sarvam.configured
              ? "The backend will make genuine provider requests. Model access and availability are reported with each response."
              : "No subscription key is configured. Text workflows use labelled deterministic responses; real speech transcription and synthesis require your Sarvam key."}
          </p>
          <dl className="utility-definition">
            <div>
              <dt>Reasoning</dt>
              <dd>
                <code>{h.sarvam.chat_model}</code>
              </dd>
            </div>
            <div>
              <dt>Speech recognition</dt>
              <dd>
                <code>{h.sarvam.stt_model}</code>
              </dd>
            </div>
            <div>
              <dt>Speech synthesis</dt>
              <dd>
                <code>{h.sarvam.tts_model}</code>
              </dd>
            </div>
          </dl>
          <div className="utility-config">
            <div>
              <KeyRound size={16} />
              <strong>Configure on the backend</strong>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Copy Sarvam configuration template"
                onClick={copyConfiguration}
              >
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </Button>
            </div>
            <pre>
              SARVAM_API_KEY=your_subscription_key
              <br />
              SARVAM_CHAT_MODEL=sarvam-105b
              <br />
              SARVAM_STT_MODEL=saaras:v4
              <br />
              SARVAM_TTS_MODEL=bulbul:v4-flash
            </pre>
            <p>
              Add these to the root <code>.env</code>, then restart the API.
              Your key stays on the server.
            </p>
          </div>
          <a
            className="utility-external"
            href="https://docs.sarvam.ai"
            target="_blank"
            rel="noreferrer"
          >
            Sarvam API documentation <ExternalLink size={13} />
          </a>
        </Panel>
        <Panel
          title="Sample data"
          subtitle="Prepare the workspace for a new presentation"
        >
          <div className="utility-demo-note">
            <span>100</span>
            <div>
              <strong>Synthetic customer profiles</strong>
              <p>
                90 days of purchase history, three seller catalogues, campaign
                experiments, and a deterministic seed.
              </p>
            </div>
          </div>
          <div className="utility-reset-row">
            <div>
              <h3>Restore the original scenario</h3>
              <p>
                Remove sample campaigns, negotiations, orders and activity. The
                application will ask you to confirm.
              </p>
            </div>
            <Button variant="secondary" onClick={onReset}>
              Reset sample data <ChevronRight size={15} />
            </Button>
          </div>
          <div className="utility-safety">
            <ShieldCheck size={18} />
            <p>
              This is a single-merchant local proof of concept. All payment
              states are simulated. No real customer notifications are sent.
            </p>
          </div>
        </Panel>
      </div>
    </>
  );
}
