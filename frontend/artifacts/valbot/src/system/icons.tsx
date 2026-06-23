/* ============================================================================
   ValBot — ícones (lucide-style), porte fiel de .design-ref/vb-ui.jsx
   Cada ícone herda currentColor. Props: { w, h, className, style, sw }.
   ============================================================================ */
import type { CSSProperties, JSX } from "react";

export interface IconProps {
  w?: number;
  h?: number;
  className?: string;
  style?: CSSProperties;
  sw?: number;
}

export type IconComponent = (props?: IconProps) => JSX.Element;

/* helper: ícone de traço (stroke), igual ao `svg(paths, vb)` do protótipo */
const svg =
  (paths: string[], vb?: string): IconComponent =>
  (p: IconProps = {}) =>
    (
      <svg
        width={p.w || 18}
        height={p.h || p.w || 18}
        viewBox={vb || "0 0 24 24"}
        fill="none"
        stroke="currentColor"
        strokeWidth={p.sw || 1.85}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={p.className}
        style={p.style}
      >
        {paths.map((d, i) => (
          <path key={i} d={d} />
        ))}
      </svg>
    );

export const I: Record<string, IconComponent> = {
  dashboard: (p: IconProps = {}) => (
    <svg
      width={p.w || 18}
      height={p.w || 18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.85}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <rect x={3} y={3} width={7} height={9} rx={1.5} />
      <rect x={14} y={3} width={7} height={5} rx={1.5} />
      <rect x={14} y={12} width={7} height={9} rx={1.5} />
      <rect x={3} y={16} width={7} height={5} rx={1.5} />
    </svg>
  ),
  fila: svg(["M3 6h18", "M7 12h10", "M11 18h2"]),
  regras: (p: IconProps = {}) => (
    <svg
      width={p.w || 18}
      height={p.w || 18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.85}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  ),
  custos: svg(["M12 1v22", "M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"]),
  supervisor: svg(["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z", "M9 12l2 2 4-4"]),
  usuarios: (p: IconProps = {}) => (
    <svg
      width={p.w || 18}
      height={p.w || 18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.85}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx={9} cy={7} r={4} />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  relatorios: svg([
    "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
    "M14 2v6h6",
    "M8 13h8",
    "M8 17h8",
    "M8 9h2",
  ]),
  medicao: svg(["M3 12h4l3 8 4-16 3 8h4"]),
  agendamento: (p: IconProps = {}) => (
    <svg
      width={p.w || 18}
      height={p.w || 18}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.85}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <circle cx={12} cy={12} r={9} />
      <path d="M12 7v5l3 2" />
    </svg>
  ),
  search: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      className={p.className}
      style={p.style}
    >
      <circle cx={11} cy={11} r={7} />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  ),
  bell: svg([
    "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9",
    "M10.3 21a1.94 1.94 0 0 0 3.4 0",
  ]),
  logout: svg(["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"]),
  down: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  ),
  right: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  ),
  plus: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.3}
      strokeLinecap="round"
      className={p.className}
      style={p.style}
    >
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  check: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  x: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.1}
      strokeLinecap="round"
      className={p.className}
      style={p.style}
    >
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  ),
  download: svg([
    "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
    "M7 10l5 5 5-5",
    "M12 15V3",
  ]),
  pdf: svg(["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6"]),
  edit: svg(["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"]),
  trash: svg(["M3 6h18", "M8 6V4h8v2", "M6 6l1 14h10l1-14"]),
  play: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={p.className}
      style={p.style}
    >
      <path d="M7 4v16l13-8z" />
    </svg>
  ),
  filter: svg(["M3 5h18l-7 8v6l-4-2v-4z"]),
  clock: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <circle cx={12} cy={12} r={9} />
      <path d="M12 7v5l3 2" />
    </svg>
  ),
  alert: svg([
    "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
    "M12 9v4",
    "M12 17h.01",
  ]),
  bolt: svg([
    "M13 2L4.1 12.5a1 1 0 0 0 .8 1.6H11l-1 7.9 8.9-10.5a1 1 0 0 0-.8-1.6H12z",
  ]),
  video: svg([
    "M16 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2z",
    "M22 8l-4 4 4 4z",
  ]),
  cpu: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.85}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={p.className}
      style={p.style}
    >
      <rect x={7} y={7} width={10} height={10} rx={1.5} />
      <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
    </svg>
  ),
  building: svg([
    "M4 22V4a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v18",
    "M15 9h4a1 1 0 0 1 1 1v12",
    "M8 7h2M8 11h2M8 15h2",
  ]),
  target: (p: IconProps = {}) => (
    <svg
      width={p.w || 16}
      height={p.w || 16}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.85}
      className={p.className}
      style={p.style}
    >
      <circle cx={12} cy={12} r={9} />
      <circle cx={12} cy={12} r={5} />
      <circle cx={12} cy={12} r={1} />
    </svg>
  ),
};

export default I;
