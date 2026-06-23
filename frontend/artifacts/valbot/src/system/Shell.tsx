/* ============================================================================
   ValBot — Shell compartilhado: Sidebar (9 rotas) + Topbar + <Shell>
   Porte fiel de .design-ref/vb-shell.jsx, adaptado ao app real (wouter).
   ============================================================================ */
import type { ReactNode, JSX } from "react";
import { Link } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { I, type IconComponent } from "./icons";
import "./vb.css";

/* deriva nome legível e iniciais a partir do email logado */
function nomeDeEmail(email: string | null): string {
  if (!email) return "—";
  const local = email.split("@")[0];
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ") || email;
}
function iniciaisDeEmail(email: string | null): string {
  if (!email) return "?";
  return email.replace(/[^a-zA-Z]/g, "").slice(0, 2).toUpperCase() || "?";
}

/* id → rota real do app (mapeado a partir dos hrefs do protótipo) */
interface SidebarItem {
  id: string;
  label: string;
  icon: IconComponent;
  href: string;
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  { id: "fila", label: "Fila do Auditor", icon: I.fila, href: "/fila-auditor" },
  { id: "dashboard", label: "Dashboard", icon: I.dashboard, href: "/dashboard" },
  { id: "regras", label: "Regras", icon: I.regras, href: "/regras" },
  { id: "custos", label: "Custos", icon: I.custos, href: "/custos" },
  { id: "supervisor", label: "Supervisor", icon: I.supervisor, href: "/supervisor" },
  { id: "usuarios", label: "Usuários", icon: I.usuarios, href: "/admin/usuarios" },
  { id: "relatorios", label: "Relatórios", icon: I.relatorios, href: "/relatorios" },
  { id: "medicao", label: "Medição", icon: I.medicao, href: "/medicao" },
  { id: "agendamento", label: "Agendamento", icon: I.agendamento, href: "/agendamento" },
];

export interface SidebarProps {
  active?: string;
  /** badge da Fila do Auditor (não renderiza se 0) */
  filaCount?: number;
  /** badge do Supervisor (não renderiza se 0) */
  supCount?: number;
  userName?: string;
  userRole?: string;
  userInitials?: string;
}

interface BadgeSpec {
  n: number;
  cls: string;
}

export function Sidebar({
  active,
  filaCount = 0,
  supCount = 0,
  userName,
  userRole,
  userInitials,
}: SidebarProps): JSX.Element {
  const { email, isAdmin, logout } = useAuth();
  // DEFAULT vem do usuário logado (useAuth); props seguem como override opcional.
  const nome = userName ?? nomeDeEmail(email);
  const papel = userRole ?? (isAdmin ? "Admin" : "Revisor");
  const iniciais = userInitials ?? iniciaisDeEmail(email);

  const badge: Record<string, BadgeSpec> = {
    fila: { n: filaCount, cls: "warn" },
    supervisor: { n: supCount, cls: "brand" },
  };
  return (
    <aside className="sb">
      <div className="sb-brand">
        <img
          src="/logo.png"
          alt="ValBot"
          className="sb-mark"
          style={{ objectFit: "cover", background: "none", boxShadow: "0 4px 12px rgba(67,56,202,.22)" }}
        />
        <div>
          <div className="bn">ValBot</div>
          <div className="bs">Auditoria Inteligente</div>
        </div>
      </div>
      <div className="sb-section">Operação</div>
      <nav className="sb-nav">
        {SIDEBAR_ITEMS.map((it) => {
          const Ico = it.icon;
          const b = badge[it.id];
          return (
            <Link
              key={it.id}
              href={it.href}
              className={"sb-item" + (active === it.id ? " on" : "")}
            >
              <Ico w={18} />
              {it.label}
              {b && b.n > 0 && <span className={"sb-badge " + b.cls}>{b.n}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="sb-user">
        <span className="sb-ava">{iniciais}</span>
        <div style={{ minWidth: 0 }}>
          <div className="un" title={email ?? undefined}>{nome}</div>
          <div className="ur">{papel}</div>
        </div>
        <button className="sb-logout" title="Sair" onClick={() => logout()}>
          <I.logout w={16} />
        </button>
      </div>
    </aside>
  );
}

export interface TopbarProps {
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
}

export function Topbar({ title, sub, actions }: TopbarProps): JSX.Element {
  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      <div className="topbar-actions">
        {actions}
        <button className="icon-btn" title="Buscar">
          <I.search w={17} />
        </button>
        <button className="icon-btn" title="Alertas">
          <I.bell w={17} />
        </button>
      </div>
    </header>
  );
}

export interface ShellProps {
  active?: string;
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  /** badges + identidade do usuário (ligados ao auth real depois) */
  filaCount?: number;
  supCount?: number;
  userName?: string;
  userRole?: string;
  userInitials?: string;
}

export function Shell({
  active,
  title,
  sub,
  actions,
  children,
  filaCount,
  supCount,
  userName,
  userRole,
  userInitials,
}: ShellProps): JSX.Element {
  return (
    <div className="app">
      <Sidebar
        active={active}
        filaCount={filaCount}
        supCount={supCount}
        userName={userName}
        userRole={userRole}
        userInitials={userInitials}
      />
      <div className="main">
        <Topbar title={title} sub={sub} actions={actions} />
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

export default Shell;
