"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DataBadge } from "@/components/ui";
import { chartHasIndex } from "@/components/lazy/chart-utils";
import type { DashboardData, ExplainResult, PricePoint, Scenario } from "@/lib/types";

const tooltipStyle = {
  contentStyle: {
    borderRadius: 12,
    border: "1px solid var(--line)",
    background: "var(--paper)",
    color: "var(--ink)",
    boxShadow: "0 12px 30px rgba(0,0,0,0.18)",
    fontSize: 12,
  },
  labelStyle: { color: "var(--ink)", fontWeight: 600 },
  itemStyle: { color: "var(--ink)" },
  cursor: { stroke: "var(--line)" },
} as const;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/;
const axisTick = { fill: "var(--ink-soft)", fontSize: 12 } as const;

function parseIso(value: unknown) {
  const m = typeof value === "string" ? ISO_DATE.exec(value) : null;
  return m ? { y: Number(m[1]), m: Number(m[2]) - 1, d: Number(m[3]) } : null;
}

/** "2026-03-14" -> "14 Mar"; month-start series -> "Mar 2026"; non-dates pass through. */
function makeDateTick(values: unknown[]) {
  const parsed = values.map(parseIso);
  const monthly = parsed.length > 0 && parsed.every((p) => p && p.d === 1);
  return (value: unknown) => {
    const p = parseIso(value);
    if (!p) return String(value);
    return monthly ? `${MONTHS[p.m]} ${p.y}` : `${p.d} ${MONTHS[p.m]}`;
  };
}

function fullDate(value: unknown) {
  const p = parseIso(value);
  return p ? `${p.d} ${MONTHS[p.m]} ${p.y}` : String(value);
}

function EmptyChart({ height }: { height: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-lg border border-dashed border-[var(--line)] px-4 text-center text-sm text-[var(--ink-soft)]"
      style={{ height }}
    >
      Your progress will appear here after your first assessment.
    </div>
  );
}

export function CompareChart({ data, height = 230 }: { data: PricePoint[]; height?: number }) {
  const hasIndex = chartHasIndex(data);
  const tickFormatter = makeDateTick(data.map((p) => p.date));
  return (
    <div className="chart-wrap" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={axisTick}
            tickMargin={8}
            padding={{ left: 12, right: 12 }}
            minTickGap={24}
            tickFormatter={tickFormatter}
          />
          <YAxis
            width={44}
            axisLine={false}
            tickLine={false}
            tick={axisTick}
            tickMargin={6}
            tickCount={4}
            allowDecimals={false}
            domain={[
              (min: number) => Math.floor(min - Math.max(1, min * 0.02)),
              (max: number) => Math.ceil(max + Math.max(1, max * 0.02)),
            ]}
          />
          <Tooltip {...tooltipStyle} labelFormatter={fullDate} />
          <Line
            isAnimationActive={false}
            type="monotone"
            dataKey="close"
            name="Company close"
            stroke="var(--green)"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4 }}
          />
          {hasIndex ? (
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="index"
              name="Index"
              stroke="var(--ink-soft)"
              strokeWidth={1.8}
              strokeDasharray="5 4"
              dot={false}
            />
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DashboardCharts({ data }: { data: DashboardData }) {
  const skillKeys = ["basics", "reading_stock", "judging_info", "risk"] as const;
  const colors = ["var(--green)", "#3b8bd0", "#d19a2a", "#cf5f5f"];
  const dashes = [undefined, "6 3", "2 3", "10 3 2 3"];
  const skillsOverTime = data.skills_over_time.map((point) => ({
    date: point.date,
    ...point.skills,
  }));
  return (
    <div className="chart-grid">
      <div className="chart-card">
        <div className="chart-title">
          <div>
            <span className="eyebrow">SKILLS OVER TIME</span>
            <h3>Your progress, week by week</h3>
          </div>
          <DataBadge origin={data.data_origin} />
        </div>
        {skillsOverTime.length === 0 ? (
          <EmptyChart height={240} />
        ) : (
          <div className="chart-wrap" style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={skillsOverTime} margin={{ top: 12, right: 8, left: 4, bottom: 4 }}>
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 5" vertical={false} />
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={axisTick}
                  tickMargin={8}
                  padding={{ left: 12, right: 12 }}
                  tickFormatter={makeDateTick(skillsOverTime.map((p) => p.date))}
                />
                <YAxis
                  width={40}
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  axisLine={false}
                  tickLine={false}
                  tick={axisTick}
                  tickMargin={6}
                />
                <Tooltip {...tooltipStyle} labelFormatter={fullDate} />
                {skillKeys.map((key, index) => (
                  <Line
                    isAnimationActive={false}
                    key={key}
                    type="monotone"
                    dataKey={key}
                    name={key.replace("_", " ")}
                    stroke={colors[index]}
                    strokeWidth={2.4}
                    strokeDasharray={dashes[index]}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <div
          className="chart-legend"
          hidden={skillsOverTime.length === 0}
          style={{ fontSize: 12, gap: 14 }}
        >
          {skillKeys.map((key, index) => (
            <span key={key} style={{ fontSize: 12, gap: 6 }}>
              <i style={{ background: colors[index], width: 9, height: 9 }} />
              {key.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>
      <div className="chart-card">
        <div className="chart-title">
          <div>
            <span className="eyebrow">CONFIDENCE CALIBRATION</span>
            <h3>How close were your calls?</h3>
          </div>
          <DataBadge origin={data.data_origin} />
        </div>
        {data.brier_over_time.length === 0 ? (
          <EmptyChart height={240} />
        ) : (
          <div className="chart-wrap" style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.brier_over_time}
                margin={{ top: 12, right: 8, left: 4, bottom: 4 }}
              >
                <CartesianGrid stroke="var(--line)" strokeDasharray="3 5" vertical={false} />
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={axisTick}
                  tickMargin={8}
                  padding={{ left: 12, right: 12 }}
                  tickFormatter={makeDateTick(data.brier_over_time.map((p) => p.date))}
                />
                <YAxis
                  width={40}
                  domain={[0, 0.5]}
                  ticks={[0, 0.1, 0.2, 0.3, 0.4, 0.5]}
                  tickFormatter={(v: number) => v.toFixed(1)}
                  axisLine={false}
                  tickLine={false}
                  tick={axisTick}
                  tickMargin={6}
                />
                <Tooltip
                  {...tooltipStyle}
                  labelFormatter={fullDate}
                  formatter={(value) => Number(value).toFixed(2)}
                />
                <Line
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="brier"
                  name="Brier score"
                  stroke="#cf5f5f"
                  strokeWidth={2.8}
                  dot={{ r: 3, fill: "#cf5f5f" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <p className="chart-note">
          A smaller score means your stated confidence has matched outcomes more closely.
        </p>
      </div>
    </div>
  );
}

export function ScenarioChart({ scenario }: { scenario: Scenario }) {
  return <CompareChart data={scenario.context.chart} height={260} />;
}
export function ExplainChart({ data }: { data: ExplainResult }) {
  return <CompareChart data={data.chart} height={260} />;
}
