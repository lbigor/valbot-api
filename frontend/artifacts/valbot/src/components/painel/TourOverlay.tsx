import { useState, useEffect, useRef } from "react";
import "./TourOverlay.css";

/**
 * Passo do tour guiado.
 * - sel:  seletor CSS do elemento a destacar (ausente => card centralizado, sem spotlight).
 * - t:    título do passo.
 * - d:    descrição.
 * - hold: duração (ms) usada para animar a progress bar do passo.
 * - act:  ação opcional disparada no passo (ganchos do painel; aqui só marca o cursor como "clique").
 */
interface TourStep {
  sel?: string;
  t: string;
  d: string;
  hold?: number;
  act?: string;
}

const TOUR: TourStep[] = [
  { t: "Tour do fluxo", d: "Vou destacar cada etapa do Painel do Auditor e os pontos de conhecimento. Avance no seu ritmo — a barra acima apenas marca o tempo de cada passo.", hold: 4200 },
  { sel: ".exam-picker", t: "Exame em auditoria", d: "Aqui você seleciona o exame da fila — o cabeçalho traz o RENACH e o resultado em análise.", hold: 4200 },
  { sel: ".viewer", act: "seekInfra", t: "Vídeo do exame", d: "Levo o playhead até uma infração: a moldura acende na cor da gravidade e a tarja corre com o enquadramento. Na 1ª revisão, o avanço libera conforme você assiste.", hold: 5400 },
  { sel: ".timeline", t: "Linha do tempo", d: "Quatro trilhas — VÍDEO, TECHPRÁTICO (examinador), VALBOT (IA) e AUDITOR (seu laudo). Onde TechPrático e ValBot não coincidem, há uma divergência a revisar.", hold: 6200 },
  { sel: ".m-accept-big", t: "Trazer a detecção da IA", d: "Este “+” lança a infração detectada pelo ValBot direto no seu laudo, no mesmo início/fim.", hold: 4800 },
  { sel: ".dm", act: "openFicha", t: "Ficha do Procedimento", d: "Ponto de conhecimento: cada infração abre sua ficha oficial do MBEDV — descrição, gravidade e peso, e as abas Condutas que pontuam, que não pontuam e Definições.", hold: 7200 },
  { sel: ".lbtn.warn", t: "Lançar infração", d: "Enquadre manualmente pela Matriz Nacional — cada lançamento tem início, fim e o artigo do CTB.", hold: 5000 },
  { sel: ".laudo", t: "Seu laudo", d: "As infrações confirmadas somam pontos e definem o veredito sugerido. A sua análise é o laudo final.", hold: 5400 },
  { sel: ".ia-row", t: "Decisão", d: "Aprovar ou Reprovar pede confirmação e valida a coerência com o laudo antes de registrar e avançar.", hold: 5000 },
  { sel: ".pchrome-right", t: "Supervisão", d: "No topo, o Painel do Supervisor acompanha acessos, tempo de vídeo e a qualidade de cada auditoria.", hold: 5000 },
];

const GUIDE_KEY = "vb-guide";

export function TourOverlay({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  const [box, setBox] = useState<DOMRect | null>(null);
  // refs de timeout/raf para limpeza determinística no cleanup do useEffect (sem leak).
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rafRef = useRef<number | null>(null);

  const s = TOUR[i];
  const last = i === TOUR.length - 1;

  // Medição do alvo (acompanha layout/scroll) por ~24 frames após um pequeno atraso.
  useEffect(() => {
    let n = 0;
    const upd = () => {
      const el = s.sel ? document.querySelector(s.sel) : null;
      setBox(el ? el.getBoundingClientRect() : null);
      if (n++ < 24) {
        rafRef.current = requestAnimationFrame(upd);
      }
    };
    timeoutRef.current = setTimeout(upd, 90);
    return () => {
      if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i]);

  // Persiste "visto" em localStorage ao montar o tour.
  useEffect(() => {
    try {
      localStorage.setItem(GUIDE_KEY, "1");
    } catch {
      /* storage indisponível — ignora */
    }
  }, []);

  // Posicionamento do card e do cursor fantasma a partir do bounding box medido.
  let cardStyle: React.CSSProperties = { left: "50%", top: "50%", transform: "translate(-50%,-50%)" };
  let cur: { x: number; y: number } | null = null;
  if (box) {
    const cw = 348, ch = 268, gap = 20, W = window.innerWidth, H = window.innerHeight;
    const cl = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
    if (H - box.bottom > ch + gap) cardStyle = { top: box.bottom + gap, left: cl(box.left, 16, W - cw - 16) };
    else if (box.top > ch + gap) cardStyle = { top: box.top - ch - gap, left: cl(box.left, 16, W - cw - 16) };
    else if (W - box.right > cw + gap) cardStyle = { left: box.right + gap, top: cl(box.top, 16, H - ch - 16) };
    else if (box.left > cw + gap) cardStyle = { left: box.left - cw - gap, top: cl(box.top, 16, H - ch - 16) };
    else cardStyle = { left: cl(box.left, 16, W - cw - 16), top: 16 };
    cur = { x: cl(box.left + box.width / 2, 12, W - 12), y: cl(box.top + box.height / 2, 12, H - 12) };
  }

  return (
    <div className="tour-scrim2">
      {box && (
        <div
          className="tour-spot"
          style={{ left: box.left - 6, top: box.top - 6, width: box.width + 12, height: box.height + 12 }}
        />
      )}
      {cur && (
        <div className={"tour-cursor" + (s.act ? " act" : "")} style={{ left: cur.x, top: cur.y }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff" stroke="rgba(0,0,0,.5)" strokeWidth="1.2">
            <path d="M5 3l15 9-6.5 1.5L10 20z" />
          </svg>
        </div>
      )}
      <div className="tour-card" style={cardStyle}>
        <div className="tour-progress">
          <span key={i} style={{ animationDuration: (s.hold || 4800) + "ms" }} />
        </div>
        <div className="tour-step">Etapa {i + 1} / {TOUR.length}</div>
        <div className="tour-title">{s.t}</div>
        <div className="tour-desc">{s.d}</div>
        <div className="tour-dots">
          {TOUR.map((_, k) => (
            <span key={k} className={"tour-dot" + (k === i ? " on" : "") + (k < i ? " done" : "")} />
          ))}
        </div>
        <div className="tour-actions">
          <button className="tour-skip" onClick={onClose}>Pular</button>
          {i > 0 && <button className="tour-skip" onClick={() => setI(i - 1)}>Voltar</button>}
          <button className="tour-go" onClick={() => (last ? onClose() : setI(i + 1))}>
            {last ? "Concluir" : "Avançar"}
          </button>
        </div>
      </div>
    </div>
  );
}
