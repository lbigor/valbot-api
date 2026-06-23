import { createContext, useContext, useEffect, useState, ReactNode } from "react";

/**
 * Gate por email simples — sem senha. O usuário digita um email na entrada,
 * o backend valida formato e devolve cookie httpOnly com duração de 90 dias.
 *
 * Fonte da verdade: o cookie httpOnly retornado por /api/auth/me.
 * localStorage é só hint local de UX (último email digitado) — nunca
 * decide sozinho se o usuário está autenticado.
 *
 * Fluxo de inicialização:
 *   1. mount → start em loading=true, email=null
 *   2. GET /api/auth/me com credentials:"include"
 *      - 200  → seta email + isAdmin a partir da resposta
 *      - !200 → mantém email=null (App renderiza <Login>)
 *   3. loading=false
 */

/**
 * Resultado de uma tentativa de login. Quando a senha é temporária (reset do
 * admin), o backend NÃO emite cookie e devolve `must_change_password: true`;
 * sinalizamos isso ao chamador para que ele exiba o passo de troca de senha.
 */
type LoginResult = {
  email: string;
  is_admin: boolean;
  must_change_password?: boolean;
};

type AuthState = {
  email: string | null;
  isAdmin: boolean;
  loading: boolean;
  /** Email com senha temporária aguardando troca obrigatória (ou null). */
  mustChangePassword: string | null;
  setEmail: (email: string) => Promise<LoginResult>;
  loginWithPassword: (email: string, password: string) => Promise<LoginResult>;
  /**
   * Troca a senha (foco: pós-reset). Valida `senhaAtual` (a temporária) e grava
   * `novaSenha`; em sucesso o backend emite o cookie e populamos a sessão como
   * no login. Rejeita com Error.message exibível.
   */
  changePassword: (
    email: string,
    senhaAtual: string,
    novaSenha: string,
  ) => Promise<LoginResult>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({
  email: null,
  isAdmin: false,
  loading: true,
  mustChangePassword: null,
  setEmail: async () => ({ email: "", is_admin: false }),
  loginWithPassword: async () => ({ email: "", is_admin: false }),
  changePassword: async () => ({ email: "", is_admin: false }),
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmailState] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  // Começa em true: bloqueia a renderização da SPA até /api/auth/me responder.
  // Sem isso há um flash de Dashboard antes do redirect para Login.
  const [loading, setLoading] = useState(true);
  // Email cuja senha é temporária e precisa ser trocada antes de entrar.
  const [mustChangePassword, setMustChangePassword] = useState<string | null>(null);

  // Hidrata via backend ao montar. Cookie httpOnly + credentials:"include"
  // garantem que o navegador envia a sessão automaticamente.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/auth/me", {
          method: "GET",
          credentials: "include",
          headers: { "Cache-Control": "no-store" },
        });
        if (cancelled) return;
        if (!r.ok) {
          // Sem sessão válida — força tela de login.
          localStorage.removeItem("valbot_email");
          localStorage.removeItem("valbot_role");
          setEmailState(null);
          setIsAdmin(false);
          return;
        }
        const d = await r.json();
        if (!d || !d.email) {
          setEmailState(null);
          setIsAdmin(false);
          return;
        }
        setEmailState(d.email);
        setIsAdmin(d.role !== "revisor" && d.is_admin !== false);
        // Atualiza hint local pro próximo login (pré-preencher o input).
        localStorage.setItem("valbot_email", d.email);
        if (d.role) localStorage.setItem("valbot_role", d.role);
      } catch {
        // Backend offline — ainda assim, sem confirmação não autorizamos.
        if (!cancelled) {
          setEmailState(null);
          setIsAdmin(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setEmail = async (raw: string) => {
    setLoading(true);
    try {
      const r = await fetch("/api/auth/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: raw }),
      });
      if (!r.ok) {
        const msg = await r.text().catch(() => `HTTP ${r.status}`);
        throw new Error(msg);
      }
      const d = await r.json();
      // Senha temporária (reset do admin): backend não emite cookie. Não
      // populamos a sessão — sinalizamos a troca obrigatória.
      if (d.must_change_password) {
        setMustChangePassword(d.email);
        return { email: d.email, is_admin: false, must_change_password: true };
      }
      setMustChangePassword(null);
      setEmailState(d.email);
      setIsAdmin(d.role !== "revisor" && d.is_admin !== false);
      localStorage.setItem("valbot_email", d.email);
      if (d.role) localStorage.setItem("valbot_role", d.role);
      return d;
    } finally {
      setLoading(false);
    }
  };

  // Login real com senha — porta de entrada do painel admin (/admin).
  // Valida credenciais contra admin_users no backend; em sucesso, o backend
  // emite o mesmo cookie de sessão httpOnly usado pelo resto do SPA.
  const loginWithPassword = async (raw: string, password: string) => {
    // NÃO usa o `loading` global: ele controla o splash do App, que desmontaria
    // o AdminLogin durante o login e perderia o passo de troca + a senha
    // temporária digitada. O spinner do botão é loading LOCAL do AdminLogin.
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email: raw, password }),
    });
    if (!r.ok) {
      let msg = "Credenciais inválidas";
      try {
        const j = await r.json();
        if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg;
      } catch {
        /* mantém mensagem genérica */
      }
      throw new Error(msg);
    }
    const d = await r.json();
    // Senha temporária (reset do admin): backend não emite cookie. Não
    // populamos a sessão — o front força a troca antes de entrar.
    if (d.must_change_password) {
      setMustChangePassword(d.email);
      return { email: d.email, is_admin: false, must_change_password: true };
    }
    setMustChangePassword(null);
    setEmailState(d.email);
    setIsAdmin(d.role !== "revisor" && d.is_admin !== false);
    localStorage.setItem("valbot_email", d.email);
    if (d.role) localStorage.setItem("valbot_role", d.role);
    return d;
  };

  // Troca de senha pós-reset: valida a senha atual (temporária) e grava a nova.
  // Em sucesso, o backend emite o cookie e populamos a sessão como no login.
  const changePassword = async (
    rawEmail: string,
    senhaAtual: string,
    novaSenha: string,
  ): Promise<LoginResult> => {
    // Sem `loading` global (mesmo motivo do loginWithPassword): evitar o splash
    // que desmonta o AdminLogin no meio da troca. Spinner é local do botão.
    const r = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        email: rawEmail,
        senha_atual: senhaAtual,
        password: novaSenha,
      }),
    });
    if (!r.ok) {
      let msg = "Não foi possível trocar a senha";
      try {
        const j = await r.json();
        if (j?.detail) msg = typeof j.detail === "string" ? j.detail : msg;
      } catch {
        /* mantém mensagem genérica */
      }
      throw new Error(msg);
    }
    const d = await r.json();
    setMustChangePassword(null);
    setEmailState(d.email);
    setIsAdmin(d.role !== "revisor" && d.is_admin !== false);
    localStorage.setItem("valbot_email", d.email);
    if (d.role) localStorage.setItem("valbot_role", d.role);
    return d;
  };

  const logout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      /* segue o fluxo: limpa estado local de qualquer jeito */
    }
    localStorage.removeItem("valbot_email");
    localStorage.removeItem("valbot_role");
    setEmailState(null);
    setIsAdmin(false);
    setMustChangePassword(null);
  };

  return (
    <AuthContext.Provider
      value={{
        email,
        isAdmin,
        loading,
        mustChangePassword,
        setEmail,
        loginWithPassword,
        changePassword,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
