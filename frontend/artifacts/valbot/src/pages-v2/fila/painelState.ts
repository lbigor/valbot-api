/* ============================================================================
   Painel — persistência de estado em localStorage (porte de painel-core.jsx)
   LS "vb-painel-v3" + guia didático "vb-guide".
   ============================================================================ */
const LS = "vb-painel-v3";

export interface PainelState {
  dir?: string;
  selId?: string;
  pos?: number;
  tlOpen?: boolean;
  howtoOpen?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  tele?: Record<string, any>;
}

export function loadState(): PainelState {
  try {
    return (JSON.parse(localStorage.getItem(LS) || "null") as PainelState) || {};
  } catch {
    return {};
  }
}
export function saveState(p: PainelState): void {
  try {
    localStorage.setItem(LS, JSON.stringify({ ...loadState(), ...p }));
  } catch {
    /* noop */
  }
}

export function guideSeen(): string[] {
  try {
    return JSON.parse(localStorage.getItem("vb-guide") || "[]") as string[];
  } catch {
    return [];
  }
}
export function markGuide(k: string): void {
  try {
    const s = guideSeen();
    if (!s.includes(k)) localStorage.setItem("vb-guide", JSON.stringify([...s, k]));
  } catch {
    /* noop */
  }
}
