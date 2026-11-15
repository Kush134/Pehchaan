import { notFound } from "next/navigation";
import { Workspace } from "@/components/workspace";
const modules = [
  "dashboard",
  "comeback",
  "customers",
  "haggle",
  "agents",
  "firewall",
  "soundbox",
  "catalog",
  "ledger",
  "settings",
];
export function generateStaticParams() {
  return modules.map((module) => ({ module }));
}
export default async function Page({
  params,
}: {
  params: Promise<{ module: string }>;
}) {
  const { module } = await params;
  if (!modules.includes(module)) notFound();
  return <Workspace module={module} />;
}
