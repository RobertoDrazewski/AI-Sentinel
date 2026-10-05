"""Detecta un objeto real (mano, brazo, portón moviéndose) dentro de una zona chica:
reja (manipulación sostenida) o timbre (una mano cruzando un instante) (v6).

Historial resumido (ver versiones anteriores para el detalle completo de cada
intento fallido):
  v1/v2/v3: flujo óptico frame a frame. La reja de Roberto son barrotes verticales
  de altísimo contraste; un viento que hace vibrar apenas la cámara unos pocos
  píxeles generaba "movimiento aparente" fuerte justo sobre esos bordes sin que
  nada real se hubiera movido -- eso entraba como "manipulación" en pleno día, con
  la imagen prácticamente estática a simple vista.

  v4: se cambió a un modelo de fondo adaptativo (BackgroundSubtractorMOG2), más
  robusto contra ese temblor. Pero un modelo que se adapta solo tiene el problema
  inverso: si algo nuevo se queda quieto en la zona (una mano sostenida, alguien
  forcejeando sin moverse mucho), el propio modelo lo termina "aprendiendo" como
  fondo nuevo en bien menos de un segundo -- justo lo opuesto a lo que necesitamos
  para pedir "sostenido 1.5s".

v5 resuelve la tensión entre ambos problemas separando las dos cosas: en vez de un
modelo que se adapta todo el tiempo, se guarda una foto de referencia que SÓLO se
actualiza de a poco cuando la zona está en calma (sin nada raro encima), y nunca
mientras hay algo marcado como posible disturbio. Así:
  - Mientras algo esté ahí (una mano forzando la reja), la referencia se queda
    congelada de ANTES de que apareciera, así que la diferencia no se "diluye" con
    el correr de los segundos -- se puede sostener la detección por todo el tiempo
    que haga falta.
  - El temblor de cámara por viento se sigue filtrando igual que en v4: exigimos
    que la diferencia forme una MANCHA compacta de tamaño mínimo (no píxeles
    sueltos). Un temblor de unos pocos píxeles sobre barrotes separados entre sí
    genera varias manchitas finas y separadas (una por barrote), cada una muy por
    debajo del tamaño mínimo -- nunca una sola mancha grande y sólida como la de
    una mano o un cuerpo.
  - La referencia sí se va actualizando despacio cuando no hay nada raro (así
    sigue la luz del día cambiando a lo largo del día sin volverse cada vez más
    sensible).

v6 (fix de los ~200 falsos positivos de "manipulación" en una sola noche en "Reja
/ entrada"): v5 tenía dos problemas que juntos convertían UN solo evento (real o
ni siquiera real -- de noche, con cámara IR, alcanza con un insecto pasando cerca
del iluminador, o la autoexposición de la cámara "cazando" el nivel de luz de a
poco) en una tormenta de decenas de alertas:

  1. update() devolvía True en CADA frame mientras la mancha siguiera por encima
     del umbral, no sólo una vez al cruzar el segundo 1.5 -- así que mientras algo
     distinto de la referencia siguiera ahí (aunque sea un insecto quieto un rato,
     o un reflejo IR nuevo), cada frame volvía a "pedir" una alerta, y el cooldown
     de 30s de alert_manager dejaba pasar una cada 30 segundos exactos mientras
     durara: 10 minutos de disturbio = 20 alertas por un solo evento.
  2. La referencia se queda congelada mientras hay disturbio (a propósito, ver
     v5) -- pero si lo que lo disparó no era una mano forzando la reja sino un
     corrimiento lento de brillo (autoexposición de noche), la referencia nunca
     se "pone al día" con la luz real, así que la diferencia contra ella no hace
     más que crecer con el tiempo: queda trabada en "disturbado" indefinidamente,
     sin volver nunca sola a la calma.

v6 corrige los dos: ahora update() es "de flanco" -- avisa una sola vez al cruzar
el umbral sostenido, y no vuelve a avisar hasta que la zona pasa por calma de
nuevo (así una manipulación real de varios minutos avisa una sola vez, no decenas
de veces). Y si el disturbio sigue sin cortar por demasiado tiempo seguido (más de
max_disturbed_seconds), asumimos que no es alguien forzando la reja ahora mismo
sino el sensor/luz desajustados, y recongelamos la referencia contra el frame
actual en vez de quedar trabados para siempre.
"""
from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np


