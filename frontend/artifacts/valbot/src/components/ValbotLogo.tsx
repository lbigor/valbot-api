import type { SVGProps } from "react";

/**
 * ValbotLogo — marca do ValBot como SVG monoline (olho + check).
 *
 * Desenhado em stroke="currentColor" para herdar a cor do contexto
 * (ex.: usar dentro da sidebar escura ou da topbar clara). Para a marca
 * cheia (disco índigo com check) use o asset public/logo.png via <ValbotLogoMark/>.
 */
export interface ValbotLogoProps extends Omit<SVGProps<SVGSVGElement>, "size"> {
  /** lado do quadrado em px (default 38) */
  size?: number;
}

export function ValbotLogo({ size = 38, className, ...rest }: ValbotLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label="ValBot"
      className={className}
      {...rest}
    >
      {/* contorno do olho */}
      <path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z" />
      {/* íris */}
      <circle cx="12" cy="12" r="4.2" />
      {/* check dentro da íris (validação) */}
      <path d="M10 12.1l1.5 1.5L14.2 10.8" />
    </svg>
  );
}

export interface ValbotLogoMarkProps {
  /** lado do quadrado em px (default 38) */
  size?: number;
  className?: string;
  alt?: string;
}

/**
 * ValbotLogoMark — a marca cheia (disco índigo + check) servida como imagem
 * a partir de public/logo.png. Use no lugar do SVG quando quiser a versão
 * colorida/raster da identidade.
 */
export function ValbotLogoMark({
  size = 38,
  className,
  alt = "ValBot",
}: ValbotLogoMarkProps) {
  return (
    <img
      src="/logo.png"
      alt={alt}
      width={size}
      height={size}
      className={className}
      style={{ display: "block", borderRadius: 11 }}
    />
  );
}

export default ValbotLogo;
