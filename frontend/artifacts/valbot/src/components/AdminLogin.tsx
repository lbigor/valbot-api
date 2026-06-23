import { useState } from "react";
import {
  Mail,
  Lock,
  ShieldCheck,
  Cpu,
  ArrowRight,
  Loader2,
  Eye,
  EyeOff,
  AlertCircle,
  KeyRound,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GlassCard } from "@/components/ui/glass-card";
import { CardContent } from "@/components/ui/card";

/** Resultado mínimo que o login pode devolver. `must_change_password` indica
 *  senha temporária (reset do admin) — força o passo de troca obrigatória. */
type LoginResult = { must_change_password?: boolean } | unknown;

interface AdminLoginProps {
  /**
   * Quando preenchido (email com senha temporária pós-reset), a tela já abre no
   * passo de troca obrigatória. Vem do `mustChangePassword` do AuthContext, que
   * persiste mesmo se o componente remontar (ex.: splash de loading durante o
   * login) — sem isso o passo de troca se perde e a tela volta pro login.
   */
  forceChangeEmail?: string | null;
  /** Recebe credenciais e resolve a sessão; rejeita com Error.message exibível. */
  onSubmit: (email: string, password: string) => Promise<LoginResult>;
  /**
   * Troca a senha temporária pela nova (pós-reset do admin). Recebe o email, a
   * senha atual (a temporária recém-digitada) e a nova. Resolve a sessão em
   * sucesso; rejeita com Error.message exibível.
   */
  onChangePassword: (
    email: string,
    senhaAtual: string,
    novaSenha: string,
  ) => Promise<unknown>;
}

/**
 * Tela de login do painel administrativo (rota /admin).
 *
 * Diferente do <Login> piloto (email sem senha, papel por heurística), aqui o
 * acesso exige credenciais reais validadas contra admin_users no backend
 * (POST /api/auth/login). Mantém o visual cyber/glass do Valbot para coerência.
 */
