(window as unknown as { __VALBOT_BUILD__?: string }).__VALBOT_BUILD__ = "2026-06-15-r2-cachebust";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { DemoProvider } from "@/contexts/DemoContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <AuthProvider>
        <DemoProvider>
          <App />
        </DemoProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>,
);
