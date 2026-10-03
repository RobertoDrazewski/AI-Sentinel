import { useRef, useState, MouseEvent } from "react";

export interface Point {
  x: number;
  y: number;
}

interface Props {
  imageSrc: string; // data:image/jpeg;base64,... o URL
  onFinish: (polygon: Point[]) => void;
}

export default function ZoneCanvasEditor({ imageSrc, onFinish }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<Point[]>([]);

  function handleClick(e: MouseEvent<HTMLDivElement>) {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setPoints((prev) => [...prev, { x, y }]);
  }

  function undo() {
    setPoints((prev) => prev.slice(0, -1));
  }

  function reset() {
    setPoints([]);
  }

  function finish() {
    if (points.length >= 3) {
      onFinish(points);
      setPoints([]);
    }
  }

  const pointsPx = (rect: DOMRect | undefined) =>
    points.map((p) => `${p.x * (rect?.width || 0)},${p.y * (rect?.height || 0)}`).join(" ");

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={containerRef}
        onClick={handleClick}
        className="relative w-full aspect-video bg-black rounded-xl overflow-hidden cursor-crosshair select-none"
      >
        <img src={imageSrc} alt="Zona" className="w-full h-full object-contain pointer-events-none" />
        <svg className="absolute inset-0 w-full h-full">
          <polygon
            points={pointsPx(containerRef.current?.getBoundingClientRect())}
            fill="rgba(245, 158, 11, 0.25)"
            stroke="#f59e0b"
            strokeWidth={2}
          />
          {points.map((p, i) => (
            <circle
              key={i}
              cx={`${p.x * 100}%`}
              cy={`${p.y * 100}%`}
              r={5}
              fill="#f59e0b"
              stroke="#0f172a"
              strokeWidth={1}
            />
          ))}
        </svg>
      </div>
      <div className="flex gap-2 text-sm">
        <button onClick={undo} className="px-3 py-1.5 rounded-lg bg-panel2 hover:bg-slate-700">
          Deshacer punto
        </button>
        <button onClick={reset} className="px-3 py-1.5 rounded-lg bg-panel2 hover:bg-slate-700">
          Reiniciar
        </button>
        <button
          onClick={finish}
          disabled={points.length < 3}
          className="px-3 py-1.5 rounded-lg bg-accent text-slate-900 font-semibold disabled:opacity-40"
        >
          Cerrar zona ({points.length} puntos)
        </button>
      </div>
      <p className="text-xs text-slate-400">
        Hacé click sobre la imagen para marcar cada vértice de la zona (mínimo 3 puntos).
      </p>
    </div>
  );
}
