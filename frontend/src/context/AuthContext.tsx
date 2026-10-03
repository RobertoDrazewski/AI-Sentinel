import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, clearToken, setToken } from "../api/client";

interface UserOut {
  id: number;
  email: string;
  business_name?: string;
  plan_status: string;
}

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, businessName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshMe() {
    try {
      const me = await api.get<UserOut>("/api/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshMe();
  }, []);

  async function login(email: string, password: string) {
    const data = await api.post<{ access_token: string }>("/api/auth/login", { email, password });
    setToken(data.access_token);
    await refreshMe();
  }

  async function register(email: string, password: string, businessName?: string) {
    const data = await api.post<{ access_token: string }>("/api/auth/register", {
      email,
      password,
      business_name: businessName
    });
    setToken(data.access_token);
    await refreshMe();
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
