import type { ReactNode, CSSProperties } from "react";
import { Icons } from "./icons";

/* ============ ValBot — componentes compartilhados (porte de ui.jsx) ============ */

/* ---------- metadados (porte de data.jsx meta) ---------- */
export type ExamStatus = "processando" | "divergencia" | "finalizado";
export type Gravidade = "gravissima" | "grave" | "media" | "leve";

export const STATUS_META: Record<ExamStatus, { label: string; cls: string }> = {
  processando: { label: "Processando", cls: "badge-proc" },
  divergencia: { label: "Divergência", cls: "badge-bad" },
  finalizado: { label: "Finalizado", cls: "badge-ok" },
};

export const GRAV_META: Record<
  Gravidade,
  { label: string; color: string; bg: string; ring: string; pontos: number }
> = {
  gravissima: { label: "Gravíssima", color: "#BE123C", bg: "#FCEAEF", ring: "#F3C2CF", pontos: 6 },
  grave: { label: "Grave", color: "#B45309", bg: "#FBF1E3", ring: "#F0D9B3", pontos: 4 },
  media: { label: "Média", color: "#1D4ED8", bg: "#E7EEFD", ring: "#C5D6F8", pontos: 2 },
  leve: { label: "Leve", color: "#6B7689", bg: "#F1F4F9", ring: "#E5E9F0", pontos: 1 },
};

/* ---------- Badge ---------- */
export function Badge({
  cls,
  children,
  style,
}: {
  cls: string;
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <span className={"badge " + cls} style={style}>
      <span className="dot" />
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: ExamStatus }) {
  const m = STATUS_META[status];
  return <Badge cls={m.cls}>{m.label}</Badge>;
}

export function ResultBadge({
  result,
  small,
}: {
  result?: "aprovado" | "reprovado" | null;
  small?: boolean;
}) {
  if (!result) return <span style={{ color: "var(--faint)" }}>—</span>;
  const ok = result === "aprovado";
  return (
    <span
      className={"badge " + (ok ? "badge-ok" : "badge-bad")}
      style={small ? { height: 22, fontSize: 11.5 } : undefined}
    >
      <span className="dot" />
      {ok ? "Aprovado" : "Reprovado"}
    </span>
  );
}

export function GravTag({ grav }: { grav: Gravidade }) {
  const m = GRAV_META[grav];
  return (
    <span
      className="badge"
      style={{ color: m.color, background: m.bg, boxShadow: `inset 0 0 0 1px ${m.ring}` }}
    >
      <span className="dot" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

/* ---------- Spark (sparkline) ---------- */
export interface SparkProps {
  data: number[];
  color?: string;
  w?: number;
  h?: number;
  fill?: boolean;
  fluid?: boolean;
}

export function Spark({
  data,
  color = "var(--brand)",
  w = 132,
  h = 40,
  fill = true,
  fluid = false,
}: SparkProps) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const pad = (max - min) * 0.15 || 1;
  const lo = min - pad;
  const hi = max + pad;
  const X = (i: number) => (i / (data.length - 1)) * w;
  const Y = (v: number) => h - ((v - lo) / (hi - lo)) * h;
  const line = data.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(" ");
  const area = line + ` L${w} ${h} L0 ${h} Z`;
  const uid = Math.round(X(0) + color.length + data[0] + (fluid ? 999 : 0));
  const gid = "sg" + uid;

  if (fluid) {
    const INSET = 0.07;
    const lastX = w * (1 - INSET);
    const Xf = (i: number) => (i / (data.length - 1)) * lastX;
    const lineF = data
      .map((v, i) => `${i ? "L" : "M"}${Xf(i).toFixed(1)} ${Y(v).toFixed(1)}`)
      .join(" ");
    const areaF = lineF + ` L${lastX.toFixed(1)} ${h} L0 ${h} Z`;
    return (
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        style={{ display: "block" }}
      >
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity="0.26" />
            <stop offset="0.55" stopColor={color} stopOpacity="0.07" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <line
          x1="0"
          x2={lastX}
          y1={Y(min)}
          y2={Y(min)}
          stroke={color}
          strokeOpacity="0.16"
          strokeWidth="1"
          strokeDasharray="2 3"
          vectorEffect="non-scaling-stroke"
        />
        {fill && <path d={areaF} fill={`url(#${gid})`} />}
        <path
          d={lineF}
          fill="none"
          stroke={color}
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.18" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${gid})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={X(data.length - 1)} cy={Y(data[data.length - 1])} r="3" fill={color} />
    </svg>
  );
}

/* ---------- Delta chip ---------- */
export function Delta({ v, invert }: { v: number; invert?: boolean }) {
  const up = v >= 0;
  const good = invert ? !up : up;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        fontSize: 12.5,
        fontWeight: 650,
        color: good ? "var(--ok)" : "var(--bad)",
        background: good ? "var(--ok-bg)" : "var(--bad-bg)",
        padding: "2px 7px 2px 5px",
        borderRadius: 7,
      }}
    >
      {up ? <Icons.up /> : <Icons.down />}
      {Math.abs(v).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%
    </span>
  );
}

/* ---------- Ring / donut ---------- */
export function Ring({
  pct,
  size = 132,
  stroke = 13,
  color = "var(--brand)",
}: {
  pct: number;
  size?: number;
  stroke?: number;
  color?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={c}
        strokeDashoffset={off}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 1s cubic-bezier(.2,.7,.3,1)" }}
      />
    </svg>
  );
}
