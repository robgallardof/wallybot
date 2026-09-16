import { notFound } from "next/navigation";
import Application from "../client";

const sections = [
  "setup",
  "login",
  "dashboard",
  "portfolio",
  "connections",
  "markets",
  "intelligence",
  "research",
  "risk",
  "events",
  "system",
  "settings",
  "docs",
];

export default async function Page({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (!sections.includes(section)) notFound();
  return <Application />;
}
