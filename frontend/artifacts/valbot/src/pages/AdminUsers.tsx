import { type ReactNode, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users,
  UserPlus,
  Pencil,
  Ban,
  RotateCcw,
  KeyRound,
  ShieldCheck,
  X,
  Copy,
  Check,
} from "lucide-react";
import "./AdminUsers.css";

// Tela de Cadastro de Usuário (admin) — CRUD de contas Valbot.
// Consome /api/admin/users (lista/criação) e /api/admin/users/{id} (edição/revogação).
// Senha só trafega no POST de criação e no reset; a temp retornada é exibida uma vez ao admin.

type Role = "admin" | "auditor" | "supervisor";
const ROLES: Role[] = ["admin", "auditor", "supervisor"];
const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  auditor: "Auditor",
  supervisor: "Supervisor",
};

interface AdminUser {
  id: string | number;
  email: string;
  role: Role;
  created_at: string | null;
  last_login_at: string | null;
  revoked_at: string | null;
}

const fmtDate = (s: string | null) =>
  s ? new Date(s).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

// ---- Fetchers inline (credentials:include) ---------------------------------
async function listUsers(): Promise<AdminUser[]> {
  const r = await fetch("/api/admin/users", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const d = await r.json(); return (Array.isArray(d) ? d : (d?.items ?? [])) as AdminUser[];
}
async function createUser(body: { email: string; role: Role; password: string }): Promise<AdminUser> {
  const r = await fetch("/api/admin/users", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
  return r.json() as Promise<AdminUser>;
}
async function patchUser(
  id: AdminUser["id"],
  body: { role?: Role; revoked?: boolean },
): Promise<AdminUser> {
  const r = await fetch(`/api/admin/users/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
  return r.json() as Promise<AdminUser>;
}
async function deleteUser(id: AdminUser["id"]): Promise<void> {
  const r = await fetch(`/api/admin/users/${id}`, { method: "DELETE", credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
}
async function resetPassword(id: AdminUser["id"]): Promise<{ temp_password: string }> {
  const r = await fetch(`/api/admin/users/${id}/reset-password`, {
    method: "POST",
    credentials: "include",
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
  return r.json() as Promise<{ temp_password: string }>;
}

// ---- Toast simples ---------------------------------------------------------
type Toast = { kind: "ok" | "err"; msg: string } | null;

function RoleBadge({ role }: { role: Role }) {
  return (
    <span className="au-badge" data-role={role}>
      {role === "admin" && <ShieldCheck size={12} />}
      {ROLE_LABEL[role] ?? role}
    </span>
  );
}
function StatusBadge({ revoked }: { revoked: boolean }) {
  return (
    <span className="au-status" data-revoked={revoked ? "1" : "0"}>
      <span className="au-dot" />
      {revoked ? "Revogado" : "Ativo"}
    </span>
  );
}

// ---- Modal de criação ------------------------------------------------------
function CreateModal({
  onClose,
  onCreate,
  pending,
  error,
}: {
  onClose: () => void;
  onCreate: (b: { email: string; role: Role; password: string }) => void;
  pending: boolean;
  error: string | null;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("auditor");
  const [password, setPassword] = useState("");
  const valid = /\S+@\S+\.\S+/.test(email) && password.length >= 6;
  return (
    <div className="au-overlay" onClick={onClose}>
      <div className="au-modal" onClick={(e) => e.stopPropagation()}>
        <div className="au-modal-head">
          <h3>Criar usuário</h3>
          <button className="au-icon-btn" onClick={onClose} aria-label="Fechar">
            <X size={16} />
          </button>
        </div>
        <label className="au-field">
          <span>Email</span>
          <input
            type="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="usuario@valbot.com.br"
          />
        </label>
        <label className="au-field">
          <span>Papel</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        </label>
        <label className="au-field">
          <span>Senha</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="mínimo 6 caracteres"
          />
        </label>
        {error && <p className="au-err">{error}</p>}
        <div className="au-modal-foot">
          <button className="au-btn-ghost" onClick={onClose} disabled={pending}>
            Cancelar
          </button>
          <button
            className="au-btn"
            disabled={!valid || pending}
            onClick={() => onCreate({ email: email.trim(), role, password })}
          >
            {pending ? "Criando…" : "Criar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Modal de edição de papel ----------------------------------------------
function EditModal({
  user,
  onClose,
  onSave,
  pending,
  error,
}: {
  user: AdminUser;
  onClose: () => void;
  onSave: (role: Role) => void;
  pending: boolean;
  error: string | null;
}) {
  const [role, setRole] = useState<Role>(user.role);
  return (
    <div className="au-overlay" onClick={onClose}>
      <div className="au-modal" onClick={(e) => e.stopPropagation()}>
        <div className="au-modal-head">
          <h3>Editar papel</h3>
          <button className="au-icon-btn" onClick={onClose} aria-label="Fechar">
            <X size={16} />
          </button>
        </div>
        <p className="au-sub">{user.email}</p>
        <label className="au-field">
          <span>Papel</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
        </label>
        {error && <p className="au-err">{error}</p>}
        <div className="au-modal-foot">
          <button className="au-btn-ghost" onClick={onClose} disabled={pending}>
            Cancelar
          </button>
          <button className="au-btn" disabled={pending} onClick={() => onSave(role)}>
            {pending ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Modal de senha temporária ---------------------------------------------
function TempPasswordModal({
  email,
  temp,
  onClose,
}: {
  email: string;
  temp: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(temp).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      },
      () => {},
    );
  };
  return (
    <div className="au-overlay" onClick={onClose}>
      <div className="au-modal" onClick={(e) => e.stopPropagation()}>
        <div className="au-modal-head">
          <h3>Senha temporária</h3>
          <button className="au-icon-btn" onClick={onClose} aria-label="Fechar">
            <X size={16} />
          </button>
        </div>
        <p className="au-sub">
          Repasse esta senha a <strong>{email}</strong> por canal seguro. Ela não será exibida novamente.
        </p>
        <div className="au-temp">
          <code className="mono">{temp}</code>
          <button className="au-icon-btn" onClick={copy} aria-label="Copiar">
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>
        <div className="au-modal-foot">
          <button className="au-btn" onClick={onClose}>
            Entendi
          </button>
        </div>
      </div>
    </div>
  );
}

export function AdminUsers() {
  const qc = useQueryClient();
  const { data: users, isLoading, isError } = useQuery({
    queryKey: ["admin-users"],
    queryFn: listUsers,
  });

  const [toast, setToast] = useState<Toast>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [tempPwd, setTempPwd] = useState<{ email: string; temp: string } | null>(null);

  const flash = (kind: "ok" | "err", msg: string) => {
    setToast({ kind, msg });
    setTimeout(() => setToast(null), 3500);
  };
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-users"] });

  const mCreate = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      setShowCreate(false);
      refresh();
      flash("ok", "Usuário criado.");
    },
    onError: (e: Error) => flash("err", "Falha ao criar: " + e.message),
  });
  const mEdit = useMutation({
    mutationFn: ({ id, role }: { id: AdminUser["id"]; role: Role }) => patchUser(id, { role }),
    onSuccess: () => {
      setEditing(null);
      refresh();
      flash("ok", "Papel atualizado.");
    },
    onError: (e: Error) => flash("err", "Falha ao editar: " + e.message),
  });
  const mToggle = useMutation({
    mutationFn: ({ id, revoked }: { id: AdminUser["id"]; revoked: boolean }) =>
      patchUser(id, { revoked }),
    onSuccess: (_d, v) => {
      refresh();
      flash("ok", v.revoked ? "Usuário revogado." : "Usuário reativado.");
    },
    onError: (e: Error) => flash("err", "Falha: " + e.message),
  });
  const mReset = useMutation({
    mutationFn: (u: AdminUser) => resetPassword(u.id).then((r) => ({ email: u.email, temp: r.temp_password })),
    onSuccess: (r) => {
      setTempPwd(r);
      flash("ok", "Senha redefinida.");
    },
    onError: (e: Error) => flash("err", "Falha no reset: " + e.message),
  });

  return (
    <AppLayout activePage="Usuários">
      <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Cadastro de usuário</h1>
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              Gerencie contas, papéis e acesso ao Valbot.
            </p>
          </div>
          <button className="au-btn" onClick={() => setShowCreate(true)}>
            <UserPlus size={16} />
            Criar usuário
          </button>
        </div>

        {toast && (
          <div className="au-toast" data-kind={toast.kind}>
            {toast.msg}
          </div>
        )}

        <div className="au-panel">
          {isLoading && <p style={{ color: "var(--muted)", padding: 16 }}>Carregando…</p>}
          {isError && (
            <p style={{ color: "var(--danger, #EF4444)", padding: 16 }}>
              Não foi possível carregar os usuários.
            </p>
          )}
          {users && (
            <table className="au-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Papel</th>
                  <th>Criado em</th>
                  <th>Último login</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Ações</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 16, color: "var(--muted)" }}>
                      Nenhum usuário cadastrado.
                    </td>
                  </tr>
                )}
                {users.map((u) => {
                  const revoked = !!u.revoked_at;
                  return (
                    <tr key={u.id} data-revoked={revoked ? "1" : "0"}>
                      <td className="au-email">{u.email}</td>
                      <td>
                        <RoleBadge role={u.role} />
                      </td>
                      <td className="mono au-muted">{fmtDate(u.created_at)}</td>
                      <td className="mono au-muted">{fmtDate(u.last_login_at)}</td>
                      <td>
                        <StatusBadge revoked={revoked} />
                      </td>
                      <td>
                        <div className="au-actions">
                          <button
                            className="au-icon-btn"
                            title="Editar papel"
                            onClick={() => setEditing(u)}
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            className="au-icon-btn"
                            title="Reset de senha"
                            disabled={mReset.isPending}
                            onClick={() => mReset.mutate(u)}
                          >
                            <KeyRound size={15} />
                          </button>
                          {revoked ? (
                            <button
                              className="au-icon-btn au-ok"
                              title="Reativar"
                              disabled={mToggle.isPending}
                              onClick={() => mToggle.mutate({ id: u.id, revoked: false })}
                            >
                              <RotateCcw size={15} />
                            </button>
                          ) : (
                            <button
                              className="au-icon-btn au-danger"
                              title="Revogar"
                              disabled={mToggle.isPending}
                              onClick={() => mToggle.mutate({ id: u.id, revoked: true })}
                            >
                              <Ban size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreate={(b) => mCreate.mutate(b)}
          pending={mCreate.isPending}
          error={mCreate.isError ? (mCreate.error as Error).message : null}
        />
      )}
      {editing && (
        <EditModal
          user={editing}
          onClose={() => setEditing(null)}
          onSave={(role) => mEdit.mutate({ id: editing.id, role })}
          pending={mEdit.isPending}
          error={mEdit.isError ? (mEdit.error as Error).message : null}
        />
      )}
      {tempPwd && (
        <TempPasswordModal
          email={tempPwd.email}
          temp={tempPwd.temp}
          onClose={() => setTempPwd(null)}
        />
      )}
    </AppLayout>
  );
}

export default AdminUsers;