class GateTamperDetector:
    def __init__(
        self,
        min_sustained_seconds: float = 1.5,
        min_blob_area_ratio: float = 0.05,
        diff_threshold: int = 28,
        refresh_interval_seconds: float = 8.0,
        max_disturbed_seconds: float = 45.0,
    ):
        self._reference: Optional[np.ndarray] = None
        self._motion_start: Optional[float] = None
        self._last_refresh: float = 0.0
        # Ya avisamos por este episodio de disturbio en curso -- se resetea a
        # False recién cuando la zona vuelve a estar en calma (ver update()), así
        # un disturbio sostenido de varios minutos avisa UNA sola vez, no una vez
        # por cada 30s de cooldown que dure.
        self._alerted: bool = False
        self.min_sustained_seconds = min_sustained_seconds
        # Qué fracción del área de la zona tiene que cubrir la mancha de diferencia
        # MÁS GRANDE para contar como "algo real ahí", no ruido/temblor disperso.
        self.min_blob_area_ratio = min_blob_area_ratio
        # Diferencia de intensidad (0-255, en escala de grises) para que un píxel
        # cuente como "distinto" de la referencia.
        self.diff_threshold = diff_threshold
        # Cada cuánto se deja "mezclar" la referencia hacia lo que ve la cámara,
        # pero SÓLO cuando la zona está en calma (ver update()).
        self.refresh_interval_seconds = refresh_interval_seconds
        # Si la zona queda "disturbada" sin cortar por más que esto, ya no lo
        # tratamos como alguien forzando la reja en este momento -- es mucho más
        # probable que sea autoexposición/luz cambiando de a poco de noche, o algo
        # que se quedó quieto ahí (rama, bolsa, insecto). Recongelamos la
        # referencia contra el frame actual para no quedar trabados avisando cada
        # 30 segundos para siempre.
        self.max_disturbed_seconds = max_disturbed_seconds

    def update(self, frame: np.ndarray, zone_mask: np.ndarray) -> bool:
        """zone_mask: máscara binaria (mismo tamaño que frame) con 255 en la zona.
        Devuelve True UNA SOLA VEZ por episodio de disturbio sostenido (al cruzar
        min_sustained_seconds), no en cada frame mientras siga disturbada -- ver
        el comentario de v6 arriba del todo del archivo."""
        now = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)
        small = cv2.resize(gray, (frame.shape[1] // 2, frame.shape[0] // 2))
        mask_small = cv2.resize(zone_mask, (small.shape[1], small.shape[0]))

        zone_area = int(np.count_nonzero(mask_small))
        if zone_area == 0:
            self._motion_start = None
            self._alerted = False
            return False

        if self._reference is None or self._reference.shape != small.shape:
            self._reference = small.copy()
            self._last_refresh = now
            self._motion_start = None
            self._alerted = False
            return False

        diff = cv2.absdiff(small, self._reference)
        _, diff_mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        # Limpieza morfológica: saca píxeles sueltos de 1-2px (temblor fino sobre
        # un borde, grano de sensor), sin afectar una mancha realmente sólida.
        diff_mask = cv2.morphologyEx(diff_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        diff_in_zone = cv2.bitwise_and(diff_mask, diff_mask, mask=mask_small)

        contours, _ = cv2.findContours(diff_in_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_blob = max((cv2.contourArea(c) for c in contours), default=0.0)
        blob_ratio = largest_blob / zone_area
        disturbed = blob_ratio >= self.min_blob_area_ratio

        if disturbed:
            if self._motion_start is None:
                self._motion_start = now
            disturbed_for = now - self._motion_start

            if disturbed_for >= self.max_disturbed_seconds:
                # Lleva demasiado tiempo disturbada seguida -- recalibramos contra
                # el frame actual y arrancamos de cero, en vez de seguir avisando.
                self._reference = small.copy()
                self._last_refresh = now
                self._motion_start = None
                self._alerted = False
                return False

            if disturbed_for >= self.min_sustained_seconds and not self._alerted:
                self._alerted = True
                return True
            return False

        # Zona en calma este frame: cierra el episodio (si había uno) y re-arma
        # para que el PRÓXIMO disturbio sostenido pueda volver a avisar.
        self._motion_start = None
        self._alerted = False
        # Sólo actualizamos la referencia (para seguir la luz del día, sombras
        # lentas, etc.) cuando la zona está en calma y ya pasó un rato desde el
        # último refresco -- nunca mientras hay algo marcado como disturbio.
        if now - self._last_refresh >= self.refresh_interval_seconds:
            self._reference = cv2.addWeighted(self._reference, 0.8, small, 0.2, 0)
            self._last_refresh = now
        return False
