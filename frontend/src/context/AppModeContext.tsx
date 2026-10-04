import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "../api/client";

// Distingue si este frontend está hablando con el AGENTE LOCAL (instalado en
// la PC del cliente, con acceso directo por red local a su cámara/DVR) o con
// el PORTAL CENTRAL (desplegado en Railway, para registro/pago/descarga). Un
// backend en la nube no puede ver una IP 192.168.x.x de la casa de nadie, así
// que la configuración de cámaras/zonas sólo tiene sentido en el primer caso.
// Ver Nav.tsx, Dashboard.tsx, Onboarding.tsx y Register.tsx.
interface AppModeState {
  // null mientras todavía no se sabe (primer render, antes de que responda
  // /api/health) -- tratar como "no mostrar ni ocultar nada todavía".
  isLocalAgent: boolean | null;
}

const AppModeContext = createContext<AppModeState>({ isLocalAgent: null });

export function AppModeProvider({ children }: { children: ReactNode }) {
  const [isLocalAgent, setIsLocalAgent] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .get<{ is_local_agent?: boolean }>("/api/health")
      .then((data) => setIsLocalAgent(Boolean(data.is_local_agent)))
      .catch(() => setIsLocalAgent(false));
  }, []);

  return <AppModeContext.Provider value={{ isLocalAgent }}>{children}</AppModeContext.Provider>;
}

export function useAppMode() {
  return useContext(AppModeContext);
}
