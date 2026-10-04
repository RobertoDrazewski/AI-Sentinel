import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import logo from "../assets/logo-sentinel.png";

interface ActivationStatus {
  activated: boolean;
  central_server_configured: boolean;
}

// Pantalla de primera vez del AGENTE EMPAQUETADO (el programa instalado en la PC
// del cliente) -- activa esta instalación contra la cuenta real del portal
// público, usando el mismo mail/contraseña con el que el cliente se registró y
// pagó ahí. De ahí en más esta PC queda emparejada (ver AgentToken en el
// backend) y el agente consulta periódicamente la licencia/túnel real contra
// ese servidor en vez de calcular todo con esta base local -- ver
// backend/app/phone_home.py.
//
// Si esta build no tiene configurado un servidor central (CENTRAL_SERVER_URL
// vacío -- hoy es el caso en desarrollo), esta pantalla avisa que todavía no
// hace falta activar nada y deja pasar directo al login/registro local de
// siempre, sin bloquear nada.
export default function Activation() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ActivationStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get<ActivationStatus>("/api/local/activation-status")
      .then(setStatus)
      .catch(() => setStatus({ activated: true, central_server_configured: false }));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/api/local/activate", { email, password });
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "No se pudo activar. Revisá el mail y la contraseña.");
    } finally {
      setLoading(false);
    }
  }

  if (status === null) {
    return <div className="min-h-screen flex items-center justify-center text-slate-400">Cargando...</div>;
  }

  // Nada que activar en esta build (o ya está activada) -- seguir de largo.
  if (!status.central_server_configured || status.activated) {
    navigate("/login", { replace: true });
    return null;
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm bg-panel p-6 rounded-xl space-y-4 text-center">
          <p className="text-2xl">✅</p>
          <h1 className="text-xl font-bold text-accent">Listo, activado</h1>
          <p className="text-sm text-slate-400">
            Esta computadora ya quedó asociada a tu cuenta. Ahora ingresá con el mismo mail y
            contraseña para entrar al panel.
          </p>
          <button
            onClick={() => navigate("/login")}
            className="w-full py-2 rounded-lg bg-accent text-slate-900 font-semibold"
          >
            Ir a iniciar sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-panel p-6 rounded-xl space-y-4">
        <img src={logo} alt="AI Sentinel" className="h-16 w-16 object-contain mx-auto" />
        <h1 className="text-xl font-bold text-accent text-center">Activar este agente</h1>
        <p className="text-sm text-slate-400 text-center">
          Ingresá el mail y la contraseña de tu cuenta de AI Sentinel para activar esta computadora.
        </p>
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
          {loading ? "Activando..." : "Activar"}
        </button>
        <p className="text-xs text-center text-slate-500">
          Tiene que ser la misma cuenta con la que te registraste y pagaste en el portal -- no se crea
          una cuenta nueva acá.
        </p>
      </form>
    </div>
  );
}
