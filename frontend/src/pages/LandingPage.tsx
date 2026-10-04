import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { BellRing, Car, Lock, MapPinned, ScanFace, ShieldAlert, type LucideIcon } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { AppleLogo, WindowsLogo } from "../components/OsLogos";
import logo from "../assets/logo-sentinel.png";

// Las 5 zonas de la imagen de fondo que sí representan algo real del
// producto (los recuadros chicos "OK" de relleno no tienen texto propio).
// hotspot x/y/w/h son % del ancho/alto DE LA IMAGEN COMPLETA (1584x672) --
// se usan en escritorio para alinear el brillo/tooltip sobre la foto. thumb
// es un recorte real de esa misma foto (sin el texto en inglés) para las
// tarjetas de mobile.
interface Feature {
  icon: LucideIcon;
  accent: string;
  title: string;
  text: string;
  thumb: string;
  hotspot: { x: number; y: number; w: number; h: number };
  tooltipSide: "left" | "right";
}

const FEATURES: Feature[] = [
  {
    icon: ScanFace,
    accent: "bg-sky-500/15 text-sky-400",
    title: "Reconocimiento facial",
    text: "Reconoce a tu familia automáticamente y te avisa apenas aparece una cara que no conoce.",
    thumb: "/thumb-face-recognition.jpg",
    hotspot: { x: 2, y: 3, w: 23, h: 41 },
    tooltipSide: "right"
  },
  {
    icon: Car,
    accent: "bg-amber-500/15 text-amber-400",
    title: "Vehículos detenidos",
    text: "Avisa si un auto o moto se queda parado en una zona que marcaste, como la salida de tu garage.",
    thumb: "/thumb-vehicles.jpg",
    hotspot: { x: 2, y: 52, w: 27, h: 46 },
    tooltipSide: "right"
  },
  {
    icon: MapPinned,
    accent: "bg-emerald-500/15 text-emerald-400",
    title: "Zonas personalizadas",
    text: "Marcás vos las zonas que te importan -- reja, timbre, calle, donde quieras -- cada una con su propia alarma.",
    thumb: "/thumb-zones.jpg",
    hotspot: { x: 75, y: 2, w: 24, h: 38 },
    tooltipSide: "left"
  },
  {
    icon: BellRing,
    accent: "bg-violet-500/15 text-violet-400",
    title: "Alertas al instante",
    text: "Te llega la foto y el aviso directo a Telegram apenas pasa algo, sin demoras.",
    thumb: "/thumb-alerts.jpg",
    hotspot: { x: 65, y: 34, w: 19, h: 36 },
    tooltipSide: "left"
  },
  {
    icon: ShieldAlert,
    accent: "bg-red-500/15 text-red-400",
    title: "Intrusos",
    text: "Marca en rojo cualquier rostro desconocido frente a tu cámara.",
    thumb: "/thumb-intruders.jpg",
    hotspot: { x: 83, y: 60, w: 17, h: 40 },
    tooltipSide: "left"
  }
];

const FILLER_HOTSPOTS = [
  { x: 28, y: 7, w: 10, h: 17 },
  { x: 62, y: 4, w: 11, h: 21 },
  { x: 33, y: 64, w: 10, h: 26 },
  { x: 57, y: 62, w: 11, h: 33 }
];

const tooltipPos: Record<"left" | "right", string> = {
  right: "left-full ml-3",
  left: "right-full mr-3"
};

// Tamaño real de landing-bg.jpg. Con esto emulamos a mano lo que haría
// "object-fit: cover" pero calculando nosotros el recorte, así sabemos
// exactamente qué % de la imagen quedó visible y podemos alinear ahí
// encima el logo y los hotspots sin que se desfasen.
const IMAGE_W = 1584;
const IMAGE_H = 672;
const IMAGE_ASPECT = IMAGE_W / IMAGE_H;

// Centro medido (análisis de brillo sobre la imagen real) del espacio
// circular luminoso del medio del fondo -- ahí es donde tiene que caer el
// logo siempre, sea cual sea el tamaño de la ventana.
const GLOW_CENTER = { x: 49, y: 44 }; // % de la imagen completa

function computeCoverBox() {
  if (typeof window === "undefined") return { left: 0, top: 0, width: 0, height: 0 };
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const viewportAspect = vw / vh;
  let width: number;
  let height: number;
  if (viewportAspect < IMAGE_ASPECT) {
    height = vh;
    width = vh * IMAGE_ASPECT;
  } else {
    width = vw;
    height = vw / IMAGE_ASPECT;
  }
  return { left: (vw - width) / 2, top: (vh - height) / 2, width, height };
}

