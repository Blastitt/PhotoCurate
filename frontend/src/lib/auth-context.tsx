"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { auth, type UserResponse } from "@/lib/api";

interface AuthState {
  user: UserResponse | null;
  token: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    name: string;
    password: string;
    tenant_name: string;
    tenant_slug: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    loading: true,
  });

  const setToken = useCallback((token: string | null) => {
    if (token) {
      localStorage.setItem("token", token);
    } else {
      localStorage.removeItem("token");
    }
    setState((s) => ({ ...s, token }));
  }, []);

  // Load user on mount / token change
  useEffect(() => {
    const stored = localStorage.getItem("token");
    if (!stored) {
      setState({ user: null, token: null, loading: false });
      return;
    }
    setState((s) => ({ ...s, token: stored, loading: true }));
    auth
      .me()
      .then((user) => setState({ user, token: stored, loading: false }))
      .catch(() => {
        localStorage.removeItem("token");
        setState({ user: null, token: null, loading: false });
      });
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await auth.login(email, password);
      setToken(res.access_token);
      const user = await auth.me();
      setState({ user, token: res.access_token, loading: false });
    },
    [setToken],
  );

  const register = useCallback(
    async (data: {
      email: string;
      name: string;
      password: string;
      tenant_name: string;
      tenant_slug: string;
    }) => {
      const res = await auth.register(data);
      setToken(res.access_token);
      const user = await auth.me();
      setState({ user, token: res.access_token, loading: false });
    },
    [setToken],
  );

  const logout = useCallback(() => {
    setToken(null);
    setState({ user: null, token: null, loading: false });
  }, [setToken]);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
