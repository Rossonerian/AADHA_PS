"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DataBadge } from "@/components/ui";
import type { DashboardData, ExplainResult, Scenario } from "@/lib/types";

export function CompareChart({ data, height = 230 }: { data: { date: string; stock: number; index: number }[]; height?: number }) {
  return <div className="chart-wrap" style={{ height }}><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}><CartesianGrid stroke="#e7e9e4" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#788078", fontSize: 11 }} /><YAxis hide domain={["dataMin - 8", "dataMax + 8"]} /><Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e7e9e4", boxShadow: "0 12px 30px #1c2b1b14" }} /><Line type="monotone" dataKey="stock" name="Company" stroke="#315c4c" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} /><Line type="monotone" dataKey="index" name="Index" stroke="#b2a16c" strokeWidth={2} strokeDasharray="5 5" dot={false} /></LineChart></ResponsiveContainer></div>;
}

export function DashboardCharts({ data }: { data: DashboardData }) {
  const skillKeys = ["basics", "reading_stock", "judging_info", "risk"] as const;
  const colors = ["#315c4c", "#6d8d75", "#b59a5a", "#b27663"];
  return <div className="chart-grid">
    <div className="chart-card"><div className="chart-title"><div><span className="eyebrow">SKILLS OVER TIME</span><h3>Your progress, week by week</h3></div><DataBadge origin={data.data_origin} /></div><div className="chart-wrap" style={{ height: 240 }}><ResponsiveContainer width="100%" height="100%"><LineChart data={data.skills_over_time} margin={{ top: 12, right: 8, left: -22, bottom: 0 }}><CartesianGrid stroke="#e7e9e4" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#788078", fontSize: 11 }} /><YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#788078", fontSize: 11 }} /><Tooltip /><>{skillKeys.map((key, index) => <Line key={key} type="monotone" dataKey={key} name={key.replace("_", " ")} stroke={colors[index]} strokeWidth={2.4} dot={false} />)}</></LineChart></ResponsiveContainer></div><div className="chart-legend">{skillKeys.map((key, index) => <span key={key}><i style={{ background: colors[index] }} />{key.replace("_", " ")}</span>)}</div></div>
    <div className="chart-card"><div className="chart-title"><div><span className="eyebrow">CONFIDENCE CALIBRATION</span><h3>How close were your calls?</h3></div><DataBadge origin={data.data_origin} /></div><div className="chart-wrap" style={{ height: 240 }}><ResponsiveContainer width="100%" height="100%"><LineChart data={data.brier_over_time} margin={{ top: 12, right: 8, left: -22, bottom: 0 }}><CartesianGrid stroke="#e7e9e4" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#788078", fontSize: 11 }} /><YAxis domain={[0, 0.5]} axisLine={false} tickLine={false} tick={{ fill: "#788078", fontSize: 11 }} /><Tooltip formatter={(value) => Number(value).toFixed(2)} /><Line type="monotone" dataKey="brier" name="Brier score" stroke="#b27663" strokeWidth={2.8} dot={{ r: 3, fill: "#b27663" }} /></LineChart></ResponsiveContainer></div><p className="chart-note">A smaller score means your stated confidence has matched outcomes more closely.</p></div>
  </div>;
}

export function ScenarioChart({ scenario }: { scenario: Scenario }) { return <CompareChart data={scenario.context.chart} height={260} />; }
export function ExplainChart({ data }: { data: ExplainResult }) { return <CompareChart data={data.chart} height={260} />; }
