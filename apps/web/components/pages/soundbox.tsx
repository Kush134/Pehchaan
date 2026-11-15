"use client";
import Link from "next/link";
import SmsPanel from "./sms";
import BusinessCopilot from "./business-copilot";
import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  Check,
  ChevronRight,
  Globe2,
  Loader2,
  Mic,
  MicOff,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, post } from "@/lib/api";
import { useHealth } from "@/lib/hooks";
import { useUI } from "@/store/ui";
import type { VoiceResult } from "@/types";
import { Badge, PageTitle, Panel } from "../shared";
import { Button } from "../ui/button";
type Message = { role: "user" | "assistant"; text: string; provider?: string };
export default function Soundbox() {
  const [language, setLanguage] = useState("hi-IN");
  const [preferredLanguage, setPreferredLanguage] = useState("hi-IN");
  const [input, setInput] = useState("");
  const [startedNegotiation, setStartedNegotiation] = useState<string | null>(
    null,
  );
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [result, setResult] = useState<VoiceResult | null>(null);
  const [busy, setBusy] = useState("restore");
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [audio, setAudio] = useState<string | null>(null);
  const [autoVoice, setAutoVoice] = useState(true);
  const recorder = useRef<MediaRecorder | null>(null);
  const tracks = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const started = useRef(0);
  const audioUrl = useRef<string | null>(null);
  const conversationVersion = useRef(0);
  const notify = useUI((s) => s.notify);
  const { data: health } = useHealth();
  const client = useQueryClient();
  useEffect(() => {
    let active = true;
    const version = conversationVersion.current;
    const restore = async () => {
      const saved = localStorage.getItem("pehchaan-voice");
      const preferences = await api<{ merchant_language: string }>(
        "/settings/integrations",
      ).catch(() => null);
      const preferred = preferences?.merchant_language || "hi-IN";
      if (!active || conversationVersion.current !== version) return;
      setPreferredLanguage(preferred);
      if (!saved) {
        setLanguage(preferred);
        return;
      }
      try {
        const history = await api<{
          session_id: string;
          language?: string;
          messages: Message[];
          proposal:
            | (NonNullable<VoiceResult["proposal"]> & { expires_at?: string })
            | null;
        }>(`/voice/history?session_id=${encodeURIComponent(saved)}`);
        if (!active || conversationVersion.current !== version) return;
        setSessionId(history.session_id);
        setMessages(history.messages);
        if (history.language) setLanguage(history.language);
        const proposal = history.proposal;
        if (proposal?.status === "pending_approval") {
          if (
            proposal.expires_at &&
            new Date(proposal.expires_at).getTime() <= Date.now()
          ) {
            setError(
              "Your saved proposal has expired. Ask for a new proposal before approving an action.",
            );
          } else {
            const previous = history.messages
              .filter((message) => message.role === "assistant")
              .at(-1);
            setResult({
              session_id: history.session_id,
              transcript: "",
              response: previous?.text || "",
              proposal,
              provider: previous?.provider || "demo",
              demo: previous?.provider !== "sarvam",
            });
          }
        }
      } catch (failure) {
        if (!active || conversationVersion.current !== version) return;
        if (failure instanceof ApiError && failure.status === 404) {
          localStorage.removeItem("pehchaan-voice");
          setLanguage(preferred);
          setError(
            "The saved conversation is no longer available. You can start a new conversation.",
          );
        } else {
          setSessionId(saved);
          setError(
            "The saved conversation could not be loaded. Reload to try restoring its messages again.",
          );
        }
      }
    };
    void restore().finally(() => {
      if (active && conversationVersion.current === version) setBusy("");
    });
    const resetConversation = () => {
      conversationVersion.current += 1;
      if (timer.current) clearInterval(timer.current);
      if (recorder.current?.state === "recording") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      tracks.current?.getTracks().forEach((track) => track.stop());
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = null;
      setRecording(false);
      setBusy("");
      setSessionId(undefined);
      setMessages([]);
      setResult(null);
      setInput("");
      setError("");
      setAudio(null);
      setStartedNegotiation(null);
      setLanguage("hi-IN");
      setPreferredLanguage("hi-IN");
    };
    window.addEventListener("pehchaan-workspace-reset", resetConversation);
    return () => {
      active = false;
      window.removeEventListener("pehchaan-workspace-reset", resetConversation);
    };
  }, []);
  const newConversation = () => {
    conversationVersion.current += 1;
    localStorage.removeItem("pehchaan-voice");
    setSessionId(undefined);
    setLanguage(preferredLanguage);
    setMessages([]);
    setResult(null);
    setInput("");
    setError("");
    setStartedNegotiation(null);
    if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    audioUrl.current = null;
    setAudio(null);
    notify("New conversation ready. Your earlier conversation remains saved.");
  };
  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
      tracks.current?.getTracks().forEach((t) => t.stop());
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    },
    [],
  );
  const speak = async (text: string) => {
    try {
      const speech = await post<{
        audio_base64: string | null;
        mime_type: string;
        provider: string;
        demo: boolean;
        error?: string;
      }>("/voice/synthesize", { text, language });
      if (!speech.audio_base64) {
        setError(
          speech.error ||
            "Speech provider unavailable. The text response is ready.",
        );
        return;
      }
      const bytes = Uint8Array.from(atob(speech.audio_base64), (c) =>
        c.charCodeAt(0),
      );
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      const url = URL.createObjectURL(
        new Blob([bytes], { type: speech.mime_type || "audio/wav" }),
      );
      audioUrl.current = url;
      setAudio(url);
    } catch (e) {
      setError(`Audio response: ${(e as Error).message}`);
    }
  };
  const send = async (text = input) => {
    if (!text.trim() || busy) return;
    setBusy("chat");
    setError("");
    setInput("");
    setMessages((old) => [...old, { role: "user", text }]);
    const version = conversationVersion.current;
    try {
      const reply = await post<VoiceResult>("/voice/chat", {
        text,
        language,
        session_id: sessionId,
      });
      if (conversationVersion.current !== version) return;
      setSessionId(reply.session_id);
      localStorage.setItem("pehchaan-voice", reply.session_id);
      setResult(reply);
      setMessages((old) => [
        ...old,
        { role: "assistant", text: reply.response, provider: reply.provider },
      ]);
      if (reply.error) setError(reply.error);
      if (autoVoice) await speak(reply.response);
      await client.invalidateQueries();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const approve = async (approved: boolean) => {
    if (!result?.proposal) return;
    setBusy("approve");
    try {
      const response = await post<{
        response?: string;
        message?: string;
        status?: string;
        action?: string;
        session_id?: string;
      }>("/voice/approve", {
        session_id: sessionId,
        proposal_id: result.proposal.id,
        approved,
      });
      setResult((old) => (old ? { ...old, proposal: null } : null));
      if (
        approved &&
        response.action === "start_negotiation" &&
        response.session_id
      ) {
        localStorage.setItem("pehchaan-session", response.session_id);
        window.dispatchEvent(new Event("pehchaan-session-change"));
        setStartedNegotiation(response.session_id);
      }
      const text =
        response.response ||
        response.message ||
        (approved
          ? "The approved action has been executed."
          : "Proposal declined. No action was executed.");
      setMessages((old) => [...old, { role: "assistant", text }]);
      await client.invalidateQueries();
      notify(
        approved
          ? "Approved action executed and recorded."
          : "Proposal declined.",
      );
      if (autoVoice) await speak(text);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const stop = () => {
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (timer.current) clearInterval(timer.current);
    setRecording(false);
  };
  const start = async () => {
    setError("");
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      setError(
        "Audio recording is unavailable in this browser. Use the text command below.",
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      tracks.current = stream;
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(
        (m) => MediaRecorder.isTypeSupported(m),
      );
      const rec = new MediaRecorder(
        stream,
        mime ? { mimeType: mime } : undefined,
      );
      recorder.current = rec;
      const chunks: BlobPart[] = [];
      rec.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const duration = Math.min(
          (performance.now() - started.current) / 1000,
          30,
        );
        setBusy("transcribe");
        try {
          const blob = new Blob(chunks, { type: rec.mimeType });
          if (blob.size > 10 * 1024 * 1024)
            throw new Error(
              "Recording exceeds the 10 MB upload limit. Record a shorter command.",
            );
          const data = new FormData();
          data.append(
            "file",
            blob,
            rec.mimeType.includes("mp4") ? "command.m4a" : "command.webm",
          );
          data.append("language", language);
          data.append("duration_seconds", String(duration));
          const transcription = await api<{
            transcript: string;
            demo: boolean;
            provider: string;
            error?: string;
          }>("/voice/transcribe", { method: "POST", body: data });
          if (!transcription.transcript)
            throw new Error(
              transcription.error ||
                "No speech was recognized. Try again or use text.",
            );
          setInput(transcription.transcript);
          await send(transcription.transcript);
          if (transcription.error) setError(transcription.error);
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy("");
        }
      };
      started.current = performance.now();
      setSeconds(0);
      rec.start(250);
      setRecording(true);
      timer.current = setInterval(() => {
        const elapsed = Math.floor(
          (performance.now() - started.current) / 1000,
        );
        setSeconds(elapsed);
        if (elapsed >= 29) {
          stop();
          notify(
            "Recording completed within the 30-second limit. Transcribing your command.",
          );
        }
      }, 250);
    } catch {
      setError(
        "Microphone permission was denied or no audio device was found. You can type the same command below.",
      );
    }
  };
  const phrases =
    language === "mr-IN"
      ? [
          "कोण 14 दिवसांपासून आले नाही?",
          "मागील आठवड्यात सर्वाधिक काय विकले?",
          "कोणता माल एक्सपायर होणार?",
          "₹15 सूट आणि ₹250 किमान बिलाची मोहीम तयार करा",
          "घाऊक वाटाघाटी सुरू करा",
        ]
      : language === "hi-IN"
        ? [
            "कौन 14 दिन से नहीं आया?",
            "पिछले हफ्ते सबसे ज्यादा क्या बिका?",
            "कौन सा माल एक्सपायर होने वाला है?",
            "2 किलो चावल और 1 पैकेट बिस्कुट बेचा",
            "₹15 discount और ₹250 minimum bill की campaign बनाओ",
            "Bulk negotiation शुरू करो",
          ]
        : [
            "Who has not visited in 14 days?",
            "What sold best last week?",
            "Which goods expire soon?",
            "Record sale: 2 kg rice and 1 packet biscuit sold",
            "Create a retention campaign: ₹15 off a ₹250 minimum bill",
            "Start bulk negotiation",
          ];
  return (
    <>
      <PageTitle
        eyebrow="SARVAM-POWERED MERCHANT ASSISTANT"
        title="Your business. In your own words."
        description="Speak in Hindi or Marathi. Review every proposed change before it happens."
        actions={
          <>
            <Button
              variant="secondary"
              disabled={!!busy || recording}
              onClick={newConversation}
            >
              <Plus size={14} />
              New conversation
            </Button>
            <Badge tone={health?.sarvam.configured ? "green" : "amber"}>
              {health?.sarvam.configured
                ? "SARVAM CONNECTED"
                : "DEMO TEXT ASSISTANT"}
            </Badge>
          </>
        }
      />
      <div className="soundbox-layout">
        <section className="soundbox-stage">
          <div className="soundbox-stage-top">
            <span>
              <span className="status-dot" />
              SOUNDBOX SIMULATOR
            </span>
            <Badge>VIRTUAL DEVICE</Badge>
          </div>
          <div className={`soundbox-device ${recording ? "recording" : ""}`}>
            <div className="device-top">
              <span className="device-logo">
                pehchaan<span>पहचान</span>
              </span>
              <span className="device-wifi">
                <i />
                <i />
                <i />
              </span>
            </div>
            <div className="device-screen">
              <span>
                {recording
                  ? "LISTENING"
                  : busy === "transcribe"
                    ? "TRANSCRIBING"
                    : "आपका व्यापार साथी"}
              </span>
              <div className="device-wave">
                {Array.from({ length: 27 }, (_, i) => (
                  <motion.i
                    key={i}
                    animate={
                      recording
                        ? { scaleY: [0.2, 0.5 + (i % 5) / 5, 0.2] }
                        : { scaleY: 0.15 + (Math.sin(i) * 0.15 + 0.2) }
                    }
                    transition={
                      recording
                        ? { repeat: Infinity, duration: 0.6 + (i % 4) * 0.15 }
                        : undefined
                    }
                  />
                ))}
              </div>
              <strong>
                {recording
                  ? `${seconds.toString().padStart(2, "0")} / 30s`
                  : "नमस्ते, शर्मा जी"}
              </strong>
              <small>
                {recording
                  ? "Tap to finish your command"
                  : "Your next payment starts here."}
              </small>
            </div>
            <div className="speaker-grille">
              {Array.from({ length: 84 }, (_, i) => (
                <i key={i} />
              ))}
            </div>
            <button
              aria-label={
                recording ? "Stop recording" : "Start microphone recording"
              }
              className={`device-mic ${recording ? "active" : ""}`}
              disabled={!!busy}
              onClick={() => (recording ? stop() : void start())}
            >
              {busy ? (
                <Loader2 size={23} className="spin" />
              ) : recording ? (
                <Square fill="currentColor" size={19} />
              ) : (
                <Mic size={24} />
              )}
            </button>
            <span className="device-bottom-label">POWERED BY SARVAM AI</span>
          </div>
          <div className="soundbox-instructions">
            <strong>
              {recording
                ? "Listening to your command…"
                : busy === "transcribe"
                  ? "Converting speech to text…"
                  : "Tap the microphone to begin"}
            </strong>
            <span>Up to 30 seconds · Hindi, Marathi & English</span>
          </div>
          <div className="device-disclaimer">
            <ShieldCheck size={14} />
            <span>A virtual demo device. Not connected to Paytm hardware.</span>
          </div>
        </section>
        <div className="soundbox-conversation">
          <Panel
            title="Merchant conversation"
            subtitle={
              sessionId
                ? "Saved conversation · Your approval stays explicit"
                : "Your words become a validated proposal"
            }
            action={
              <label className="language-picker">
                <Globe2 size={14} />
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  aria-label="Assistant language"
                  disabled={recording}
                >
                  <option value="hi-IN">हिन्दी</option>
                  <option value="mr-IN">मराठी</option>
                  <option value="en-IN">English</option>
                </select>
              </label>
            }
          >
            <div className="conversation-messages" aria-live="polite">
              {!messages.length ? (
                <div className="assistant-welcome">
                  <span className="ai-mark">
                    <Sparkles size={22} />
                  </span>
                  <h3>Namaste, Sharma ji.</h3>
                  <p>
                    Ask about your business, adjust a retention offer, or start
                    a bulk negotiation.
                  </p>
                  <div className="suggested-prompts">
                    {phrases.map((p) => (
                      <button
                        key={p}
                        disabled={!!busy}
                        onClick={() => void send(p)}
                      >
                        {p}
                        <ChevronRight size={14} />
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((m, i) => (
                  <div className={`chat-message ${m.role}`} key={i}>
                    <span className="chat-avatar">
                      {m.role === "assistant" ? <Sparkles size={15} /> : "SK"}
                    </span>
                    <div>
                      <small>
                        {m.role === "assistant" ? "PEHCHAAN ASSISTANT" : "YOU"}

                      </small>
                      <p>{m.text}</p>
                    </div>
                  </div>
                ))
              )}
              {busy === "restore" && (
                <div className="chat-thinking">
                  <Loader2 size={15} className="spin" />
                  Restoring saved conversation…
                </div>
              )}
              {busy === "chat" && (
                <div className="chat-thinking">
                  <Loader2 size={15} className="spin" />
                  Interpreting your command…
                </div>
              )}
            </div>
            {result?.proposal?.status === "pending_approval" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="voice-proposal"
              >
                <div>
                  <ShieldCheck size={18} />
                  <strong>Action awaiting your approval</strong>
                  <Badge tone="amber">REVIEW REQUIRED</Badge>
                </div>
                <h3>{result.proposal.action === "send_comeback_offer" ? "Send comeback SMS to Kush" : result.proposal.action.replaceAll("_", " ")}</h3>
                {result.proposal.action === "send_comeback_offer" && <p className="checkout-note">Say “Haan” or “Yes” in this conversation to approve this exact offer, or use the approval button. Then watch SMS delivery and offer acceptance below.</p>}
                <dl>
                  {Object.entries(result.proposal.parameters)
                    .filter(([, v]) => typeof v !== "object")
                    .map(([k, v]) => (
                      <div key={k}>
                        <dt>{k.replaceAll("_", " ")}</dt>
                        <dd>{String(v)}</dd>
                      </div>
                    ))}
                </dl>
                <div className="proposal-actions">
                  <Button
                    size="sm"
                    disabled={!!busy}
                    onClick={() => void approve(true)}
                  >
                    <Check size={14} />
                    Approve action
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!!busy}
                    onClick={() => void approve(false)}
                  >
                    <X size={14} />
                    Decline
                  </Button>
                </div>
              </motion.div>
            )}
            {startedNegotiation && (
              <div className="notice compact">
                <ShieldCheck size={16} />
                <p>
                  Your approved buyer agent is negotiating.{" "}
                  <Link className="text-link" href="/haggle">
                    View live negotiation →
                  </Link>
                </p>
              </div>
            )}
            {error && (
              <div role="alert" className="voice-error">
                <MicOff size={16} />
                <span>{error}</span>
                <button
                  aria-label="Dismiss voice error"
                  onClick={() => setError("")}
                >
                  <X size={13} />
                </button>
              </div>
            )}
            <form
              className="command-input"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <input
                aria-label="Merchant command"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  language === "mr-IN"
                    ? "तुमचा प्रश्न इथे लिहा…"
                    : language === "hi-IN"
                      ? "अपना सवाल यहाँ लिखें…"
                      : "Type a merchant command…"
                }
                disabled={recording}
              />
              <Button
                size="icon"
                type="submit"
                aria-label="Send command"
                disabled={!input.trim() || !!busy || recording}
              >
                {busy ? (
                  <Loader2 size={17} className="spin" />
                ) : (
                  <Send size={17} />
                )}
              </Button>
            </form>
            <div className="conversation-bottom">
              <label>
                <input
                  type="checkbox"
                  checked={autoVoice}
                  onChange={(e) => setAutoVoice(e.target.checked)}
                />
                <Volume2 size={13} />
                Spoken responses
              </label>
              <span>Actions require your explicit approval</span>
            </div>
            {audio && (
              <div className="audio-response">
                <Volume2 size={16} />
                <audio
                  controls
                  autoPlay
                  src={audio}
                  aria-label="Sarvam spoken response"
                />
              </div>
            )}
          </Panel>
        </div>
      </div>
      <BusinessCopilot onAsk={(text)=>void send(text)} />
      <SmsPanel compact />
      <div className="voice-pipeline">
        {[
          { n: "01", title: "Hear", subtitle: "Saaras v4 speech recognition" },
          {
            n: "02",
            title: "Understand",
            subtitle: "Sarvam-105B structured proposal",
          },
          {
            n: "03",
            title: "Approve",
            subtitle: "Human approval + policy validation",
          },
          {
            n: "04",
            title: "Respond",
            subtitle: "Bulbul v4 Flash voice synthesis",
          },
        ].map((p, i) => (
          <div key={p.n}>
            <span>{p.n}</span>
            <div>
              <strong>{p.title}</strong>
              <small>{p.subtitle}</small>
            </div>
            {i < 3 && <ChevronRight size={15} />}
          </div>
        ))}
      </div>
    </>
  );
}
