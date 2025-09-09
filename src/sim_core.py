from dataclasses import dataclass
from typing import Dict
import random

from .lanes import Lane
from .controller import Controller, ControllerConfig, Phase

@dataclass
class SimConfig:
    duration: float
    dt: float
    seed: int

    # Reglas
    n_threshold: float
    u_min_green: float
    y_yellow: float
    m_small_platoon: int
    d_detect: float
    r_close: float
    e_after: float

    # Dinámica
    lambda_a: float
    lambda_b: float
    v_max: float
    safe_gap: float
    intersection_len: float
    road_length: float
    p_block: float
    t_block: float

    # Logging
    log_every: float = 5.0

class Simulation:
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)

        self.lane_A = Lane("A", cfg.road_length, cfg.v_max, cfg.safe_gap, cfg.p_block, cfg.t_block, seed=cfg.seed + 1)
        self.lane_B = Lane("B", cfg.road_length, cfg.v_max, cfg.safe_gap, cfg.p_block, cfg.t_block, seed=cfg.seed + 2)

        self.ctrl = Controller(ControllerConfig(
            n_threshold=cfg.n_threshold,
            u_min_green=cfg.u_min_green,
            y_yellow=cfg.y_yellow,
            m_small_platoon=cfg.m_small_platoon,
            d_detect=cfg.d_detect,
            r_close=cfg.r_close,
            e_after=cfg.e_after,
        ))

        self.time = 0.0
        self.completed_A = 0
        self.completed_B = 0

    def step_once(self):
        cfg = self.cfg

        # Llegadas
        self.lane_A.spawn_poisson(cfg.lambda_a, cfg.dt, self.time)
        self.lane_B.spawn_poisson(cfg.lambda_b, cfg.dt, self.time)

        # Sensores
        a_red = self.lane_A.count_in_range_upstream(cfg.d_detect)
        b_red = self.lane_B.count_in_range_upstream(cfg.d_detect)
        a_close = self.lane_A.count_close_to_line(cfg.r_close)
        b_close = self.lane_B.count_close_to_line(cfg.r_close)
        a_any_d = self.lane_A.any_in_range_upstream(cfg.d_detect)
        b_any_d = self.lane_B.any_in_range_upstream(cfg.d_detect)
        a_stop_after = self.lane_A.has_stopped_downstream(cfg.e_after, v_thresh=0.1, min_time=0.5)
        b_stop_after = self.lane_B.has_stopped_downstream(cfg.e_after, v_thresh=0.1, min_time=0.5)

        # Controlador
        self.ctrl.step(cfg.dt, a_red, b_red, a_close, b_close, a_any_d, b_any_d, a_stop_after, b_stop_after)

        green_A = self.ctrl.is_green(True)
        green_B = self.ctrl.is_green(False)

        # Bloqueos intencionales ocasionales
        if green_A:
            self.lane_A.maybe_induce_block(cfg.e_after)
        if green_B:
            self.lane_B.maybe_induce_block(cfg.e_after)

        # Movimiento
        # Nota: en amarillo consideramos "no verde"
        self.lane_A.step(cfg.dt, green_A)
        self.lane_B.step(cfg.dt, green_B)

        # Salidas
        cutoff = cfg.e_after + cfg.intersection_len + 25.0
        self.completed_A += self.lane_A.remove_completed(cutoff)
        self.completed_B += self.lane_B.remove_completed(cutoff)

        self.time += cfg.dt

    def run_for(self, duration: float):
        steps = int(duration / self.cfg.dt)
        for _ in range(steps):
            self.step_once()
        return {
            "completed_A": self.completed_A,
            "completed_B": self.completed_B,
        }