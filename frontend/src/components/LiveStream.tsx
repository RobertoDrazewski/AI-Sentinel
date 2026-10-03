import { useEffect, useState } from "react";
import { streamUrl } from "../api/client";

export default function LiveStream({ cameraId }: { cameraId: number }) {
  const [src, setSrc] = useState(() => streamUrl(cameraId));

  // Si el token cambia o hay que forzar reconexión del <img> MJPEG, regeneramos la URL.
  useEffect(() => {
    setSrc(streamUrl(cameraId) + `&t=${Date.now()}`);
  }, [cameraId]);

  return (
    <div className="relative bg-black rounded-xl overflow-hidden aspect-video w-full">
      <img src={src} alt={`Cámara ${cameraId}`} className="w-full h-full object-contain" />
    </div>
  );
}
