import { notFound } from "next/navigation";
import Application from "../client";

const sections = [
  "setup",
  "login",
  "dashboard",
  "portfolio",
  "markets",
  "intelligence",
  "research",
  "risk",
  "events",
  "system",
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
