/* ============================================================================
   ValBot — UI compartilhada: formatadores + gráficos/widgets
   Porte fiel de .design-ref/vb-ui.jsx (widgets) + fmt de .design-ref/vb-data.js
   ============================================================================ */
import type { CSSProperties, ReactNode, JSX } from "react";
import type { IconComponent } from "./icons";

/* ---------------- formatadores (window.VB.fmt no protótipo) ---------------- */
const NOW = Date.now();

export const fmt = {
  int: (n: number): string => (n || 0).toLocaleString("pt-BR"),
  brl: (n: number): string =>
    "R$ " +
    (n || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  usd: (n: number): string =>
    "$ " +
    (n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  usd4: (n: number): string =>
    "$ " +
    (n || 0).toLocaleString("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 4 }),
  pct: (n: number): string =>
    (n || 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%",
  tokens: (n: number): string =>
    n >= 1e9
      ? (n / 1e9).toFixed(2) + " B"
      : n >= 1e6
        ? (n / 1e6).toFixed(1) + " M"
        : n >= 1e3
          ? (n / 1e3).toFixed(1) + " k"
          : String(Math.round(n || 0)),
  dur: (s: number): string => {
    s = Math.round(s || 0);
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  },
  dmy: (d: Date | string | number | null | undefined): string =>
    d ? new Date(d).toLocaleDateString("pt-BR") : "—",
  dmyhm: (d: Date | string | number | null | undefined): string =>
    d
      ? new Date(d).toLocaleDateString("pt-BR") +
        ", " +
        new Date(d).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
      : "—",
  ago: (d: Date | string | number): string => {
    const m = Math.round((NOW - new Date(d).getTime()) / 60000);
    if (m < 60) return "há " + m + " min";
    const h = Math.round(m / 60);
    if (h < 24) return "há " + h + "h";
    return "há " + Math.round(h / 24) + "d";
  },
};

/* ---------------- Sparkline (mini gráfico SVG) ---------------- */
export interface SparklineProps {
  data: number[];
  w?: number;
  h?: number;
  color?: string;
  fill?: boolean;
  sw?: number;
}

export function Sparkline({
  data,
  w = 200,
  h = 48,
  color = "var(--brand)",
  fill = true,
  sw = 2,
}: SparklineProps): JSX.Element | null {
  if (!data || !data.length) return null;
  const min = Math.min(...data),
    max = Math.max(...data),
    span = max - min || 1;
  const dx = w / (data.length - 1);
  const pts = data.map((v, i) => [i * dx, h - 4 - ((v - min) / span) * (h - 8)]);
  const line = pts
    .map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1))
    .join(" ");
  const area = line + ` L${w} ${h} L0 ${h} Z`;
  const id = "sg" + Math.random().toString(36).slice(2, 7);
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      style={{ display: "block" }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.18" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${id})`} />}
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={sw}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3" fill={color} />
    </svg>
  );
}

/* alias `Spark` (compatibilidade com o nome usado nas páginas vb) */
export const Spark = Sparkline;

/* ---------------- Donut ---------------- */
export interface DonutSegment {
  value: number;
  color: string;
  label?: string;
}

export interface DonutProps {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
  center?: ReactNode;
}

export function Donut({ segments, size = 132, thickness = 16, center }: DonutProps): JSX.Element {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2,
    c = 2 * Math.PI * r;
  let off = 0;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={thickness}
        />
        {segments.map((s, i) => {
          const len = (s.value / total) * c;
          const el = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={thickness}
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-off}
              strokeLinecap="butt"
            />
          );
          off += len;
          return el;
        })}
      </svg>
      {center && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "grid",
            placeItems: "center",
            textAlign: "center",
          }}
        >
          {center}
        </div>
      )}
    </div>
  );
}

/* ---------------- Bars (verticais) ---------------- */
export interface BarDatum {
  label: string;
  value: number;
  color?: string;
}

export interface BarsProps {
  data: BarDatum[];
  h?: number;
  color?: string;
}

