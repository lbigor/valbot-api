/* ============ ValBot — formatters (porte de ui.jsx) ============ */

export const fmtInt = (n: number): string => n.toLocaleString("pt-BR");

export const fmtBRL = (n: number, dec = 2): string =>
  "R$ " +
  n.toLocaleString("pt-BR", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });

export const MES = [
  "jan", "fev", "mar", "abr", "mai", "jun",
  "jul", "ago", "set", "out", "nov", "dez",
] as const;

const pad2 = (n: number) => String(n).padStart(2, "0");

export const fmtDate = (d?: Date | null): string =>
  d ? `${pad2(d.getDate())} ${MES[d.getMonth()]}` : "—";

export const fmtDMY = (d?: Date | null): string =>
  d ? `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}` : "—";

export const fmtTime = (d?: Date | null): string =>
  d ? `${pad2(d.getHours())}:${pad2(d.getMinutes())}` : "—";

export const fmtDT = (d?: Date | null): string =>
  d ? `${fmtDMY(d)} ${fmtTime(d)}` : "—";

export const fmtDur = (s: number): string =>
  `${Math.floor(s / 60)}:${pad2(s % 60)}`;
