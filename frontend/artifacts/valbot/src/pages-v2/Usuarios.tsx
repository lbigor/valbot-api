/* ============================================================================
   ValBot — Usuários (admin_users · migration 018) — CRUD + perfis/permissões
   Porte fiel de .design-ref/page-usuarios.jsx
   Religado a /api/admin/users (dados reais) via @tanstack/react-query.
   ============================================================================ */
import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/system/Shell";
import { Kpi, fmt } from "@/system/ui";
import { I } from "@/system/icons";

/* linha de usuário editável: last_login_at pode ser null em conta nova */
interface UserRow {
  id: string;
  email: string;
  nome: string;
  role: "admin" | "supervisor" | "auditor";
  created_at: Date;
  last_login_at: Date | null;
  revoked_at: Date | null;
}

type Role = UserRow["role"];

/* item cru vindo de GET /api/admin/users (sem `nome` — derivamos do e-mail) */
interface ApiUser {
  id: string | number;
  email: string;
  role: Role;
  created_at: string | null;
  last_login_at: string | null;
  revoked_at: string | null;
}

/* display name: parte antes do @, "ponto/underscore" → espaço, capitalizado.
   ex.: "renata.moura@x" → "Renata Moura"; sem local-part válido → e-mail cru */
const nomeFromEmail = (email: string): string => {
  const local = (email || "").split("@")[0] || "";
  if (!local) return email || "";
  const parts = local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1));
  return parts.length ? parts.join(" ") : email;
};

const toRow = (u: ApiUser): UserRow => ({
  id: String(u.id),
  email: u.email,
  nome: nomeFromEmail(u.email),
  role: u.role,
  created_at: u.created_at ? new Date(u.created_at) : new Date(),
  last_login_at: u.last_login_at ? new Date(u.last_login_at) : null,
  revoked_at: u.revoked_at ? new Date(u.revoked_at) : null,
});

