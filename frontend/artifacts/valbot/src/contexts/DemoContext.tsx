import { createContext, useContext, useState, ReactNode } from "react";

type DemoCtx = { demoMode: boolean; setDemoMode: (b: boolean) => void };
// demoMode default = false: api_stub agora serve /api/analyses/hash/<h>/result
// adaptando dados reais do bench em storage/analyses_demo/. Mock só fica
// disponível via toggle ou hash com prefixo "fake_demo_".
export const DemoContext = createContext<DemoCtx>({ demoMode: false, setDemoMode: () => {} });

export function DemoProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoMode] = useState(false);
  return <DemoContext.Provider value={{ demoMode, setDemoMode }}>{children}</DemoContext.Provider>;
}
export const useDemoMode = () => useContext(DemoContext);
