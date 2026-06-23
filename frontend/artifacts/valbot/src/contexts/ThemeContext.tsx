import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";

/**
 * ThemeContext — fundação de temas do design system ValBot.
 *
 * Dois temas: "claro" (DEFAULT) e "grafite". O valor é aplicado como
 * atributo `data-dir` no elemento <html>, exatamente como o protótipo do
 * design (document.documentElement.setAttribute("data-dir", dir)), e os
 * tokens correspondentes vivem em src/styles/design-tokens.css.
 *
 * Persistência via localStorage ("valbot:theme"). Aditivo: não interfere
 * no tema shadcn/Tailwind (.dark) existente.
 */

export type ThemeDir = "claro" | "grafite";

const STORAGE_KEY = "valbot:theme";
const DEFAULT_THEME: ThemeDir = "claro";

interface ThemeContextValue {
  theme: ThemeDir;
  setTheme: (dir: ThemeDir) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function readStoredTheme(): ThemeDir {
  if (typeof window === "undefined") return DEFAULT_THEME;
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === "claro" || v === "grafite") return v;
  } catch {
    /* localStorage indisponível (modo privado etc.) — usa default */
  }
  return DEFAULT_THEME;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeDir>(readStoredTheme);

  // Aplica o data-dir no <html> e persiste sempre que o tema muda.
  useEffect(() => {
    document.documentElement.setAttribute("data-dir", theme);
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const setTheme = useCallback((dir: ThemeDir) => setThemeState(dir), []);
  const toggleTheme = useCallback(
    () => setThemeState((t) => (t === "claro" ? "grafite" : "claro")),
    [],
  );

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme deve ser usado dentro de <ThemeProvider>");
  }
  return ctx;
}
