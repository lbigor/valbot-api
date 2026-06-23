import { useState, type ReactNode } from "react";
import "./HowItWorks.css";

const LS = "vb-painel-v3";

function loadState(): Record<string, unknown> {
  try {
    return JSON.parse(localStorage.getItem(LS) || "") || {};
  } catch {
    return {};
  }
}

function saveState(p: Record<string, unknown>): void {
  try {
    localStorage.setItem(LS, JSON.stringify({ ...loadState(), ...p }));
  } catch {
    /* noop */
  }
}

interface Step {
  n: number;
  c: string;
  t: string;
  d: string;
  ic: ReactNode;
}

const HOWTO: Step[] = [
  {
    n: 1,
    c: "#5B8DEF",
    t: "Aponte o momento",
    d: "Clique na linha do tempo no instante exato da falha ou use os marcadores do ValBot.",
    ic: <path d="M12 2v4M12 18v4M2 12h4M18 12h4M12 8a4 4 0 100 8 4 4 0 000-8z" />,
  },
  {
    n: 2,
    c: "#F08A2C",
    t: "Lance a infração",
    d: "Marque o início e o fim da ocorrência, escolha o enquadramento e confirme a gravidade.",
    ic: <path d="M12 5v14M5 12h14" />,
  },
  {
    n: 3,
    c: "#1FA968",
    t: "Finalize o laudo",
    d: "Revise as infrações e aprove ou reprove para concluir o exame.",
    ic: <path d="M20 6L9 17l-5-5" />,
  },
];

export function HowItWorks() {
  const [open, setOpen] = useState<boolean>(
    () => loadState().howtoOpen !== false
  );
  const toggle = () => {
    setOpen((o) => {
      saveState({ howtoOpen: !o });
      return !o;
    });
  };
  return (
    <div className={"howto" + (open ? "" : " howto-collapsed")}>
      <button className="howto-head" onClick={toggle} aria-expanded={open}>
        <svg
          className="howto-chev"
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
        Como lançar uma infração
        <span className="howto-hide">{open ? "Ocultar" : "Mostrar"}</span>
      </button>
      {open && (
        <div className="howto-grid">
          {HOWTO.map((s) => (
            <div className="howto-card" key={s.n}>
              <span className="howto-ic" style={{ background: s.c }}>
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#fff"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  {s.ic}
                </svg>
              </span>
              <div className="howto-body">
                <div className="howto-t">
                  <span className="howto-n mono">{s.n}</span>
                  {s.t}
                </div>
                <div className="howto-d">{s.d}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