/* ---- Fetchers (credentials:include) -------------------------------------- */
async function listUsers(): Promise<UserRow[]> {
  const r = await fetch("/api/admin/users", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const d = await r.json();
  const items: ApiUser[] = Array.isArray(d) ? d : (d?.items ?? []);
  return items.map(toRow);
}
async function createUser(body: { email: string; role: Role; password: string }): Promise<void> {
  const r = await fetch("/api/admin/users", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
}
async function patchUser(
  id: string,
  body: { role?: Role; revoked?: boolean },
): Promise<void> {
  const r = await fetch(`/api/admin/users/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
}
async function resetPassword(id: string): Promise<string> {
  const r = await fetch(`/api/admin/users/${id}/reset-password`, {
    method: "POST",
    credentials: "include",
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
  const d = await r.json();
  return d?.senha_temporaria ?? "";
}

const ROLE_META: Record<Role, { label: string; cls: string; desc: string }> = {
  admin: { label: "Admin", cls: "bad", desc: "Acesso total · gestão de usuários e regras" },
  supervisor: { label: "Supervisor", cls: "proc", desc: "Arbitra divergências · decisão final" },
  auditor: { label: "Auditor", cls: "ok", desc: "Revisa exames e emite parecer" },
};
const PERMISSOES: { k: string; admin: boolean; supervisor: boolean; auditor: boolean }[] = [
  { k: "Ver fila e exames", admin: true, supervisor: true, auditor: true },
  { k: "Emitir parecer (1ª instância)", admin: true, supervisor: true, auditor: true },
  { k: "Decisão final (arbitragem)", admin: true, supervisor: true, auditor: false },
  { k: "Editar matriz de regras", admin: true, supervisor: false, auditor: false },
  { k: "Ver custos e medição", admin: true, supervisor: true, auditor: false },
  { k: "Gerenciar usuários", admin: true, supervisor: false, auditor: false },
  { k: "Configurar agendamentos", admin: true, supervisor: false, auditor: false },
];

interface EditState {
  mode: "new" | "edit";
  user: UserRow;
}

export default function Usuarios() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["v2-admin-users"],
    queryFn: listUsers,
  });
  const users = useMemo<UserRow[]>(() => data ?? [], [data]);

  const [q, setQ] = useState("");
  const [rf, setRf] = useState<"todos" | Role>("todos");
  const [edit, setEdit] = useState<EditState | null>(null); // {mode, user}
  const [pwReset, setPwReset] = useState<{ nome: string; senha: string } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => {
    setToast(m);
    clearTimeout((window as any).__t);
    (window as any).__t = setTimeout(() => setToast(null), 1900);
  };
  const refresh = () => qc.invalidateQueries({ queryKey: ["v2-admin-users"] });

  const mCreate = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      setEdit(null);
      refresh();
      flash("Usuário criado");
    },
    onError: (e: Error) => flash("Falha ao criar: " + e.message),
  });
  const mEditRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) => patchUser(id, { role }),
    onSuccess: () => {
      setEdit(null);
      refresh();
      flash("Usuário atualizado");
    },
    onError: (e: Error) => flash("Falha ao editar: " + e.message),
  });
  const mToggle = useMutation({
    mutationFn: ({ id, revoked }: { id: string; revoked: boolean }) =>
      patchUser(id, { revoked }),
    onSuccess: (_d, v) => {
      refresh();
      flash(v.revoked ? "Acesso revogado" : "Acesso reativado");
    },
    onError: (e: Error) => flash("Falha: " + e.message),
  });
  const mReset = useMutation({
    mutationFn: ({ id }: { id: string; nome: string }) => resetPassword(id),
    onSuccess: (temp, v) =>
      temp ? setPwReset({ nome: v.nome, senha: temp }) : flash("Senha redefinida"),
    onError: (e: Error) => flash("Falha no reset: " + e.message),
  });

  const ativos = users.filter((u) => !u.revoked_at);
  const counts = {
    admin: ativos.filter((u) => u.role === "admin").length,
    supervisor: ativos.filter((u) => u.role === "supervisor").length,
    auditor: ativos.filter((u) => u.role === "auditor").length,
  };
  const shown = useMemo(
    () =>
      users.filter(
        (u) =>
          (rf === "todos" || u.role === rf) &&
          (!q || (u.nome + u.email).toLowerCase().includes(q.toLowerCase())),
      ),
    [users, rf, q],
  );

  /* roteia o save do modal: novo → POST; edição → PATCH role */
  const save = (u: UserRow, password: string) => {
    if (edit?.mode === "new") {
      mCreate.mutate({ email: u.email.trim().toLowerCase(), role: u.role, password });
    } else {
      mEditRole.mutate({ id: u.id, role: u.role });
    }
  };
  const toggleRevoke = (u: UserRow) => {
    mToggle.mutate({ id: u.id, revoked: !u.revoked_at });
  };

  const actions = (
    <button
      className="btn btn-primary"
      onClick={() =>
        setEdit({
          mode: "new",
          user: {
            id: "u" + Date.now(),
            nome: "",
            email: "",
            role: "auditor",
            created_at: new Date(),
            last_login_at: null,
            revoked_at: null,
          },
        })
      }
    >
      <I.plus w={16} />
      Novo usuário
    </button>
  );

  return (
    <Shell
      active="usuarios"
      title="Usuários"
      sub="Contas do painel · perfis e permissões de acesso"
      actions={actions}
    >
      <div className="grid g-4">
        <Kpi
          icon={I.usuarios}
          label="Usuários ativos"
          value={ativos.length}
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
          foot={<span>{users.length - ativos.length} revogado(s)</span>}
        />
        <Kpi
          icon={I.supervisor}
          label="Admins"
          value={counts.admin}
          iconColor="var(--bad)"
          iconBg="var(--bad-bg)"
        />
        <Kpi
          icon={I.check}
          label="Supervisores"
          value={counts.supervisor}
          iconColor="var(--proc)"
          iconBg="var(--proc-bg)"
        />
        <Kpi
          icon={I.fila}
          label="Auditores"
          value={counts.auditor}
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
        />
      </div>

      <div className="row wrap" style={{ marginTop: 18, marginBottom: 14 }}>
        <div className="search">
          <I.search />
          <input
            placeholder="Buscar por nome ou e-mail…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        {(
          [
            ["todos", "Todos"],
            ["admin", "Admins"],
            ["supervisor", "Supervisores"],
            ["auditor", "Auditores"],
          ] as [("todos" | Role), string][]
        ).map(([k, l]) => (
          <button
            key={k}
            className={"chip" + (rf === k ? " on" : "")}
            onClick={() => setRf(k)}
          >
            {l}
            <span className="chip-n">
              {k === "todos" ? users.length : users.filter((u) => u.role === k).length}
            </span>
          </button>
        ))}
      </div>

      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Usuário</th>
              <th>Perfil</th>
              <th>Criado em</th>
              <th>Último acesso</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {shown.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className="row" style={{ gap: 10 }}>
                    <span className="sb-ava" style={{ width: 34, height: 34, fontSize: 12 }}>
                      {u.nome
                        .split(" ")
                        .map((x) => x[0])
                        .slice(0, 2)
                        .join("")}
                    </span>
                    <div>
                      <div className="t-strong">{u.nome}</div>
                      <div className="t-sub mono">{u.email}</div>
                    </div>
                  </div>
                </td>
                <td>
                  <span className={"badge " + ROLE_META[u.role].cls}>
                    <span className="bd" />
                    {ROLE_META[u.role].label}
                  </span>
                </td>
                <td className="t-sub mono">{fmt.dmy(u.created_at)}</td>
                <td className="t-sub">{u.last_login_at ? fmt.ago(u.last_login_at) : "—"}</td>
                <td>
                  {u.revoked_at ? (
                    <span className="badge neutral">
                      <span className="bd" />
                      revogado
                    </span>
                  ) : (
                    <span className="badge ok">
                      <span className="bd" />
                      ativo
                    </span>
                  )}
                </td>
                <td>
                  <div className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                    <button
                      className="icon-btn"
                      style={{ width: 32, height: 32 }}
                      title="Editar"
                      onClick={() => setEdit({ mode: "edit", user: { ...u } })}
                    >
                      <I.edit w={15} />
                    </button>
                    <button
                      className="icon-btn"
                      style={{ width: 32, height: 32 }}
                      title="Resetar senha"
                      onClick={() => mReset.mutate({ id: u.id, nome: u.nome })}
                    >
                      <I.bolt w={15} />
                    </button>
                    <button
                      className="icon-btn"
                      style={{ width: 32, height: 32 }}
                      title={u.revoked_at ? "Reativar" : "Revogar"}
                      onClick={() => toggleRevoke(u)}
                    >
                      {u.revoked_at ? <I.check w={15} /> : <I.trash w={15} />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="tbl-foot">
          <I.usuarios w={14} />
          {isLoading
            ? "Carregando…"
            : isError
              ? "Falha ao carregar usuários"
              : `${shown.length} usuário(s) · autenticação por e-mail + senha (PBKDF2)`}
        </div>
      </div>

      {/* matriz de permissões */}
      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-h">
          <h2>Matriz de permissões por perfil</h2>
        </div>
        <div className="tbl-wrap" style={{ border: "none", boxShadow: "none", borderRadius: 0 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Permissão</th>
                {(Object.keys(ROLE_META) as Role[]).map((r) => (
                  <th key={r} style={{ textAlign: "center" }}>
                    {ROLE_META[r].label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PERMISSOES.map((p, i) => (
                <tr key={i}>
                  <td className="t-strong">{p.k}</td>
                  {(["admin", "supervisor", "auditor"] as Role[]).map((r) => (
                    <td key={r} style={{ textAlign: "center", verticalAlign: "middle" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: "100%",
                          lineHeight: 1,
                          color: p[r] ? "var(--ok)" : undefined,
                        }}
                        className={p[r] ? undefined : "faint"}
                      >
                        {p[r] ? <I.check w={17} /> : "—"}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {edit && (
        <UserModal
          mode={edit.mode}
          user={edit.user}
          pending={mCreate.isPending || mEditRole.isPending}
          onSave={save}
          onClose={() => setEdit(null)}
        />
      )}
      {pwReset && (
        <ResetPasswordModal
          nome={pwReset.nome}
          senha={pwReset.senha}
          onClose={() => setPwReset(null)}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </Shell>
  );
}

interface UserModalProps {
  mode: "new" | "edit";
  user: UserRow;
  pending: boolean;
  onSave: (u: UserRow, password: string) => void;
  onClose: () => void;
}

function UserModal({ mode, user, pending, onSave, onClose }: UserModalProps) {
  const [u, setU] = useState<UserRow>(user);
  const [password, setPassword] = useState("");
  const set = <K extends keyof UserRow>(k: K, v: UserRow[K]) =>
    setU((x) => ({ ...x, [k]: v }));
  /* novo → exige e-mail válido + senha ≥6; edição → só troca papel */
  const valid =
    mode === "new" ? /\S+@\S+\.\S+/.test(u.email) && password.length >= 6 : true;
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="modal">
        <div style={{ padding: "20px 22px 0" }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              color: "var(--brand)",
              fontWeight: 700,
            }}
          >
            {mode === "new" ? "Novo usuário" : "Editar usuário"}
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 3 }}>
            {mode === "new" ? "Criar conta" : u.nome}
          </div>
        </div>
        <div style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="fld">
            <label className="fld-l">E-mail</label>
            <input
              className="mono"
              value={u.email}
              disabled={mode === "edit"}
              onChange={(e) => set("email", e.target.value)}
              placeholder="usuario@valmatech.com.br"
            />
          </div>
          {mode === "new" && (
            <div className="fld">
              <label className="fld-l">Senha inicial</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="mínimo 6 caracteres"
              />
            </div>
          )}
          <div className="fld">
            <label className="fld-l">Perfil de acesso</label>
            <div className="grid g-3" style={{ gap: 8 }}>
              {(Object.entries(ROLE_META) as [Role, (typeof ROLE_META)[Role]][]).map(([k, m]) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => set("role", k)}
                  style={{
                    textAlign: "left",
                    padding: "10px 12px",
                    borderRadius: 10,
                    border:
                      "1px solid " +
                      (u.role === k ? "var(--brand-500)" : "var(--border-strong)"),
                    background: u.role === k ? "var(--brand-tint)" : "var(--surface)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: u.role === k ? "var(--brand)" : "var(--ink)",
                    }}
                  >
                    {m.label}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--muted)",
                      lineHeight: 1.35,
                      marginTop: 2,
                    }}
                  >
                    {m.desc}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="drawer-f" style={{ borderRadius: "0 0 var(--r-xl) var(--r-xl)" }}>
          <button className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onSave(u, password)}
            disabled={!valid || pending}
          >
            {mode === "new" ? "Criar usuário" : "Salvar"}
          </button>
        </div>
      </div>
    </>
  );
}

interface ResetPasswordModalProps {
  nome: string;
  senha: string;
  onClose: () => void;
}

/* visualização única estilo "API key": a senha aparece uma vez, copia-se e
   fecha-se manualmente — sem auto-dismiss. */
function ResetPasswordModal({ nome, senha, onClose }: ResetPasswordModalProps) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard
      .writeText(senha)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      })
      .catch(() => {});
  };
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="modal">
        <div style={{ padding: "20px 22px 0" }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              color: "var(--brand)",
              fontWeight: 700,
            }}
          >
            Senha redefinida
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 3 }}>{nome}</div>
        </div>
        <div style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div
            style={{
              fontSize: 12.5,
              lineHeight: 1.45,
              color: "var(--muted)",
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid var(--border-strong)",
              background: "var(--brand-tint)",
            }}
          >
            Esta senha será exibida apenas <strong>UMA vez</strong>. Copie e envie ao usuário com
            segurança.
          </div>
          <div className="fld">
            <label className="fld-l">Senha temporária</label>
            <div className="row" style={{ gap: 8, alignItems: "stretch" }}>
              <div
                className="mono"
                style={{
                  flex: 1,
                  userSelect: "all",
                  fontSize: 18,
                  fontWeight: 700,
                  letterSpacing: ".02em",
                  padding: "12px 14px",
                  borderRadius: 10,
                  border: "1px solid var(--border-strong)",
                  background: "var(--surface)",
                  color: "var(--ink)",
                  wordBreak: "break-all",
                }}
              >
                {senha}
              </div>
              <button
                className="btn"
                type="button"
                onClick={copy}
                style={{ whiteSpace: "nowrap" }}
              >
                {copied ? "Copiado!" : "Copiar"}
              </button>
            </div>
          </div>
        </div>
        <div className="drawer-f" style={{ borderRadius: "0 0 var(--r-xl) var(--r-xl)" }}>
          <button className="btn btn-primary" type="button" onClick={onClose}>
            Fechar
          </button>
        </div>
      </div>
    </>
  );
}
