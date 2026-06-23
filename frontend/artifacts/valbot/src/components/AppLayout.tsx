import React from "react";
import {
  LayoutDashboard,
  ListFilter, DollarSign, Users, Activity, Clock,
  AlertTriangle,
  FileText,
  ShieldCheck,
  BookOpen,
  Settings,
  Bell,
  Search,
  ChevronRight,
  LogOut,
  Crown,
  GalleryVerticalEnd,
  Film,
  Wrench,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "wouter";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/contexts/AuthContext";

export const NavContext = React.createContext<{
  navigate?: (page: string, hash?: string | null) => void;
  activePage?: string;
  selectedHash?: string | null;
  setSelectedHash?: (h: string | null) => void;
}>({});

// Items com `adminOnly: true` só aparecem no sidebar para admins. Revisores
// comuns só precisam da Fila Operacional (+ Análise do Exame, alcançada pela fila).
// `path` é a URL real (wouter Link) — URL bookmarkável + browser back/forward funciona.
const SIDEBAR_ITEMS = [
  { id: "Fila do Auditor", label: "Fila do Auditor", icon: ListFilter, path: "/fila-auditor", adminOnly: false },
  { id: "Dashboard", label: "Dashboard", icon: LayoutDashboard, path: "/dashboard", adminOnly: true },
  { id: "Regras", label: "Regras", icon: BookOpen, path: "/regras", adminOnly: true },
  { id: "Custos", label: "Custos", icon: DollarSign, path: "/custos", adminOnly: true },
  { id: "Supervisor", label: "Supervisor", icon: ShieldCheck, path: "/supervisor", adminOnly: true },
  { id: "Usuários", label: "Usuários", icon: Users, path: "/admin/usuarios", adminOnly: true },
  { id: "Relatórios", label: "Relatórios", icon: FileText, path: "/relatorios", adminOnly: true },
  { id: "Medição", label: "Medição", icon: Activity, path: "/medicao", adminOnly: true },
  { id: "Agendamento", label: "Agendamento", icon: Clock, path: "/agendamento", adminOnly: true },
];

export function AppLayout({
  activePage,
  children,
}: {
  activePage: string;
  children: React.ReactNode;
}) {
  const nav = React.useContext(NavContext);
  const [location] = useLocation();
  // Identifica página ativa pela URL — fonte de verdade é wouter, não state.
  const currentPage = nav.activePage ?? activePage;
  const { email, isAdmin, logout } = useAuth();

  // Counts dinâmicos pra badges (alertas + fila)
  const { data: alertas } = useQuery<any[]>({
    queryKey: ["alertas-count"],
    queryFn: async () => {
      const r = await fetch("/api/alertas");
      if (!r.ok) return [];
      return r.json();
    },
    enabled: !!email,
    refetchInterval: 30000,
  });
  const alertasCount = (alertas ?? []).filter(
    (a: any) => (a.status ?? "Pendente") === "Pendente",
  ).length;
  const { data: videos } = useQuery<any[]>({
    queryKey: ["fila-count"],
    queryFn: async () => {
      // Badge = conteúdo da Fila do Auditor: exames divergentes (só os que
      // ainda divergem após o Comitê), MESMA fonte/filtro da tela.
      const r = await fetch("/api/videos?only_unresolved=true");
      if (!r.ok) return [];
      const d = await r.json();
      return Array.isArray(d) ? d : (d?.items ?? d?.videos ?? []);
    },
    enabled: !!email,
    refetchInterval: 30000,
  });
  const filaCount = (videos ?? []).filter(
    (v: any) => v.has_result && v.status === "processed",
  ).length;

  // Status do VLM (Claude Haiku) — só ativo se ANTHROPIC_API_KEY no backend
  const { data: vlmStatus } = useQuery<any>({
    queryKey: ["vlm-status"],
    queryFn: async () => {
      const r = await fetch("/api/vlm-status");
      if (!r.ok) return null;
      return r.json();
    },
    enabled: !!email,
    refetchInterval: 60000,
  });
  const initials = (email ?? "?")
    .split("@")[0]
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#060D1A] text-[#F9FAFB] font-sans selection:bg-[#1D4ED8] selection:text-white">
      {/* Sidebar */}
      <aside className="w-[240px] flex flex-col border-r border-[#1F2937] bg-[#0B1120] shrink-0">
        {/* Logo area */}
        <div className="flex flex-col justify-center h-16 px-6 border-b border-[#1F2937]">
          <h1 className="text-2xl font-bold text-[#06B6D4] leading-tight">
            VALBOT
          </h1>
          <span className="text-[10px] text-[#9CA3AF] uppercase tracking-wider font-semibold">
            Auditoria Inteligente
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {SIDEBAR_ITEMS.filter((item) => isAdmin || !item.adminOnly).map((item) => {
            const Icon = item.icon;
            const isActive = currentPage === item.id || location.startsWith(item.path);
            return (
              <Link
                key={item.id}
                href={item.path}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
                  isActive
                    ? "bg-[#1D4ED8]/10 text-[#06B6D4] border border-[#06B6D4]/20"
                    : "text-[#9CA3AF] hover:bg-[#111827] hover:text-[#F9FAFB]"
                }`}
              >
                <Icon
                  size={18}
                  className={isActive ? "text-[#06B6D4]" : "text-[#9CA3AF]"}
                />
                {item.label}
                {item.id === "Alertas" && alertasCount > 0 && (
                  <span className="ml-auto flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-[#EF4444] text-[9px] font-bold text-white">
                    {alertasCount}
                  </span>
                )}
                {item.id === "Fila do Auditor" && filaCount > 0 && (
                  <span className="ml-auto flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-[#F59E0B] text-[9px] font-bold text-white">
                    {filaCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* VLM status compact */}
        {vlmStatus && (
          <div
            className="mx-3 mb-2 px-2.5 py-1.5 rounded text-[10px] font-mono flex items-center gap-1.5"
            style={{
              background: vlmStatus.active ? "rgba(16,185,129,0.10)" : "rgba(107,114,128,0.10)",
              color: vlmStatus.active ? "#10B981" : "#6B7280",
              border: `1px solid ${vlmStatus.active ? "rgba(16,185,129,0.30)" : "#1F2937"}`,
            }}
            title={vlmStatus.philosophy}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${vlmStatus.active ? "bg-[#10B981]" : "bg-[#6B7280]"}`} />
            VLM {vlmStatus.active ? "ativo (Haiku)" : "off · só heurística"}
          </div>
        )}

        {/* User Profile */}
        <div className="p-4 border-t border-[#1F2937] bg-[#0B1120]">
          <div className="flex items-center gap-3">
            <Avatar className="h-9 w-9 border border-[#1F2937] shrink-0">
              <AvatarFallback className="bg-[#111827] text-[#06B6D4] text-xs">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="flex flex-col text-left min-w-0 flex-1">
              <span className="text-sm font-medium text-[#F9FAFB] truncate" title={email ?? ""}>
                {email ?? "—"}
              </span>
              <span className="text-xs text-[#9CA3AF] flex items-center gap-1">
                {isAdmin && <Crown size={10} className="text-[#F59E0B]" />}
                {isAdmin ? "Admin" : "Revisor"}
              </span>
            </div>
            <button
              onClick={() => logout()}
              title="Trocar usuário"
              className="text-[#9CA3AF] hover:text-[#EF4444] transition-colors shrink-0"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-[56px] flex items-center justify-between px-6 border-b border-[#1F2937] bg-[#0B1120] shrink-0">
          <div className="flex items-center text-sm text-[#9CA3AF]">
            <span>VALBOT</span>
            <ChevronRight size={14} className="mx-2" />
            <span className="text-[#F9FAFB] font-medium">{currentPage}</span>
          </div>

          <div className="flex items-center gap-5">
            <div className="relative">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]"
              />
              <input
                type="text"
                placeholder="Buscar exames, alertas..."
                className="h-8 w-64 bg-[#111827] border border-[#1F2937] rounded-md pl-9 pr-3 text-sm text-[#F9FAFB] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#1D4ED8]"
              />
            </div>
            <Link
              href="/alertas"
              className="relative text-[#9CA3AF] hover:text-[#F9FAFB] transition-colors cursor-pointer"
              title={alertasCount > 0 ? `${alertasCount} alerta(s) pendente(s)` : "Sem alertas pendentes"}
            >
              <Bell size={20} />
              {alertasCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 min-w-4 px-1 items-center justify-center rounded-full bg-[#EF4444] text-[9px] font-bold text-white border border-[#0B1120]">
                  {alertasCount > 99 ? "99+" : alertasCount}
                </span>
              )}
            </Link>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#060D1A]">
          {children}
        </main>
      </div>
    </div>
  );
}
