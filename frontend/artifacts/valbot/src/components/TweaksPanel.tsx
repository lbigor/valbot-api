import { useEffect, useState, useCallback, type ReactNode } from "react";

/**
 * TweaksPanel — painel flutuante de customização do design system ValBot.
 *
 * Porte de tweaks-panel.jsx do bundle, adaptado para o app real (sem o
 * protocolo de host/iframe do protótipo Omelette). Permite:
 *  - escolher a cor de marca a partir de presets curados — aplica
 *    document.documentElement.style.setProperty("--brand"/"--brand-600"/
 *    "--brand-500"/"--brand-tint", …), exatamente como o protótipo;
 *  - escolher a densidade (compacto / regular / confortável);
 *  - persistir tudo em localStorage ("valbot:tweaks").
 *
 * Aditivo: não registra rotas nem altera a navegação. Renderize em qualquer
 * lugar (ex.: <TweaksPanel/> no shell) e abra pelo botão flutuante.
 */

const STORAGE_KEY = "valbot:tweaks";

export interface BrandPreset {
  /** rótulo curto */
  label: string;
  /** --brand */
  brand: string;
  /** --brand-600 */
  b600: string;
  /** --brand-500 */
  b500: string;
  /** --brand-tint */
  tint: string;
}

/** Presets de marca curados (índigo default + alternativas). */
export const BRAND_PRESETS: BrandPreset[] = [
  { label: "Índigo", brand: "#4338CA", b600: "#4F46E5", b500: "#6366F1", tint: "#EEF0FE" },
  { label: "Azul", brand: "#1D4ED8", b600: "#2563EB", b500: "#3B82F6", tint: "#E7EEFD" },
  { label: "Verde", brand: "#0F8A5B", b600: "#12A06A", b500: "#22B57D", tint: "#E6F6EF" },
  { label: "Violeta", brand: "#7A5AE0", b600: "#8B6BF0", b500: "#9D82F4", tint: "#F0EBFE" },
  { label: "Âmbar", brand: "#B45309", b600: "#D97706", b500: "#F59E0B", tint: "#FBF1E3" },
];

export type Density = "compacto" | "regular" | "confortavel";

const DENSITY_SCALE: Record<Density, string> = {
  compacto: "0.92",
  regular: "1",
  confortavel: "1.08",
};

interface TweaksState {
  brand: number; // índice em BRAND_PRESETS
  density: Density;
}

const DEFAULTS: TweaksState = { brand: 0, density: "regular" };

function readStored(): TweaksState {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<TweaksState>;
    return {
      brand:
        typeof parsed.brand === "number" && parsed.brand >= 0 && parsed.brand < BRAND_PRESETS.length
          ? parsed.brand
          : DEFAULTS.brand,
      density:
        parsed.density === "compacto" || parsed.density === "confortavel" || parsed.density === "regular"
          ? parsed.density
          : DEFAULTS.density,
    };
  } catch {
    return DEFAULTS;
  }
}

function applyBrand(preset: BrandPreset) {
  const root = document.documentElement;
  root.style.setProperty("--brand", preset.brand);
  root.style.setProperty("--brand-600", preset.b600);
  root.style.setProperty("--brand-500", preset.b500);
  root.style.setProperty("--brand-tint", preset.tint);
}

function applyDensity(d: Density) {
  document.documentElement.style.setProperty("--ds-density", DENSITY_SCALE[d]);
}

