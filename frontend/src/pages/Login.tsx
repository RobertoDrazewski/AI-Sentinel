import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import logo from "../assets/logo-sentinel.png";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.message || "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-panel p-6 rounded-xl space-y-4">
        <img src={logo} alt="AI Sentinel" className="h-16 w-16 object-contain mx-auto" />
        <h1 className="text-xl font-bold text-accent text-center">AI Sentinel</h1>
        <p className="text-sm text-slate-400 text-center">Ingresá a tu cuenta</p>
        {error && <p className="text-sm text-danger">{error}</p>}
        <input
          type="email"
          placeholder="Email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700 outline-none focus:border-accent"
        />
        <input
          type="password"
          placeholder="Contraseña"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3 py-2 rounded-lg bg-panel2 border border-slate-700 outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold disabled:opacity-50"
        >
          {loading ? "Ingresando..." : "Ingresar"}
        </button>
        <p className="text-sm text-center text-slate-400">
          ¿No tenés cuenta?{" "}
          <Link to="/register" className="text-accent">
            Registrate
          </Link>
        </p>
      </form>
    </div>
  );
}
