from dataclasses import dataclass

@dataclass
class Vehicle:
    vid: int
    x: float          # posición (m): 0 en línea de alto; negativa aguas arriba; positiva aguas abajo
    v: float          # velocidad (m/s)
    entered_at: float
    stopped_for: float = 0.0  # >=0 acumula tiempo detenido; <0 tiempo restante de bloqueo intencional
    length: float = 4.5

    def is_stopped(self, v_thresh: float = 0.1) -> bool:
        return abs(self.v) < v_thresh