import { useEffect } from "react";
import { Switch, Route, Redirect, useLocation } from "wouter";
import { NavContext } from "@/components/AppLayout";
// Telas v2 — redesign fiel ao protótipo ai/design (sistema/, tema claro, vb.css).
import Dashboard from "@/pages-v2/Dashboard";
import Regras from "@/pages-v2/Regras";
import FilaAuditor from "@/pages-v2/fila/FilaAuditor";
import Custos from "@/pages-v2/Custos";
import Supervisor from "@/pages-v2/Supervisor";
import AnaliseSupervisor from "@/pages-v2/AnaliseSupervisor";
import Usuarios from "@/pages-v2/Usuarios";
import Relatorios from "@/pages-v2/Relatorios";
import Medicao from "@/pages-v2/Medicao";
import Agendamento from "@/pages-v2/Agendamento";
import { useAuth } from "@/contexts/AuthContext";
import { AdminLogin } from "@/components/AdminLogin";

// ─────────────────────────────────────────────────────────────────────────────
// Routing — telas de requisito (spec v2): Fila do Auditor (imersiva), Dashboard,
// Regras. Telas legadas removidas (ver commit de limpeza). wouter cuida do
// history; NavContext segue exposto pra compat das páginas mantidas.
// ─────────────────────────────────────────────────────────────────────────────

export const PAGE_TO_PATH: Record<string, (hash?: string | null) => string> = {
  "Fila do Auditor": () => "/fila-auditor",
  "Dashboard": () => "/dashboard",
  "Regras": () => "/regras",
  "Custos": () => "/custos",
  "Supervisor": () => "/supervisor",
  "Usuários": () => "/admin/usuarios",
  "Relatórios": () => "/relatorios",
  "Medição": () => "/medicao",
  "Agendamento": () => "/agendamento",
};

function pathToPage(path: string): string {
  if (path.startsWith("/dashboard")) return "Dashboard";
  if (path.startsWith("/regras")) return "Regras";
  if (path.startsWith("/custos")) return "Custos";
  if (path.startsWith("/supervisor")) return "Supervisor";
  if (path.startsWith("/admin/usuarios")) return "Usuários";
  if (path.startsWith("/relatorios")) return "Relatórios";
  if (path.startsWith("/medicao")) return "Medição";
  if (path.startsWith("/agendamento")) return "Agendamento";
  return "Fila do Auditor"; // /fila-auditor (e /fila legado redireciona)
}

export default function App() {
  const { email, isAdmin, loading, mustChangePassword, setEmail, loginWithPassword, changePassword } =
    useAuth();
  const [location, setLocation] = useLocation();
  const selectedHash = null;

  // Compat shim — páginas chamam nav.navigate(page, hash).
  const navigate = (p: string, hash?: string | null) => {
    const builder = PAGE_TO_PATH[p];
    if (builder) setLocation(builder(hash));
  };

  // Atalhos ⌘+1..3 → telas mantidas.
  useEffect(() => {
    const SHORTCUTS = ["Fila do Auditor", "Dashboard", "Regras"];
    const handler = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return;
      const meta = e.metaKey || e.ctrlKey;
      if (meta && /^[1-9]$/.test(e.key)) {
        e.preventDefault();
        const name = SHORTCUTS[parseInt(e.key, 10) - 1];
        if (name && PAGE_TO_PATH[name]) setLocation(PAGE_TO_PATH[name]());
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setLocation]);

  // Splash enquanto AuthContext valida sessão.
  if (loading) {
    return (
      <div className="fixed inset-0 bg-[#040814] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-2 border-cyan-500/30 border-t-cyan-400 animate-spin" />
          <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-400/80 font-medium">
            Validando sessão…
          </p>
        </div>
      </div>
    );
  }

  // Sem sessão → tela de login.
  // /admin tem porta de entrada própria, com senha (admin_users). As demais
  // URLs caem no <Login> piloto (email sem senha) pra não quebrar a UX atual.
  if (!email) {
    // Login único com senha. `mustChangePassword` (senha temporária pós-reset)
    // vive no AuthContext e SOBREVIVE ao remount do AdminLogin — sem ele, o
    // splash de loading desmonta o AdminLogin durante o login e o passo de troca
    // (state local) se perde, voltando pro login. Passamos como `forceChangeEmail`
    // para o AdminLogin reabrir já no modo "defina nova senha".
    return (
      <AdminLogin
        forceChangeEmail={mustChangePassword}
        onSubmit={(e, p) => loginWithPassword(e, p)}
        onChangePassword={(e, atual, nova) => changePassword(e, atual, nova)}
      />
    );
  }

  const activePage = pathToPage(location);
  const defaultPath = isAdmin ? "/dashboard" : "/fila-auditor";

  return (
    <NavContext.Provider
      value={{ navigate, activePage, selectedHash, setSelectedHash: () => { /* noop — URL é a fonte de verdade */ } }}
    >
      <Switch>
        {/* Aliases / entry points */}
        <Route path="/"><Redirect to={defaultPath} /></Route>
        <Route path="/login"><Redirect to={defaultPath} /></Route>
        <Route path="/fila"><Redirect to="/fila-auditor" /></Route>
        {/* Já autenticado e veio pra /admin → manda pro painel. */}
        <Route path="/admin"><Redirect to={defaultPath} /></Route>

        {/* Telas de requisito */}
        <Route path="/fila-auditor" component={FilaAuditor} />
        <Route path="/dashboard" component={Dashboard} />
        <Route path="/regras" component={Regras} />
        <Route path="/custos" component={Custos} />
        <Route path="/supervisor" component={Supervisor} />
        <Route path="/supervisor/analise/:id">
          {(params) => <AnaliseSupervisor os={params.id} />}
        </Route>
        <Route path="/admin/usuarios" component={Usuarios} />
        <Route path="/relatorios" component={Relatorios} />
        <Route path="/medicao" component={Medicao} />
        <Route path="/agendamento" component={Agendamento} />

        {/* Fallback → default */}
        <Route><Redirect to={defaultPath} /></Route>
      </Switch>
    </NavContext.Provider>
  );
}
