import math
import random
from typing import List
from .vehicle import Vehicle

class Lane:
    """
    Un carril unidimensional con x=0 en la línea de alto.
    name "A": horizontal (izq->der). name "B": vertical (arriba->abajo).
    """
    def __init__(self, name: str, road_length: float, v_max: float, safe_gap: float, p_block: float, t_block: float, seed: int):
        self.name = name
        self.road_length = road_length
        self.v_max = v_max
        self.safe_gap = safe_gap
        self.p_block = p_block
        self.t_block = t_block
        self.vehicles: List[Vehicle] = []
        self.next_vid = 1
        self.rng = random.Random(seed)

    def spawn_poisson(self, rate: float, dt: float, now: float):
        lam = rate * dt
        arrivals = self._poisson_knuth(lam)
        for _ in range(arrivals):
            x0 = -self.road_length
            if self.vehicles and (self.vehicles[0].x - x0) < self.safe_gap:
                continue
            v0 = self.v_max * 0.85
            self.vehicles.insert(0, Vehicle(self.next_vid, x0, v0, now))
            self.next_vid += 1

    def _poisson_knuth(self, lam: float) -> int:
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= self.rng.random()
        return max(0, k-1)

    # Sensores
    def count_in_range_upstream(self, a: float, b: float = 0.0) -> int:
        lo = -a
        hi = -b
        return sum(1 for v in self.vehicles if lo <= v.x < hi)

    def any_in_range_upstream(self, a: float) -> bool:
        return self.count_in_range_upstream(a, 0.0) > 0

    def count_close_to_line(self, r: float) -> int:
        return self.count_in_range_upstream(r, 0.0)

    def has_stopped_downstream(self, e: float, v_thresh: float = 0.1, min_time: float = 0.5) -> bool:
        for v in self.vehicles:
            if 0.0 <= v.x <= e and (abs(v.v) < v_thresh):
                if min_time <= 0.0 or v.stopped_for >= min_time:
                    return True
        return False

    # Alias para el HUD (usado por app.py)
    def count_red_zone(self, d: float) -> int:
        """
        Devuelve el conteo de vehículos en la 'zona roja' aguas arriba [-d, 0).
        Es un alias de count_in_range_upstream(d, 0.0) para compatibilidad.
        """
        return self.count_in_range_upstream(d, 0.0)

    # Dinámica
    def step(self, dt: float, green: bool):
        if not self.vehicles:
            return
        self.vehicles.sort(key=lambda vv: vv.x)
        for i, v in enumerate(self.vehicles):
            target_v = self.v_max

            # Headway con el de adelante
            if i+1 < len(self.vehicles):
                ahead = self.vehicles[i+1]
                gap = ahead.x - v.x - ahead.length
                if gap < self.safe_gap:
                    target_v = 0.0

            if not green:
                if v.x < 0:
                    dist_to_line = -v.x
                    max_adv = max(0.0, dist_to_line - self.safe_gap)
                    adv = min(target_v*dt, max_adv)
                    v.v = adv/dt if dt>0 else 0.0
                # Si ya cruzó (x>=0), continúa
            else:
                # Verde: si no está bloqueado por "temporizador", avanza
                if v.stopped_for < 0.0:
                    v.v = 0.0
                else:
                    v.v = min(v.v + 2.0*dt, target_v)  # ligera aceleración

            # Integración
            v.x += v.v * dt

            # Tiempo detenido
            if abs(v.v) < 0.1:
                v.stopped_for += dt
            elif v.stopped_for > 0.0:
                v.stopped_for = 0.0

        # avance de bloqueos (si hay temporizador negativo)
        for v in self.vehicles:
            if v.stopped_for < 0.0:
                v.stopped_for += dt
                if v.stopped_for >= 0.0:
                    v.stopped_for = 0.0

    def maybe_induce_block(self, e: float):
        # Aleatoriamente "atasca" un vehículo en [0,e] durante t_block (parcial implementación de reglas 5–6)
        if self.p_block <= 0:
            return
        for v in self.vehicles:
            if 0.0 <= v.x <= e and v.stopped_for == 0.0:
                if self.rng.random() < self.p_block:
                    v.stopped_for = -self.t_block
                    break  # bloquear a lo sumo uno por paso para claridad

    def remove_completed(self, cutoff_x: float) -> int:
        out = 0
        keep = []
        for v in self.vehicles:
            if v.x > cutoff_x:
                out += 1
            else:
                keep.append(v)
        self.vehicles = keep
        return out