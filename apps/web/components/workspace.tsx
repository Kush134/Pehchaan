"use client";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Activity,
  ArrowDownUp,
  ArrowUpRight,
  Bell,
  Blocks,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  LayoutDashboard,
  Menu,
  Mic,
  Package,
  Radio,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Store,
  Users,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEventStream, useEvents, useHealth } from "@/lib/hooks";
import { post } from "@/lib/api";
import { useUI } from "@/store/ui";
import { Button } from "./ui/button";
import { EventFeed, Loading, Modal, Toasts } from "./shared";
import { JudgeDemo } from "./judge-demo";
const Dashboard = dynamic(() => import("./pages/dashboard"), {
  loading: Loading,
});
const Comeback = dynamic(() => import("./pages/comeback"), {
  loading: Loading,
});
const Customers = dynamic(() => import("./pages/customers"), {
  loading: Loading,
});
const Haggle = dynamic(() => import("./pages/haggle"), { loading: Loading });
const Agents = dynamic(() => import("./pages/agents"), { loading: Loading });
const Firewall = dynamic(() => import("./pages/firewall"), {
  loading: Loading,
});
const Soundbox = dynamic(() => import("./pages/soundbox"), {
  loading: Loading,
});
const Catalog = dynamic(() => import("./pages/catalog"), { loading: Loading });
const Ledger = dynamic(() => import("./pages/ledger"), { loading: Loading });
const Settings = dynamic(() => import("./pages/settings"), {
  loading: Loading,
});
export const navigation = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "comeback", label: "Comeback Engine", icon: Sparkles },
  { id: "customers", label: "Customer Intelligence", icon: Users },
  { id: "haggle", label: "Haggle Arena", icon: ArrowDownUp },
  { id: "agents", label: "Agent Command Center", icon: Blocks },
  { id: "firewall", label: "Mandate Firewall", icon: ShieldCheck },
  { id: "soundbox", label: "Soundbox Simulator", icon: Mic },
  { id: "catalog", label: "Product Catalogue", icon: Package },
  { id: "ledger", label: "Transaction Ledger", icon: Activity },
  { id: "settings", label: "Settings", icon: Settings2 },
];
export function Workspace({ module }: { module: string }) {
  const [mobile, setMobile] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [days, setDays] = useState(30);
  const router = useRouter();
  const { data: health } = useHealth();
  const { data: events = [] } = useEvents();
  const connected = useEventStream();
  const queryClient = useQueryClient();
  const { notify, setDemoScene } = useUI();
  const reset = async () => {
    setResetting(true);
    try {
      await post("/demo/reset");
      await queryClient.invalidateQueries();
      localStorage.removeItem("pehchaan-session");
      localStorage.removeItem("pehchaan-voice");
      window.dispatchEvent(new Event("pehchaan-workspace-reset"));
      window.dispatchEvent(new Event("pehchaan-session-change"));
      setResetOpen(false);
      notify("Sample workspace restored. 100 customer profiles are ready.");
      router.refresh();
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setResetting(false);
    }
  };
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const current = navigation.find((n) => n.id === module);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <AnimatePresence>
        {mobile && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="sidebar-backdrop"
            onClick={() => setMobile(false)}
            aria-label="Close navigation"
          />
        )}
      </AnimatePresence>
      <aside
        id="workspace-sidebar"
        className={`sidebar ${mobile ? "is-open" : ""}`}
      >
        <Link className="brand" href="/dashboard">
          <span className="brand-symbol">
            <span />
            <span />
            <span />
          </span>
          <span>
            pehchaan<span className="brand-hindi">पहचान</span>
          </span>
        </Link>
        <div className="workspace-label">
          MERCHANT WORKSPACE <span>01</span>
        </div>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger className="merchant-picker">
            <span className="store-icon">
              <Store size={17} />
            </span>
            <span>
              <strong>Sharma Kirana Store</strong>
              <small>Wakad, Pune</small>
            </span>
            <ChevronDown size={14} />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="dropdown merchant-menu">
              <DropdownMenu.Label>Merchant profile</DropdownMenu.Label>
              <DropdownMenu.Label>Sharma Kirana Store · INR</DropdownMenu.Label>
              <DropdownMenu.Label>
                100 pseudonymous customers
              </DropdownMenu.Label>
              <DropdownMenu.Item onSelect={() => router.push("/settings")}>
                View merchant settings <ArrowUpRight size={14} />
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
        <nav aria-label="Main navigation">
          {navigation.map((n, i) => (
            <div key={n.id}>
              {(i === 0 || i === 6) && (
                <div className="nav-group">
                  {i === 0 ? "GROWTH & INTELLIGENCE" : "WORKSPACE"}
                </div>
              )}
              <Link
                href={`/${n.id}`}
                onClick={() => setMobile(false)}
                className={`nav-link ${module === n.id ? "active" : ""}`}
                aria-current={module === n.id ? "page" : undefined}
              >
                {module === n.id && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="nav-active-bg"
                    transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                  />
                )}
                <n.icon size={17} />
                <span>{n.label}</span>
                {n.id === "agents" && <span className="nav-live-dot" />}
                {n.id === "comeback" && <span className="nav-new">AI</span>}
              </Link>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="system-health">
            <span
              className={`status-dot ${health?.status === "ok" ? "" : "muted-dot"}`}
            />
            <span>
              {health?.status === "ok"
                ? "All systems operational"
                : "Connecting to backend"}
            </span>
            <Radio size={13} />
          </div>
          <button className="demo-reset" onClick={() => setResetOpen(true)}>
            Reset sample data <ChevronRight size={13} />
          </button>
          <div className="ecosystem">
            <span>Paytm-ready</span>
            <small>INDEPENDENT PROOF OF CONCEPT</small>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="mobile-menu btn btn-icon btn-ghost"
              aria-label="Open navigation"
              aria-expanded={mobile}
              aria-controls="workspace-sidebar"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span className="desktop-only">Workspace</span>
            <ChevronRight size={13} />
            <strong>{current?.label}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className="search-trigger"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={14} />
              <span>Search workspace</span>
              <kbd>⌘ K</kbd>
            </button>
            <span className="top-divider" />
            <DropdownMenu.Root>
              <DropdownMenu.Trigger
                className="notification-button"
                aria-label="View notifications"
              >
                <Bell size={18} />
                {events.length > 0 && <i />}
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  className="dropdown notifications"
                >
                  <h3>Workspace activity</h3>
                  <EventFeed events={events} limit={5} />
                  <DropdownMenu.Item onSelect={() => router.push("/agents")}>
                    View all execution events <ArrowUpRight size={14} />
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger
                className="avatar"
                aria-label="Open merchant profile"
              >
                SK
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content align="end" className="dropdown">
                  <DropdownMenu.Label>Sharma Kirana Store</DropdownMenu.Label>
                  <DropdownMenu.Label>
                    Merchant · Wakad, Pune
                  </DropdownMenu.Label>
                  <DropdownMenu.Label>
                    Merchant workspace access
                  </DropdownMenu.Label>
                  <DropdownMenu.Label>
                    हिन्दी · मराठी · English
                  </DropdownMenu.Label>
                  <DropdownMenu.Label>
                    All financial actions are simulated
                  </DropdownMenu.Label>
                  <DropdownMenu.Item onSelect={() => router.push("/settings")}>
                    Open settings
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        </header>
        <main id="main" className="main-content">
          <motion.div
            key={module}
            initial={{ opacity: 0, y: 7 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            {module === "dashboard" && (
              <Dashboard
                days={days}
                setDays={setDays}
                onDemo={() => {
                  setDemoScene(0);
                  router.push("/customers");
                }}
              />
            )}
            {module === "comeback" && <Comeback />}
            {module === "customers" && <Customers />}
            {module === "haggle" && <Haggle />}
            {module === "agents" && <Agents />}
            {module === "firewall" && <Firewall />}
            {module === "soundbox" && <Soundbox />}
            {module === "catalog" && <Catalog />}
            {module === "ledger" && <Ledger />}
            {module === "settings" && (
              <Settings onReset={() => setResetOpen(true)} />
            )}
          </motion.div>
          <footer className="workspace-footer">
            <span>
              <span className={`status-dot ${connected ? "" : "muted-dot"}`} />
              {connected
                ? "Live event stream connected"
                : "Event stream reconnecting"}
            </span>
            <span>
              Synthetic merchant data <span>·</span> No real money moves
            </span>
            <span>
              PEHCHAAN <span className="footer-version">v1.0</span>
            </span>
          </footer>
        </main>
      </div>
      <Toasts />
      <JudgeDemo />
      <Modal
        open={searchOpen}
        onOpenChange={setSearchOpen}
        title="Search your workspace"
        description="Open a module or find a pseudonymous customer."
      >
        <div className="search-box">
          <Search size={18} />
          <input
            aria-label="Search modules and customers"
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Try campaigns, customers, or firewall"
          />
        </div>
        <div className="search-results">
          {navigation
            .filter((n) => n.label.toLowerCase().includes(search.toLowerCase()))
            .map((n) => (
              <button
                key={n.id}
                onClick={() => {
                  router.push(`/${n.id}`);
                  setSearchOpen(false);
                }}
              >
                <n.icon size={18} />
                {n.label}
                <ArrowUpRight size={15} />
              </button>
            ))}
          {search && (
            <button
              onClick={() => {
                router.push(`/customers?search=${encodeURIComponent(search)}`);
                setSearchOpen(false);
              }}
            >
              <Users size={18} />
              Search customers for “{search}”<Search size={15} />
            </button>
          )}
        </div>
      </Modal>
      <Modal
        open={resetOpen}
        onOpenChange={setResetOpen}
        title="Reset sample data?"
        description="This restores the seeded dataset and removes demo campaigns, negotiations, orders, and audit events."
      >
        <div className="notice">
          <CircleHelp size={20} />
          <p>
            Only this local demonstration database is affected. Use this before
            a new judge walkthrough.
          </p>
        </div>
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setResetOpen(false)}>
            Keep current data
          </Button>
          <Button variant="destructive" disabled={resetting} onClick={reset}>
            {resetting ? "Resetting…" : "Reset sample data"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
