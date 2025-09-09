#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import math
import pygame
from pygame import Color
from src.sim_core import Simulation, SimConfig
from src.controller import Phase

# Escala y geometría
PX_PER_M = 4.0
SCREEN_W, SCREEN_H = 900, 700
CENTER_X, CENTER_Y = SCREEN_W // 2, SCREEN_H // 2

ROAD_WIDTH = 80  # ancho de calzada visual
LANE_OFFSET = 0  # un carril por dirección (centrado)
CAR_LENGTH_PX = 18
CAR_WIDTH_PX = 10

# Colores
GRAY_DARK = Color(40, 40, 40)
GRAY_ROAD = Color(90, 90, 90)
WHITE = Color(230, 230, 230)
GREEN = Color(0, 190, 0)
YELLOW = Color(230, 180, 0)
RED = Color(220, 0, 0)
BLUE = Color(80, 140, 255)
CYAN = Color(0, 200, 200)
TEXT = Color(240, 240, 240)

def m_to_px(m):
    return int(round(m * PX_PER_M))

def draw_roads(surface):
    # Horizontal
    pygame.draw.rect(surface, GRAY_ROAD, (0, CENTER_Y - ROAD_WIDTH//2, SCREEN_W, ROAD_WIDTH))
    # Vertical
    pygame.draw.rect(surface, GRAY_ROAD, (CENTER_X - ROAD_WIDTH//2, 0, ROAD_WIDTH, SCREEN_H))

    # Líneas de alto (para referencia)
    pygame.draw.line(surface, WHITE, (CENTER_X - ROAD_WIDTH//2, CENTER_Y - ROAD_WIDTH//2),
                     (CENTER_X + ROAD_WIDTH//2, CENTER_Y - ROAD_WIDTH//2), 2)
    pygame.draw.line(surface, WHITE, (CENTER_X - ROAD_WIDTH//2, CENTER_Y + ROAD_WIDTH//2),
                     (CENTER_X + ROAD_WIDTH//2, CENTER_Y + ROAD_WIDTH//2), 2)
    pygame.draw.line(surface, WHITE, (CENTER_X - ROAD_WIDTH//2, CENTER_Y - ROAD_WIDTH//2),
                     (CENTER_X - ROAD_WIDTH//2, CENTER_Y + ROAD_WIDTH//2), 2)
    pygame.draw.line(surface, WHITE, (CENTER_X + ROAD_WIDTH//2, CENTER_Y - ROAD_WIDTH//2),
                     (CENTER_X + ROAD_WIDTH//2, CENTER_Y + ROAD_WIDTH//2), 2)

def draw_light(surface, x, y, state_color):
    # Semáforo sencillo (círculo)
    pygame.draw.circle(surface, state_color, (x, y), 10)
    pygame.draw.circle(surface, WHITE, (x, y), 10, 1)

def draw_signals(surface, ctrl_phase):
    # Posiciones aproximadas para dos cabezales (uno por aproximación)
    # A (horizontal): luz a la derecha del cruce para tráfico de izquierda a derecha
    # B (vertical): luz debajo del cruce para tráfico de arriba hacia abajo
    color_A = RED
    color_B = RED
    if ctrl_phase == Phase.GREEN_A:
        color_A = GREEN
    elif ctrl_phase == Phase.YELLOW_A:
        color_A = YELLOW
    elif ctrl_phase == Phase.GREEN_B:
        color_B = GREEN
    elif ctrl_phase == Phase.YELLOW_B:
        color_B = YELLOW
    elif ctrl_phase == Phase.ALL_RED:
        color_A = RED
        color_B = RED

    draw_light(surface, CENTER_X + ROAD_WIDTH//2 + 18, CENTER_Y - 18, color_A)
    draw_light(surface, CENTER_X - 18, CENTER_Y + ROAD_WIDTH//2 + 18, color_B)

def draw_vehicle(surface, lane_name, x_m, color=BLUE):
    # Convertir posición de la simulación a coordenadas de pantalla.
    # x_m es la coordenada 1D de ese carril (0 en la línea de alto).
    if lane_name == "A":
        # A: horizontal, movimiento hacia +x (izq -> der)
        screen_x = CENTER_X + m_to_px(x_m)
        screen_y = CENTER_Y - LANE_OFFSET
        rect = pygame.Rect(0, 0, CAR_LENGTH_PX, CAR_WIDTH_PX)
        rect.center = (screen_x, screen_y)
        pygame.draw.rect(surface, color, rect, border_radius=2)
    else:
        # B: vertical, movimiento hacia +x en eje vertical (arriba -> abajo)
        screen_x = CENTER_X + LANE_OFFSET
        screen_y = CENTER_Y + m_to_px(x_m)
        rect = pygame.Rect(0, 0, CAR_WIDTH_PX, CAR_LENGTH_PX)
        rect.center = (screen_x, screen_y)
        pygame.draw.rect(surface, color, rect, border_radius=2)

def draw_sensing_guides(surface, cfg):
    # Dibuja d, r y e como guías visuales
    # Para A (horizontal)
    d_px = m_to_px(cfg.d_detect)
    r_px = m_to_px(cfg.r_close)
    e_px = m_to_px(cfg.e_after)

    # Región [-d,0) a la izquierda del cruce
    pygame.draw.line(surface, CYAN, (CENTER_X - d_px, CENTER_Y - ROAD_WIDTH//2 - 10),
                     (CENTER_X, CENTER_Y - ROAD_WIDTH//2 - 10), 1)
    pygame.draw.line(surface, CYAN, (CENTER_X, CENTER_Y - ROAD_WIDTH//2 - 5),
                     (CENTER_X, CENTER_Y - ROAD_WIDTH//2 - 15), 1)
    # Región corta r antes de la línea
    pygame.draw.line(surface, CYAN, (CENTER_X - r_px, CENTER_Y - ROAD_WIDTH//2 - 20),
                     (CENTER_X, CENTER_Y - ROAD_WIDTH//2 - 20), 1)

    # Para B (vertical) arriba del cruce
    pygame.draw.line(surface, CYAN, (CENTER_X + ROAD_WIDTH//2 + 10, CENTER_Y - d_px),
                     (CENTER_X + ROAD_WIDTH//2 + 10, CENTER_Y), 1)
    pygame.draw.line(surface, CYAN, (CENTER_X + ROAD_WIDTH//2 + 5, CENTER_Y),
                     (CENTER_X + ROAD_WIDTH//2 + 15, CENTER_Y), 1)
    pygame.draw.line(surface, CYAN, (CENTER_X + ROAD_WIDTH//2 + 20, CENTER_Y - r_px),
                     (CENTER_X + ROAD_WIDTH//2 + 20, CENTER_Y), 1)

    # Región e después del cruce (ambas direcciones)
    pygame.draw.line(surface, YELLOW, (CENTER_X, CENTER_Y + e_px),
                     (CENTER_X + 8, CENTER_Y + e_px), 1)
    pygame.draw.line(surface, YELLOW, (CENTER_X + e_px, CENTER_Y),
                     (CENTER_X + e_px, CENTER_Y + 8), 1)

def draw_hud(surface, font, sim):
    cfg = sim.cfg
    ctrl = sim.ctrl
    qA = sim.lane_A.count_red_zone(cfg.road_length)
    qB = sim.lane_B.count_red_zone(cfg.road_length)

    lines = [
        f"t = {sim.time:6.1f}s   fase: {ctrl.phase.name}   en fase: {ctrl.t_in_phase:4.1f}s",
        f"qA={qA} qB={qB}   contRojoA={ctrl.red_counter_A:.1f}  contRojoB={ctrl.red_counter_B:.1f}",
        f"completados A/B = {sim.completed_A}/{sim.completed_B}   cambios={ctrl.switches}",
        f"u(min verde)={cfg.u_min_green}s, y(amarillo)={cfg.y_yellow}s, n(umbral)={cfg.n_threshold}, m={cfg.m_small_platoon}",
        f"d={cfg.d_detect}m, r={cfg.r_close}m, e={cfg.e_after}m   v_max={cfg.v_max}m/s",
        "Controles: P pausa/reanuda | +/- velocidad sim | ESC salir"
    ]
    x = 10
    y = 10
    for ln in lines:
        surf = font.render(ln, True, TEXT)
        surface.blit(surf, (x, y))
        y += surf.get_height() + 2

def main():
    pygame.init()
    pygame.display.set_caption("Simulación de Semáforos Auto-Organizantes")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 16)

    cfg = SimConfig(
        duration=1e9,         # corremos hasta que cierres
        dt=0.2,               # paso de simulación (s)
        seed=42,
        n_threshold=10.0,
        u_min_green=8.0,
        y_yellow=2.5,
        m_small_platoon=2,
        d_detect=45.0,
        r_close=8.0,
        e_after=14.0,
        lambda_a=0.35,
        lambda_b=0.25,
        v_max=12.0,
        safe_gap=5.0,
        intersection_len=10.0,
        road_length=180.0,
        p_block=0.02,
        t_block=6.0,
        log_every=9999.0,   # sin logs de consola
    )
    sim = Simulation(cfg)

    running = True
    paused = False
    sim_speed = 1.0  # multiplicador de velocidad (pasos por frame)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    sim_speed = min(5.0, sim_speed + 0.25)
                elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                    sim_speed = max(0.25, sim_speed - 0.25)

        if not paused:
            # Avanzar la simulación; ejecutar múltiples subpasos si sim_speed > 1
            substeps = max(1, int(round(sim_speed)))
            for _ in range(substeps):
                sim.step_once()

        # Dibujo
        screen.fill(GRAY_DARK)
        draw_roads(screen)
        draw_signals(screen, sim.ctrl.phase)
        draw_sensing_guides(screen, sim.cfg)

        # Vehículos
        for v in sim.lane_A.vehicles:
            color = BLUE if v.x < 0 else Color(120, 200, 255)
            # Si está bloqueado aguas abajo (tiempo_detenido negativo en our model) lo mostramos rojo
            if v.stopped_for < 0:
                color = RED
            draw_vehicle(screen, "A", v.x, color=color)

        for v in sim.lane_B.vehicles:
            color = BLUE if v.x < 0 else Color(120, 200, 255)
            if v.stopped_for < 0:
                color = RED
            draw_vehicle(screen, "B", v.x, color=color)

        draw_hud(screen, font, sim)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("\nOcurrió un error. Presiona Enter para cerrar...")