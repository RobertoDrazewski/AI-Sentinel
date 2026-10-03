import { mediaUrl } from "../api/client";

export interface AlertItem {
  id: number;
  camera_id: number;
  type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  image_path?: string | null;
  created_at: string;
  telegram_sent: boolean;
}

const SEVERITY_STYLES: Record<string, string> = {
  info: "border-l-4 border-ok",
  warning: "border-l-4 border-warn",
  critical: "border-l-4 border-danger animate-pulse"
};

export default function AlertCard({ alert }: { alert: AlertItem }) {
  return (
    <div className={`flex gap-3 bg-panel rounded-lg p-3 ${SEVERITY_STYLES[alert.severity]}`}>
      {alert.image_path && (
        <img
          src={mediaUrl(alert.image_path)}
          alt={alert.type}
          className="w-20 h-20 object-cover rounded-md flex-shrink-0"
        />
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm">{alert.message}</p>
        <p className="text-xs text-slate-400 mt-1">
          {new Date(alert.created_at).toLocaleString("es-AR")} · cámara #{alert.camera_id}
          {alert.telegram_sent ? " · ✅ enviado a Telegram" : ""}
        </p>
      </div>
    </div>
  );
}
