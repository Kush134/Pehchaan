"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Fingerprint,
  Mic,
  Play,
  ShieldCheck,
  ShoppingBasket,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Agent, Event } from "@/types";
import {
  Badge,
  ErrorState,
  EventFeed,
  Loading,
  PageTitle,
  Panel,
} from "../shared";
import { Button } from "../ui/button";
type AgentNode = Node<{ agent: Agent }, "agent">;
const icons: Record<string, typeof Bot> = {
  comeback: Sparkles,
  "customer-intelligence": Users,
  voice: Mic,
  buyer: ShoppingBasket,
  firewall: ShieldCheck,
  payment: Wallet,
  analytics: Activity,
};
function AgentCard({ data, selected }: NodeProps<AgentNode>) {
  const a = data.agent;
  const Icon = icons[a.id] || Bot;
  return (
    <div
      className={`flow-agent ${a.status === "running" ? "running" : ""} ${selected ? "selected" : ""}`}
    >
      <Handle type="target" position={Position.Left} />
      <div className="flow-agent-top">
        <span className={`flow-icon ${a.id === "firewall" ? "amber" : ""}`}>
          <Icon size={17} />
        </span>
        <span className={`flow-status ${a.status}`}>{a.status}</span>
      </div>
      <strong>{a.name}</strong>
      <p>{a.current_task}</p>
      <div className="flow-agent-bottom">
        <span>{a.tool_calls} events</span>
        <span>{a.duration_ms ? `${a.duration_ms}ms` : "Ready"}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { agent: AgentCard };
const positions: Record<string, { x: number; y: number }> = {
  "customer-intelligence": { x: 0, y: 0 },
  comeback: { x: 230, y: 0 },
  voice: { x: 0, y: 180 },
  buyer: { x: 230, y: 190 },
  "seller-a": { x: 460, y: 0 },
  "seller-b": { x: 460, y: 180 },
  "seller-c": { x: 460, y: 360 },
  supervisor: { x: 690, y: 180 },
  firewall: { x: 920, y: 180 },
  payment: { x: 920, y: 360 },
  analytics: { x: 690, y: 360 },
};
const connections = [
  ["customer-intelligence", "comeback"],
  ["voice", "comeback"],
  ["voice", "buyer"],
  ["buyer", "seller-a"],
  ["buyer", "seller-b"],
  ["buyer", "seller-c"],
  ["seller-a", "supervisor"],
  ["seller-b", "supervisor"],
  ["seller-c", "supervisor"],
  ["supervisor", "firewall"],
  ["firewall", "payment"],
  ["payment", "analytics"],
  ["comeback", "analytics"],
];
export default function Agents() {
  const [selected, setSelected] = useState<string | null>(null);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api<{ agents: Agent[]; events: Event[] }>("/agents/status"),
    refetchInterval: 2000,
  });
  const nodes = useMemo<AgentNode[]>(
    () =>
      data?.agents.map((agent) => ({
        id: agent.id,
        type: "agent",
        position: positions[agent.id] || { x: 0, y: 0 },
        data: { agent },
        selected: agent.id === selected,
      })) || [],
    [data, selected],
  );
  const edges = useMemo<Edge[]>(
    () =>
      connections.map(([source, target]) => ({
        id: `${source}-${target}`,
        source,
        target,
        animated: data?.agents.some(
          (a) => a.id === target && a.status === "running",
        ),
        style: {
          stroke: data?.agents.some(
            (a) => a.id === target && a.status === "running",
          )
            ? "var(--chart-primary)"
            : "var(--border-strong)",
          strokeWidth: 1.4,
        },
        type: "smoothstep",
      })),
    [data],
  );
  if (isLoading) return <Loading />;
  if (error || !data)
    return (
      <ErrorState
        error={error || new Error("No agents found")}
        retry={() => void refetch()}
      />
    );
  const active = data.agents.find((a) => a.id === selected);
  return (
    <>
      <PageTitle
        eyebrow="LIVE AGENT OPERATING SYSTEM"
        title="Agent Command Center"
        description="Watch your workflows execute. Every node is backed by real application events."
        actions={
          <Button asChild variant="secondary">
            <Link href="/haggle">
              <Play size={14} />
              Run a negotiation <ArrowUpRight size={14} />
            </Link>
          </Button>
        }
      />
      <div className="command-status-bar">
        <span>
          <span className="status-dot" />
          WORKSPACE ONLINE
        </span>
        <div>
          <span>
            <strong>{data.agents.length}</strong> registered agents
          </span>
          <span>
            <strong>
              {data.agents.filter((a) => a.status === "running").length}
            </strong>{" "}
            executing
          </span>
          <span>
            <strong>{data.events.length}</strong> recent events
          </span>
          <Badge tone="green">
            <Fingerprint size={12} />
            AUDIT LOG ENABLED
          </Badge>
        </div>
      </div>
      <section className="command-graph">
        <div className="graph-header">
          <div>
            <span className="graph-live-light" />
            PEHCHAAN EXECUTION NETWORK
          </div>
          <span>Click a node to inspect its latest action</span>
        </div>
        <div className="graph-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.1 }}
            minZoom={0.35}
            maxZoom={1.5}
            nodesDraggable={false}
            nodesConnectable={false}
            onNodeClick={(_, node) => setSelected(node.id)}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              color="var(--chart-grid)"
              gap={18}
              size={1}
            />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <div className="graph-legend">
          <span>
            <i className="mint-dot" />
            Executing
          </span>
          <span>
            <i />
            Ready / completed
          </span>
          <span>
            <ShieldCheck size={13} />
            Financial actions require deterministic validation
          </span>
        </div>
      </section>
      <div className="two-column">
        <Panel
          title={active ? active.name : "Execution timeline"}
          subtitle={
            active
              ? "Selected agent · Latest recorded activity"
              : "Action summaries and tool events. No hidden model reasoning."
          }
          action={
            active ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelected(null)}
              >
                View all events
              </Button>
            ) : (
              <Badge>LIVE</Badge>
            )
          }
        >
          {active ? (
            <>
              <div className="selected-agent-detail">
                <Badge tone={active.status === "running" ? "green" : "default"}>
                  {active.status}
                </Badge>
                <h3>{active.current_task}</h3>
                <p>{active.last_action}</p>
                <div>
                  <span>
                    Execution duration<strong>{active.duration_ms} ms</strong>
                  </span>
                  <span>
                    Recorded tool events<strong>{active.tool_calls}</strong>
                  </span>
                </div>
              </div>
              <EventFeed
                events={data.events.filter((e) => e.agent === selected)}
                limit={6}
              />
            </>
          ) : (
            <EventFeed events={data.events} limit={7} />
          )}
        </Panel>
        <Panel
          title="Agent registry"
          subtitle="Purpose, status, and recorded tool activity"
        >
          <div className="agent-registry">
            {data.agents.map((a) => {
              const Icon = icons[a.id] || Bot;
              return (
                <button
                  key={a.id}
                  onClick={() => setSelected(a.id)}
                  className={selected === a.id ? "selected" : ""}
                >
                  <span>
                    <Icon size={15} />
                    {a.name}
                  </span>
                  <Badge tone={a.status === "running" ? "green" : "default"}>
                    {a.status}
                  </Badge>
                  <small>{a.tool_calls} events</small>
                </button>
              );
            })}
          </div>
        </Panel>
      </div>
    </>
  );
}