export function Bars({ data, h = 150, color = "var(--brand)" }: BarsProps): JSX.Element {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: h }}>
      {data.map((d, i) => (
        <div
          key={i}
          title={`${d.label}: ${d.value}`}
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 6,
            height: "100%",
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: 26,
              height: `${Math.max(4, (d.value / max) * (h - 22))}px`,
              background: d.color || color,
              borderRadius: "5px 5px 2px 2px",
            }}
          />
          <span style={{ fontSize: 10, color: "var(--faint)" }}>{d.label}</span>
        </div>
      ))}
    </div>
  );
}

/* ---------------- HBars (barras horizontais / ranking) ---------------- */
export interface HBarItem {
  label: string;
  value: number;
  color?: string;
}

export interface HBarsProps {
  items: HBarItem[];
  color?: string;
  fmt?: (v: number) => ReactNode;
}

export function HBars({ items, color = "var(--brand)", fmt: fmtFn }: HBarsProps): JSX.Element {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
      {items.map((it, i) => (
        <div key={i}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 12.5,
              marginBottom: 5,
            }}
          >
            <span style={{ color: "var(--ink-2)", fontWeight: 550 }}>{it.label}</span>
            <span className="mono" style={{ color: "var(--muted)", fontWeight: 600 }}>
              {fmtFn ? fmtFn(it.value) : it.value}
            </span>
          </div>
          <div className="bar">
            <i style={{ width: `${(it.value / max) * 100}%`, background: it.color || color }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------------- Kpi card ---------------- */
export type DeltaDir = "up" | "down" | "flat";

export interface KpiProps {
  icon?: IconComponent;
  iconColor?: string;
  iconBg?: string;
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  delta?: ReactNode;
  deltaDir?: DeltaDir;
  foot?: ReactNode;
  spark?: number[];
  sparkColor?: string;
}

export function Kpi({
  icon,
  iconColor,
  iconBg,
  label,
  value,
  unit,
  delta,
  deltaDir,
  foot,
  spark,
  sparkColor,
}: KpiProps): JSX.Element {
  const Ico = icon;
  return (
    <div className="kpi">
      <div className="kpi-top">
        {Ico && (
          <span
            className="kpi-ico"
            style={{ background: iconBg || "var(--brand-tint)", color: iconColor || "var(--brand)" }}
          >
            <Ico w={19} />
          </span>
        )}
        <span className="kpi-label">{label}</span>
        {delta != null && (
          <span className={"delta " + (deltaDir || "up")} style={{ marginLeft: "auto" }}>
            {deltaDir === "down" ? "▾" : deltaDir === "flat" ? "•" : "▴"} {delta}
          </span>
        )}
      </div>
      <div className="kpi-val">
        {value}
        {unit && <span className="u">{unit}</span>}
      </div>
      {spark ? (
        <Sparkline data={spark} w={260} h={42} color={sparkColor || iconColor || "var(--brand)"} />
      ) : null}
      {foot && <div className="kpi-foot">{foot}</div>}
    </div>
  );
}

/* ---------------- MiniStat (linha label/valor, de page-dashboard.jsx) ---------------- */
export interface MiniStatProps {
  label: ReactNode;
  value: ReactNode;
}

export function MiniStat({ label, value }: MiniStatProps): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        paddingBottom: 12,
        borderBottom: "1px solid var(--border)",
      }}
    >
      <span style={{ fontSize: 13, color: "var(--ink-2)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 16, fontWeight: 800 }}>
        {value}
      </span>
    </div>
  );
}

/* ---------------- StatusBadge (pílula semântica, classes .badge do vb.css) ---------------- */
export type BadgeTone = "ok" | "bad" | "warn" | "proc" | "neutral";

export interface StatusBadgeProps {
  /** variante semântica → mapeia para .badge.<tone> */
  tone?: BadgeTone;
  label: ReactNode;
  /** estilos inline opcionais (ex.: cores customizadas por gravidade) */
  style?: CSSProperties;
  className?: string;
}

export function StatusBadge({
  tone = "neutral",
  label,
  style,
  className,
}: StatusBadgeProps): JSX.Element {
  return (
    <span className={"badge " + tone + (className ? " " + className : "")} style={style}>
      <span className="bd" />
      {label}
    </span>
  );
}