/** Rectángulo (en px de pantalla) donde cae la imagen completa si la
 * hiciéramos cubrir toda la ventana -- se recalcula al resizear. Partes de
 * ese rectángulo caen fuera de la pantalla (se recortan con overflow
 * hidden), pero los hotspots y el logo se posicionan en % sobre ESTE
 * rectángulo, así siempre quedan en el lugar correcto de la foto. */
function useCoverBox() {
  const [box, setBox] = useState(computeCoverBox);
  useEffect(() => {
    function onResize() {
      setBox(computeCoverBox());
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return box;
}

/** Dispara "visible" la primera vez que el elemento entra en pantalla, para
 * animar las tarjetas de mobile a medida que aparecen al hacer scroll. */
function useRevealOnScroll<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.2, rootMargin: "0px 0px -40px 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, visible };
}

/** Chip chico con los dos logos reales, cerca de los botones de "Crear
 * cuenta" -- deja claro de entrada que el programa que se bajan corre en su
 * propia PC (Windows o Mac), no "en la nube". */
function OsAvailability() {
  return (
    <div className="flex items-center justify-center gap-2 text-[11px] text-slate-400">
      <span>Disponible para</span>
      <span className="inline-flex items-center gap-1">
        <WindowsLogo className="w-3.5 h-3.5" />
        Windows
      </span>
      <span className="text-slate-600">·</span>
      <span className="inline-flex items-center gap-1">
        <AppleLogo className="w-3.5 h-3.5" />
        Mac
      </span>
    </div>
  );
}

function PrivacyNote({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <p className="flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
        <Lock className="w-3.5 h-3.5 shrink-0" strokeWidth={2.2} />
        100% local -- tus fotos nunca se suben a ningún servidor
      </p>
    );
  }
  return (
    <div className="rounded-2xl border border-sky-900/60 bg-sky-500/5 p-4 flex gap-3 text-left">
      <div className="w-10 h-10 shrink-0 rounded-xl bg-sky-500/15 text-sky-400 flex items-center justify-center">
        <Lock className="w-5 h-5" strokeWidth={2.2} />
      </div>
      <div>
        <p className="text-sm font-semibold text-sky-300">Todo corre en tu propia computadora</p>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
          Ninguna foto ni video se sube a servidores de Puma Code ni de terceros: se guardan sólo en
          tu equipo. Las alertas con las fotos las ves únicamente vos, directo en tu Telegram
          privado.
        </p>
      </div>
    </div>
  );
}

function HeroText({ compact = false }: { compact?: boolean }) {
  return (
    <>
      <div className="relative flex items-center justify-center">
        <div
          aria-hidden
          className="sentinel-glow-backdrop absolute -inset-5 sm:-inset-8 rounded-full pointer-events-none"
        />
        <img
          src={logo}
          alt="AI Sentinel"
          className={`relative ${compact ? "w-28 h-28" : "w-40 h-40 sm:w-60 sm:h-60"} object-contain animate-sentinel-glow pointer-events-none`}
        />
      </div>
      <div>
        <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-amber-500 via-amber-300 to-sky-400 bg-clip-text text-transparent">
          AI Sentinel
        </h1>
        <p className="text-xs sm:text-sm tracking-[0.2em] text-slate-400 uppercase mt-1">by Puma Code</p>
      </div>
      <p className="text-sm sm:text-base text-slate-300">
        Convertí la cámara o el DVR que ya tenés en un sistema de seguridad inteligente que te avisa por
        Telegram al instante.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 w-full mt-2">
        <Link
          to="/register"
          className="flex-1 px-4 py-3 rounded-xl bg-accent text-slate-900 font-semibold text-center hover:brightness-95 transition"
        >
          Crear cuenta
        </Link>
        <Link
          to="/login"
          className="flex-1 px-4 py-3 rounded-xl bg-panel2/80 border border-slate-600 text-slate-100 font-semibold text-center hover:bg-panel2 transition"
        >
          Ingresar
        </Link>
      </div>
      <OsAvailability />
      <PrivacyNote compact />
    </>
  );
}

/** Tarjeta de función para mobile: foto real recortada del fondo + ícono
 * profesional (lucide, no emoji) superpuesto, con una pequeña animación 3D
 * (perspective + rotateX) que la "levanta" a medida que entra en pantalla al
 * scrollear, y feedback táctil al tocarla. */
function MobileFeatureCard({ feature, index }: { feature: Feature; index: number }) {
  const { ref, visible } = useRevealOnScroll<HTMLDivElement>();
  const Icon = feature.icon;
  return (
    <div
      ref={ref}
      style={{ transitionDelay: visible ? `${index * 70}ms` : "0ms" }}
      className={`relative bg-panel rounded-2xl overflow-hidden border border-slate-800 [transform-style:preserve-3d] transition-all duration-700 ease-out active:scale-[0.97] active:duration-100 ${
        visible
          ? "opacity-100 translate-y-0 [transform:perspective(900px)_rotateX(0deg)]"
          : "opacity-0 translate-y-8 [transform:perspective(900px)_rotateX(20deg)]"
      }`}
    >
      <div className="relative h-32">
        <img src={feature.thumb} alt="" className="w-full h-full object-cover" loading="lazy" />
        <div className="absolute inset-0 bg-gradient-to-t from-panel via-panel/15 to-transparent" />
        <div
          className={`absolute -bottom-4 left-4 w-11 h-11 rounded-xl flex items-center justify-center ring-4 ring-panel ${feature.accent}`}
        >
          <Icon className="w-5 h-5" strokeWidth={2.2} />
        </div>
      </div>
      <div className="pt-6 pb-4 px-4">
        <p className="text-sm font-semibold text-slate-100">{feature.title}</p>
        <p className="text-xs text-slate-400 mt-1 leading-relaxed">{feature.text}</p>
      </div>
    </div>
  );
}

/** Portada pública. En escritorio: el fondo cubre TODA la pantalla sin
 * márgenes (igual que "object-fit: cover", pero calculado a mano para poder
 * seguir alineando el logo y los hotspots sobre la foto); el logo queda
 * anclado exactamente en el centro del espacio circular luminoso de la
 * imagen, y cada recuadro real (reconocimiento facial, vehículos, etc.)
 * brilla y muestra una explicación al pasar el mouse. En mobile el hover no
 * existe, así que en vez de forzar esa misma interacción se reorganiza todo
 * en una columna que puede scrollear, con fotos reales recortadas del fondo,
 * íconos profesionales y una pequeña animación 3D al entrar en pantalla. Si
 * ya hay sesión, va directo al panel. */
export default function LandingPage() {
  const { user, loading } = useAuth();
  const box = useCoverBox();

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-dvh w-full bg-bg">
      {/* --- Escritorio (sm+): pantalla completa, sin scroll, imagen a pantalla completa --- */}
      <div className="hidden sm:block fixed inset-0 overflow-hidden bg-bg">
        <div className="absolute" style={{ left: box.left, top: box.top, width: box.width, height: box.height }}>
          <img
            src="/landing-bg.jpg"
            alt=""
            className="block w-full h-full select-none"
            draggable={false}
          />
          <div className="absolute inset-0 bg-bg/40" />

          {FILLER_HOTSPOTS.map((h, i) => (
            <div
              key={i}
              className="absolute rounded-lg hover:shadow-[0_0_30px_8px_rgba(56,191,248,0.3)] transition-shadow duration-300"
              style={{ left: `${h.x}%`, top: `${h.y}%`, width: `${h.w}%`, height: `${h.h}%` }}
            />
          ))}

          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="group absolute rounded-lg hover:shadow-[0_0_35px_10px_rgba(245,158,11,0.35)] transition-shadow duration-300"
                style={{
                  left: `${f.hotspot.x}%`,
                  top: `${f.hotspot.y}%`,
                  width: `${f.hotspot.w}%`,
                  height: `${f.hotspot.h}%`
                }}
              >
                <div
                  className={`pointer-events-none absolute top-1/2 -translate-y-1/2 ${tooltipPos[f.tooltipSide]} w-56 bg-panel/95 border border-slate-700 rounded-xl p-3 text-left opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 transition-all duration-200 shadow-xl z-20 flex gap-2.5`}
                >
                  <div className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center ${f.accent}`}>
                    <Icon className="w-4 h-4" strokeWidth={2.2} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-accent">{f.title}</p>
                    <p className="text-xs text-slate-300 mt-0.5">{f.text}</p>
                  </div>
                </div>
              </div>
            );
          })}

          {/* El logo se ancla al centro medido del círculo luminoso de la
              imagen (GLOW_CENTER); el texto y los botones fluyen debajo. */}
          <div
            className="absolute -translate-x-1/2 flex flex-col items-center text-center gap-3 sm:gap-4 w-72 sm:w-80 max-w-[90vw]"
            style={{ left: `${GLOW_CENTER.x}%`, top: `calc(${GLOW_CENTER.y}% - 7.5rem)` }}
          >
            <HeroText />
          </div>
        </div>
      </div>

      {/* --- Mobile: columna simple, scrollea si no entra todo --- */}
      <div className="flex sm:hidden flex-col min-h-dvh">
        <div className="flex flex-col items-center text-center gap-3 px-6 pt-10 pb-8">
          <HeroText compact />
        </div>
        <div className="px-4 pb-10 space-y-3">
          {FEATURES.map((f, i) => (
            <MobileFeatureCard key={f.title} feature={f} index={i} />
          ))}
          <PrivacyNote />
        </div>
      </div>
    </div>
  );
}
