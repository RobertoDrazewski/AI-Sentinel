import { useEffect, useState } from "react";
import { Download as DownloadIcon } from "lucide-react";
import { AppleLogo, WindowsLogo } from "../components/OsLogos";

// Repo PÚBLICO (separado del código fuente, que sigue privado) donde el
// workflow de GitHub Actions publica los ejecutables ya compilados como
// Release -- ver .github/workflows/build-agent.yml en el repo principal.
// "releases/latest/download/<archivo>" es un link estable de GitHub: siempre
// apunta a los archivos de la última Release, sin necesidad de tocar nada acá
// cuando se publica una compilación nueva.
const RELEASES_BASE = "https://github.com/RobertoDrazewski/AI-Sentinel-Releases/releases/latest/download";

const DOWNLOADS = {
  windows: {
    label: "Windows",
    file: "ai-sentinel-agent-windows.exe",
    note: "Windows 10 o 11 (64 bits)"
  },
  mac: {
    label: "Mac",
    file: "ai-sentinel-agent-mac-applesilicon",
    note: "Mac con chip Apple (M1, M2, M3 o M4 -- 2020 en adelante)"
  }
} as const;

type OS = "windows" | "mac" | "otro";

// Detecta el sistema operativo desde el navegador para sugerir el botón
// correcto primero -- los dos botones quedan siempre visibles igual, esto
// sólo decide cuál se destaca arriba.
function detectOS(): OS {
  if (typeof navigator === "undefined") return "otro";
  const ua = `${navigator.userAgent} ${navigator.platform || ""}`.toLowerCase();
  if (ua.includes("win")) return "windows";
  if (ua.includes("mac")) return "mac";
  return "otro";
}

function DownloadButton({ os, highlighted }: { os: "windows" | "mac"; highlighted: boolean }) {
  const info = DOWNLOADS[os];
  const Logo = os === "windows" ? WindowsLogo : AppleLogo;
  return (
    <a
      href={`${RELEASES_BASE}/${info.file}`}
      className={`flex items-center gap-3 rounded-xl p-4 transition ${
        highlighted
          ? "bg-accent text-slate-900 hover:brightness-95"
          : "bg-panel2 text-slate-100 hover:bg-slate-700"
      }`}
    >
      <Logo className="w-7 h-7 shrink-0" />
      <div className="flex-1 min-w-0 text-left">
        <p className="font-semibold">Descargar para {info.label}</p>
        <p className={`text-xs ${highlighted ? "text-slate-800" : "text-slate-400"}`}>{info.note}</p>
      </div>
      <DownloadIcon className="w-5 h-5 shrink-0" strokeWidth={2} />
    </a>
  );
}

export default function Download() {
  const [os, setOs] = useState<OS>("otro");

  useEffect(() => {
    setOs(detectOS());
  }, []);

  return (
    <div className="max-w-md mx-auto p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-accent">Descargar el agente</h1>
        <p className="text-sm text-slate-400 mt-1">
          Instalalo en la computadora de tu casa o local, donde tengas la cámara o el DVR conectado a
          la misma red. La configuración de la cámara, las zonas y el Telegram se hacen ahí, no acá.
        </p>
      </div>

      {os !== "otro" && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">
            Detectamos que estás en {DOWNLOADS[os].label} -- este es tu instalador:
          </p>
          <DownloadButton os={os} highlighted />
        </div>
      )}

      <div className="space-y-2">
        {os !== "otro" && (
          <p className="text-xs text-slate-500">¿Vas a instalarlo en otra computadora?</p>
        )}
        <div className="space-y-2">
          {(["windows", "mac"] as const)
            .filter((o) => o !== os)
            .map((o) => (
              <DownloadButton key={o} os={o} highlighted={false} />
            ))}
        </div>
      </div>

      <div className="bg-panel rounded-xl p-4 space-y-2 text-xs text-slate-400">
        <p className="text-slate-300 font-medium">Después de instalarlo</p>
        <p>
          Al abrirlo por primera vez te va a pedir iniciar sesión con el mismo mail y contraseña de
          esta cuenta, para activarlo. De ahí en más queda corriendo solo en esa computadora.
        </p>
        <p>
          Por cada suscripción se pueden tener hasta 2 computadoras activadas al mismo tiempo. Podés
          ver y quitar dispositivos desde "Mi cuenta".
        </p>
      </div>

      {os === "mac" || os === "otro" ? (
        <div className="bg-panel rounded-xl p-4 space-y-2 text-xs text-slate-400">
          <p className="text-slate-300 font-medium">En Mac, la primera vez</p>
          <p>
            macOS va a avisar que es de "un desarrollador no identificado" (todavía no tiene la firma
            paga de Apple). Abrí la Terminal, andá a la carpeta donde se descargó y corré:
          </p>
          <code className="block bg-panel2 px-2 py-1.5 rounded text-accent break-all">
            chmod +x ai-sentinel-agent-mac-applesilicon && ./ai-sentinel-agent-mac-applesilicon
          </code>
          <p>
            Más adelante vamos a tener un instalador con doble clic, sin pasar por la Terminal.
          </p>
        </div>
      ) : null}
    </div>
  );
}
