import React, { useState } from "react";
import { Loader2, LogIn, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Tela de entrada. Pede email, valida formato, seta cookie via POST /api/auth/email.
 * Sem verificação por SMTP — atrito zero. Aviso claro de que o email fica
 * visível em cada comentário que o revisor criar.
 */
export function EmailGate() {
  const { setEmail } = useAuth();
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setErr(null);
    setLoading(true);
    try {
      await setEmail(value.trim());
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B1120] to-[#111827] p-4">
      <div className="w-full max-w-md bg-[#111827] border border-[#1F2937] rounded-xl p-8 shadow-2xl">
        <div className="flex flex-col items-center gap-3 mb-6">
          <div className="w-14 h-14 rounded-full bg-[#1D4ED8]/20 flex items-center justify-center">
            <ShieldAlert size={28} className="text-[#06B6D4]" />
          </div>
          <h1 className="text-2xl font-bold text-[#F9FAFB]">VALBOT — Revisão Colaborativa</h1>
          <p className="text-sm text-[#9CA3AF] text-center">
            Entre com seu email para revisar exames e deixar comentários.
            Seus apontamentos ficarão registrados com este email.
          </p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="text-xs font-medium text-[#9CA3AF]">Seu email</label>
          <Input
            type="email"
            autoFocus
            autoComplete="email"
            placeholder="nome@dominio.com"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="bg-[#0B1120] border-[#1F2937] text-sm text-[#F9FAFB] placeholder:text-[#6B7280]"
            disabled={loading}
          />
          {err && <div className="text-xs text-[#EF4444]">{err}</div>}
          <Button
            type="submit"
            className="w-full bg-[#1D4ED8] hover:bg-[#1E40AF] text-white mt-2"
            disabled={loading || !value.trim()}
          >
            {loading ? <Loader2 size={16} className="mr-2 animate-spin" /> : <LogIn size={16} className="mr-2" />}
            Entrar
          </Button>
        </form>

        <div className="mt-6 pt-4 border-t border-[#1F2937] text-[11px] text-[#6B7280]">
          Sem senha, sem cadastro — apenas o email como identificador. Você pode trocar de email a qualquer momento no menu superior.
        </div>
      </div>
    </div>
  );
}