export function AdminLogin({ forceChangeEmail, onSubmit, onChangePassword }: AdminLoginProps) {
  // Inicializa já no email da senha temporária quando o App força a troca
  // (mustChangePassword). Como o componente pode remontar durante o login, o
  // estado inicial é derivado da prop para o passo de troca não se perder.
  const [email, setEmail] = useState(forceChangeEmail ?? "");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Passo de troca obrigatória (senha temporária pós-reset do admin).
  // Abre direto neste passo quando `forceChangeEmail` veio preenchido.
  const [mustChange, setMustChange] = useState(!!forceChangeEmail);
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmaSenha, setConfirmaSenha] = useState("");
  const [showNova, setShowNova] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) return;
    setError(null);
    setLoading(true);
    try {
      const res = await onSubmit(email.trim(), password);
      // Senha temporária: o backend não autenticou — exige troca antes de entrar.
      if (res && (res as { must_change_password?: boolean }).must_change_password) {
        setMustChange(true);
        setLoading(false);
        return;
      }
      // Em sucesso, o AuthContext seta a sessão e o App redireciona para /dashboard.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Credenciais inválidas");
      setLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (novaSenha.length < 8) {
      setError("A nova senha deve ter pelo menos 8 caracteres");
      return;
    }
    if (novaSenha !== confirmaSenha) {
      setError("A confirmação não confere com a nova senha");
      return;
    }
    if (novaSenha === password) {
      setError("A nova senha deve ser diferente da temporária");
      return;
    }
    setLoading(true);
    try {
      // `password` ainda guarda a senha temporária que o usuário acabou de digitar.
      await onChangePassword(email.trim(), password, novaSenha);
      // Em sucesso, o AuthContext seta a sessão e o App redireciona.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível trocar a senha");
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-screen bg-[#040814] text-slate-100 flex items-center justify-center overflow-hidden font-sans">
      {/* Background neon glows */}
      <div className="pointer-events-none absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-900/10 rounded-full blur-[150px]" />
      <div className="pointer-events-none absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] bg-cyan-900/15 rounded-full blur-[180px]" />

      {/* Cyber grid */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(#06B6D4 1px, transparent 1px), linear-gradient(90deg, #06B6D4 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative z-10 w-full max-w-md mx-auto p-4">
        <GlassCard className="relative overflow-hidden bg-slate-900/40 backdrop-blur-2xl border-slate-800/80 shadow-2xl">
          {/* Glowing top line */}
          <div className="absolute top-0 inset-x-0 h-[1.5px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-75" />

          <CardContent className="p-6 md:p-8">
            <div className="flex flex-col space-y-5">
              {/* Brand */}
              <div className="text-center space-y-1.5">
                <div className="inline-flex items-center justify-center p-2.5 rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-lg shadow-cyan-500/20 mb-2">
                  {mustChange ? <KeyRound size={24} /> : <ShieldCheck size={24} />}
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-white">
                  {mustChange ? "Defina uma nova senha" : "Acesse o VALBOT"}
                </h2>
                <p className="text-slate-400 text-xs flex items-center justify-center gap-1.5">
                  <Cpu size={12} className="text-cyan-400" />
                  {mustChange
                    ? "Sua senha é temporária — escolha uma nova"
                    : "Acesso seguro — VALBOT"}
                </p>
              </div>

              {/* Error banner */}
              {error && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2.5 text-xs text-red-300"
                >
                  <AlertCircle size={15} className="shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Form de login (oculto durante a troca obrigatória) */}
              {!mustChange && (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email */}
                <div className="space-y-1.5 text-left">
                  <Label
                    htmlFor="admin-email"
                    className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
                  >
                    Email
                  </Label>
                  <div className="relative group">
                    <Mail
                      size={16}
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-cyan-400 transition-colors z-10"
                    />
                    <Input
                      id="admin-email"
                      type="email"
                      required
                      autoComplete="username"
                      placeholder="nome@valbot.ai"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="h-11 pl-10 bg-slate-950/65 border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus-visible:ring-1 focus-visible:ring-cyan-400 focus-visible:border-cyan-400"
                    />
                  </div>
                </div>

                {/* Senha */}
                <div className="space-y-1.5 text-left">
                  <Label
                    htmlFor="admin-password"
                    className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
                  >
                    Senha
                  </Label>
                  <div className="relative group">
                    <Lock
                      size={16}
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-cyan-400 transition-colors z-10"
                    />
                    <Input
                      id="admin-password"
                      type={showPwd ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      placeholder="••••••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="h-11 pl-10 pr-10 bg-slate-950/65 border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus-visible:ring-1 focus-visible:ring-cyan-400 focus-visible:border-cyan-400"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd((v) => !v)}
                      aria-label={showPwd ? "Ocultar senha" : "Mostrar senha"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-cyan-400 transition-colors z-10"
                    >
                      {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                {/* Submit */}
                <Button
                  type="submit"
                  disabled={loading || !email.trim() || !password}
                  className="w-full h-11 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-700 hover:to-cyan-600 active:scale-[0.98] text-white text-sm font-semibold rounded-xl border border-cyan-500/40 shadow-lg shadow-cyan-500/10 transition-all group"
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <>
                      Entrar
                      <ArrowRight
                        size={16}
                        className="group-hover:translate-x-1 transition-transform"
                      />
                    </>
                  )}
                </Button>
              </form>
              )}

              {/* Form de troca obrigatória (senha temporária pós-reset) */}
              {mustChange && (
              <form onSubmit={handleChangePassword} className="space-y-4">
                {/* Nova senha */}
                <div className="space-y-1.5 text-left">
                  <Label
                    htmlFor="admin-nova-senha"
                    className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
                  >
                    Nova senha
                  </Label>
                  <div className="relative group">
                    <Lock
                      size={16}
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-cyan-400 transition-colors z-10"
                    />
                    <Input
                      id="admin-nova-senha"
                      type={showNova ? "text" : "password"}
                      required
                      autoComplete="new-password"
                      placeholder="mínimo 8 caracteres"
                      value={novaSenha}
                      onChange={(e) => setNovaSenha(e.target.value)}
                      className="h-11 pl-10 pr-10 bg-slate-950/65 border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus-visible:ring-1 focus-visible:ring-cyan-400 focus-visible:border-cyan-400"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNova((v) => !v)}
                      aria-label={showNova ? "Ocultar senha" : "Mostrar senha"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-cyan-400 transition-colors z-10"
                    >
                      {showNova ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                {/* Confirmar nova senha */}
                <div className="space-y-1.5 text-left">
                  <Label
                    htmlFor="admin-confirma-senha"
                    className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
                  >
                    Confirmar nova senha
                  </Label>
                  <div className="relative group">
                    <Lock
                      size={16}
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-cyan-400 transition-colors z-10"
                    />
                    <Input
                      id="admin-confirma-senha"
                      type={showNova ? "text" : "password"}
                      required
                      autoComplete="new-password"
                      placeholder="repita a nova senha"
                      value={confirmaSenha}
                      onChange={(e) => setConfirmaSenha(e.target.value)}
                      className="h-11 pl-10 bg-slate-950/65 border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus-visible:ring-1 focus-visible:ring-cyan-400 focus-visible:border-cyan-400"
                    />
                  </div>
                </div>

                {/* Submit */}
                <Button
                  type="submit"
                  disabled={loading || !novaSenha || !confirmaSenha}
                  className="w-full h-11 bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-700 hover:to-cyan-600 active:scale-[0.98] text-white text-sm font-semibold rounded-xl border border-cyan-500/40 shadow-lg shadow-cyan-500/10 transition-all group"
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <>
                      Salvar e entrar
                      <ArrowRight
                        size={16}
                        className="group-hover:translate-x-1 transition-transform"
                      />
                    </>
                  )}
                </Button>
              </form>
              )}

              {/* Footer */}
              <div className="pt-1 flex justify-center gap-4 text-[10px] text-slate-500 font-medium">
                <span>Segurança GOV.BR</span>
                <span>•</span>
                <span>Termos de Uso</span>
              </div>
            </div>
          </CardContent>
        </GlassCard>
      </div>
    </div>
  );
}
