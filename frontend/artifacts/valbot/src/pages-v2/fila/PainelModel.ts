/* ============================================================================
   Painel — modelo: marcadores/timecodes por clipe (porte de painel-model.jsx)
   Espelha o window.VBP do protótipo: hashCode, placeAt, clipMarks, initLaudo.
   ============================================================================ */
import { VB } from "@/system/painel-data";
import type { ExamItem, MarkRef, AudioCue, Interrupt, Grav } from "@/system/painel-data";

export function hashCode(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// posição determinística de uma infração dentro da duração do clipe
export function placeAt(seed: string, _dur: number, lo: number, hi: number): number {
  const h = hashCode(seed);
  const span = Math.max(1, hi - lo);
  return lo + (h % span);
}

export interface ClipMarks {
  tp: MarkRef[];
  vb: MarkRef[];
  onlyTp: MarkRef[];
  onlyVb: MarkRef[];
  divRegions: { from: number; to: number }[];
  processing: boolean;
  audio: AudioCue[];
  interrupt: Interrupt | null;
}

// gera marcadores das trilhas TP e ValBot para um clipe
export function clipMarks(q: ExamItem): ClipMarks {
  const dur = q.dur;
  const fix = q.tsFix || {};
  const lenOf = (c: string, salt: string) => 3 + (hashCode(q.id + c + salt) % 5); // 3..7s

  const tp: MarkRef[] = q.tp.faults
    .map((c) => {
      const t = fix[c] != null ? fix[c] : placeAt(q.id + c + "tp", dur, 3, dur - 6);
      return { code: c, t, len: lenOf(c, "tp"), grav: VB.ruleByCode[c].grav };
    })
    .sort((a, b) => a.t - b.t);

  const vbCodes = q.vb ? q.vb.faults : [];
  const vb: MarkRef[] = vbCodes
    .map((c) => {
      const shared = q.tp.faults.includes(c);
      let t: number;
      if (fix[c] != null) {
        t = fix[c];
      } else if (shared) {
        const base = tp.find((x) => x.code === c)!.t;
        t = Math.max(2, Math.min(dur - 4, base + ((hashCode(q.id + c) % 3) - 1)));
      } else {
        t = placeAt(q.id + c + "vb", dur, 3, dur - 6);
      }
      return { code: c, t, len: lenOf(c, "vb"), grav: VB.ruleByCode[c].grav, conf: q.vb!.conf, shared };
    })
    .sort((a, b) => a.t - b.t);

  const tpSet = new Set(q.tp.faults);
  const vbSet = new Set(vbCodes);
  const onlyTp = tp.filter((m) => !vbSet.has(m.code));
  const onlyVb = vb.filter((m) => !tpSet.has(m.code));
  const divRegions = [...onlyTp, ...onlyVb].map((m) => ({ from: m.t, to: m.t + m.len }));

  return { tp, vb, onlyTp, onlyVb, divRegions, processing: !q.vb, audio: q.audio || [], interrupt: q.interrupt || null };
}

// laudo inicial: concordância → herda; divergência/processando → vazio (revisor monta)
export function initLaudo(q: ExamItem): MarkRef[] {
  const m = clipMarks(q);
  if (q.final) {
    return q.final.faults.map((f) => {
      const code = (f as unknown as { code?: string }).code || (f as string);
      const ref = m.tp.find((x) => x.code === code) || m.vb.find((x) => x.code === code);
      return {
        code,
        t: ref ? ref.t : placeAt(q.id + code + "l", q.dur, 3, q.dur - 6),
        len: ref ? ref.len : 4,
        grav: VB.ruleByCode[code].grav as Grav,
      };
    });
  }
  if (q.status === "finalizado" && q.vb) {
    return m.tp.filter((x) => q.vb!.faults.includes(x.code)).map((x) => ({ ...x }));
  }
  return [];
}

export const VBP = { hashCode, clipMarks, initLaudo, placeAt };
export default VBP;
