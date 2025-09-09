from dataclasses import dataclass
from enum import Enum, auto

class Phase(Enum):
    GREEN_A = auto()
    YELLOW_A = auto()
    GREEN_B = auto()
    YELLOW_B = auto()
    ALL_RED = auto()

@dataclass
class ControllerConfig:
    n_threshold: float
    u_min_green: float
    y_yellow: float
    m_small_platoon: int
    d_detect: float
    r_close: float
    e_after: float

class Controller:
    def __init__(self, cfg: ControllerConfig):
        self.cfg = cfg
        self.phase = Phase.GREEN_A
        self.t_in_phase = 0.0
        self.red_counter_A = 0.0
        self.red_counter_B = 0.0
        self.switches = 0

    def is_green(self, for_A: bool) -> bool:
        if self.phase == Phase.GREEN_A:
            return for_A
        if self.phase == Phase.GREEN_B:
            return not for_A
        return False

    def step(self, dt: float,
             count_A_red_zone: int,
             count_B_red_zone: int,
             count_A_close_green: int,
             count_B_close_green: int,
             any_A_d: bool,
             any_B_d: bool,
             stopped_A_after: bool,
             stopped_B_after: bool):
        c = self.cfg
        self.t_in_phase += dt

        # Contador en rojo (regla 1)
        if self.phase in (Phase.GREEN_A, Phase.YELLOW_A, Phase.ALL_RED):
            self.red_counter_B += count_B_red_zone
        if self.phase in (Phase.GREEN_B, Phase.YELLOW_B, Phase.ALL_RED):
            self.red_counter_A += count_A_red_zone

        # Regla 6: ambos bloqueados -> ALL_RED, desbloquear cuando una dirección se libere
        if self.phase == Phase.ALL_RED:
            if stopped_A_after and stopped_B_after:
                return
            if not stopped_A_after and stopped_B_after:
                self._to(Phase.GREEN_A); return
            if stopped_A_after and not stopped_B_after:
                self._to(Phase.GREEN_B); return
            # ambos libres: elegir por demanda
            if self.red_counter_A >= self.red_counter_B:
                self._to(Phase.GREEN_A)
            else:
                self._to(Phase.GREEN_B)
            return

        if stopped_A_after and stopped_B_after:
            self._to(Phase.ALL_RED); return

        # Regla 5: si verde bloqueado aguas abajo -> cambiar (respetando u)
        if stopped_A_after and self.phase == Phase.GREEN_A and self._min_green_ok():
            self._start_yellow(Phase.YELLOW_A); return
        if stopped_B_after and self.phase == Phase.GREEN_B and self._min_green_ok():
            self._start_yellow(Phase.YELLOW_B); return

        # Regla 2: mínimo verde
        if not self._min_green_ok():
            pass  # no se permite cambiar aún
        else:
            # Regla 3: no cortar pelotón pequeño en r
            if self.phase == Phase.GREEN_A and 0 < count_A_close_green <= c.m_small_platoon:
                pass
            elif self.phase == Phase.GREEN_B and 0 < count_B_close_green <= c.m_small_platoon:
                pass
            else:
                # Regla 4: sin demanda en verde a d y hay en rojo a d
                if self.phase == Phase.GREEN_A and (not any_A_d) and any_B_d:
                    self._start_yellow(Phase.YELLOW_A); return
                if self.phase == Phase.GREEN_B and (not any_B_d) and any_A_d:
                    self._start_yellow(Phase.YELLOW_B); return
                # Regla 1: umbral en rojo
                if self.phase == Phase.GREEN_A and self.red_counter_B > c.n_threshold:
                    self._start_yellow(Phase.YELLOW_A); return
                if self.phase == Phase.GREEN_B and self.red_counter_A > c.n_threshold:
                    self._start_yellow(Phase.YELLOW_B); return

        # Final de amarillos -> conmutar
        if self.phase == Phase.YELLOW_A and self.t_in_phase >= c.y_yellow:
            self._to(Phase.GREEN_B); self.red_counter_B = 0.0; return
        if self.phase == Phase.YELLOW_B and self.t_in_phase >= c.y_yellow:
            self._to(Phase.GREEN_A); self.red_counter_A = 0.0; return

    def _min_green_ok(self) -> bool:
        return (self.phase not in (Phase.GREEN_A, Phase.GREEN_B)) or (self.t_in_phase >= self.cfg.u_min_green)

    def _start_yellow(self, yphase: Phase):
        if self.phase != yphase:
            self.phase = yphase
            self.t_in_phase = 0.0
            self.switches += 1

    def _to(self, phase: Phase):
        if self.phase != phase:
            self.phase = phase
            self.t_in_phase = 0.0
            self.switches += 1