import { useRef, useState } from "react";
import { api } from "../api/client";

const HOLD_MS = 1200;

export default function PanicButton({ cameraId }: { cameraId: number }) {
  const [holding, setHolding] = useState(false);
  const [progress, setProgress] = useState(0);
  const [sent, setSent] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const startRef = useRef<number>(0);

  function clearTimer() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setHolding(false);
    setProgress(0);
  }

  function startHold() {
    setHolding(true);
    startRef.current = Date.now();
    timerRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startRef.current;
      setProgress(Math.min(100, (elapsed / HOLD_MS) * 100));
      if (elapsed >= HOLD_MS) {
        clearTimer();
        triggerPanic();
      }
    }, 30);
  }

  async function triggerPanic() {
    setSent("Enviando alerta...");
    try {
      await api.post(`/api/panic/${cameraId}`);
      setSent("Alerta enviada. Abriendo llamada al 911...");
    } catch (e) {
      setSent("No se pudo registrar la alerta, pero igual abrimos la llamada.");
    } finally {
      // Igual que en el feature de sismos: abrimos el marcador del teléfono.
      // Por restricciones del navegador/SO, en la mayoría de los casos el usuario
      // todavía tiene que tocar "Llamar" una vez para confirmar - no existe forma
      // de marcar 100% sin intervención humana desde la web.
      window.location.href = "tel:911";
      setTimeout(() => setSent(null), 6000);
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onPointerDown={startHold}
        onPointerUp={clearTimer}
        onPointerLeave={clearTimer}
        className="relative w-24 h-24 rounded-full bg-danger text-white font-bold text-sm shadow-lg shadow-red-900/50 select-none overflow-hidden active:scale-95 transition-transform"
      >
        <div
          className="absolute inset-0 bg-red-900/60"
          style={{ clipPath: `inset(${100 - progress}% 0 0 0)` }}
        />
        <span className="relative z-10">
          {holding ? "Mantené..." : "PÁNICO"}
        </span>
      </button>
      <p className="text-xs text-slate-400 text-center max-w-[180px]">
        Mantené presionado 1.2s para confirmar. Envía alerta crítica y abre la llamada al 911.
      </p>
      {sent && <p className="text-xs text-accent text-center">{sent}</p>}
    </div>
  );
}
