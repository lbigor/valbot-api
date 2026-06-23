import * as React from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type GlowTone = "cyan" | "red" | "emerald" | "blue" | "amber" | "violet";

const GLOW: Record<GlowTone, string> = {
  cyan: "shadow-[0_0_25px_-12px_rgba(6,182,212,0.45)]",
  red: "shadow-[0_0_25px_-10px_rgba(239,68,68,0.55)]",
  emerald: "shadow-[0_0_25px_-12px_rgba(16,185,129,0.45)]",
  blue: "shadow-[0_0_25px_-12px_rgba(29,78,216,0.5)]",
  amber: "shadow-[0_0_25px_-12px_rgba(245,158,11,0.45)]",
  violet: "shadow-[0_0_25px_-12px_rgba(139,92,246,0.45)]",
};

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: GlowTone;
}

/**
 * Glass-styled wrapper around the shadcn <Card>. Mantém o primitivo
 * shadcn/ui (acessibilidade, ref forwarding, slots) e só adiciona
 * o tratamento glassmorphic + neon glow via classes Tailwind.
 */
export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, glow, children, ...rest }, ref) => (
    <Card
      ref={ref}
      className={cn(
        // override: shadcn Card vem com bg-card opaco — trocamos por backdrop translúcido.
        "relative rounded-xl border-slate-800/80 bg-[#0B1224]/55 backdrop-blur-md shadow-none transition-all duration-300 hover:border-slate-700",
        glow && GLOW[glow],
        className,
      )}
      {...rest}
    >
      {children}
    </Card>
  ),
);
GlassCard.displayName = "GlassCard";

export const tooltipStyle = {
  backgroundColor: "rgba(11,18,36,0.95)",
  border: "1px solid rgba(30,41,59,0.9)",
  borderRadius: 8,
  backdropFilter: "blur(8px)",
  color: "#F1F5F9",
  fontSize: 12,
  boxShadow: "0 8px 32px -8px rgba(0,0,0,0.6)",
};