export function TweaksPanel({ title = "Tweaks" }: { title?: string }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<TweaksState>(readStored);

  // Aplica + persiste sempre que muda.
  useEffect(() => {
    applyBrand(BRAND_PRESETS[state.brand]);
    applyDensity(state.density);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
  }, [state]);

  const setBrand = useCallback((i: number) => setState((s) => ({ ...s, brand: i })), []);
  const setDensity = useCallback((d: Density) => setState((s) => ({ ...s, density: d })), []);

  return (
    <>
      <style>{TWEAKS_STYLE}</style>
      {!open && (
        <button
          type="button"
          className="twk-fab"
          aria-label="Abrir customização"
          onClick={() => setOpen(true)}
          title="Customizar tema"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      )}

      {open && (
        <div className="twk-panel" role="dialog" aria-label={title}>
          <div className="twk-hd">
            <b>{title}</b>
            <button className="twk-x" aria-label="Fechar" onClick={() => setOpen(false)}>
              ✕
            </button>
          </div>
          <div className="twk-body">
            <TweakSection label="Marca">
              <div className="twk-chips" role="radiogroup" aria-label="Cor de marca">
                {BRAND_PRESETS.map((p, i) => (
                  <button
                    key={p.label}
                    type="button"
                    role="radio"
                    aria-checked={i === state.brand}
                    data-on={i === state.brand ? "1" : "0"}
                    className="twk-chip"
                    title={p.label}
                    aria-label={p.label}
                    style={{ background: p.brand }}
                    onClick={() => setBrand(i)}
                  />
                ))}
              </div>
            </TweakSection>

            <TweakSection label="Densidade">
              <div className="twk-seg" role="radiogroup" aria-label="Densidade">
                {(["compacto", "regular", "confortavel"] as Density[]).map((d) => (
                  <button
                    key={d}
                    type="button"
                    role="radio"
                    aria-checked={state.density === d}
                    data-on={state.density === d ? "1" : "0"}
                    onClick={() => setDensity(d)}
                  >
                    {d === "confortavel" ? "Confortável" : d.charAt(0).toUpperCase() + d.slice(1)}
                  </button>
                ))}
              </div>
            </TweakSection>
          </div>
        </div>
      )}
    </>
  );
}

function TweakSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="twk-row">
      <div className="twk-sect">{label}</div>
      {children}
    </div>
  );
}

const TWEAKS_STYLE = `
  .twk-fab{position:fixed;right:16px;bottom:16px;z-index:2147483646;
    width:42px;height:42px;border-radius:999px;border:1px solid var(--border-strong,#D5DBE6);
    background:var(--surface,#fff);color:var(--ink-2,#2B3445);
    display:grid;place-items:center;box-shadow:0 8px 24px -12px rgba(12,18,32,.4);cursor:pointer}
  .twk-fab:hover{background:var(--surface-2,#F8FAFC)}

  .twk-panel{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:260px;
    max-height:calc(100vh - 32px);display:flex;flex-direction:column;
    background:var(--surface,#fff);color:var(--ink,#0C1220);
    border:1px solid var(--border,#E5E9F0);border-radius:14px;
    box-shadow:0 12px 40px rgba(12,18,32,.22);
    font:12px/1.4 var(--font, ui-sans-serif,system-ui,-apple-system,sans-serif);overflow:hidden}
  .twk-hd{display:flex;align-items:center;justify-content:space-between;
    padding:12px 10px 12px 14px;border-bottom:1px solid var(--border,#E5E9F0);user-select:none}
  .twk-hd b{font-size:13px;font-weight:600}
  .twk-x{appearance:none;border:0;background:transparent;color:var(--muted,#6B7689);
    width:24px;height:24px;border-radius:6px;cursor:pointer;font-size:13px;line-height:1}
  .twk-x:hover{background:var(--surface-3,#F1F4F9);color:var(--ink,#0C1220)}
  .twk-body{padding:14px;display:flex;flex-direction:column;gap:14px;overflow-y:auto;min-height:0}
  .twk-row{display:flex;flex-direction:column;gap:7px}
  .twk-sect{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
    color:var(--muted,#6B7689)}

  .twk-chips{display:flex;gap:7px}
  .twk-chip{position:relative;appearance:none;flex:1;min-width:0;height:34px;padding:0;border:0;
    border-radius:8px;overflow:hidden;cursor:pointer;
    box-shadow:0 0 0 1px var(--border,#E5E9F0);transition:transform .12s,box-shadow .12s}
  .twk-chip:hover{transform:translateY(-1px)}
  .twk-chip[data-on="1"]{box-shadow:0 0 0 2px var(--ink,#0C1220)}

  .twk-seg{position:relative;display:flex;padding:3px;border-radius:9px;gap:2px;
    background:var(--surface-3,#F1F4F9);border:1px solid var(--border,#E5E9F0)}
  .twk-seg button{appearance:none;flex:1;border:0;background:transparent;color:var(--muted,#6B7689);
    font:inherit;font-weight:550;font-size:11.5px;min-height:26px;border-radius:6px;cursor:pointer;padding:4px}
  .twk-seg button[data-on="1"]{background:var(--surface,#fff);color:var(--ink,#0C1220);
    box-shadow:var(--shadow-sm,0 1px 2px rgba(12,18,32,.06))}
`;

export default TweaksPanel;
