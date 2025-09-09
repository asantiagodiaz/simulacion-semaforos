# app.py
import pygame
import random
import math
from collections import defaultdict

pygame.init()

# ---------------- Configuración ----------------
WIDTH, HEIGHT = 900, 900
GRID_SIZE = 3   # 3x3 celdas; calles se dibujan en las líneas intermedias -> 2 calles (GRID_SIZE-1)
CELL_W = WIDTH // GRID_SIZE
CELL_H = HEIGHT // GRID_SIZE

ROAD_W = 80            # ancho de la carretera (pixeles)
LANE_OFFSET = 14       # separación entre carriles dentro de la carretera
CAR_SIZE = 10
CAR_SPEED = 2.0
SPAWN_INTERVAL_FRAMES = 18   # cuanto menor -> más tráfico

# sensores/semáforo parámetros (metros -> pixeles)
D_DETECT = 160     # detección a distancia (pixels)
R_CLOSE = 24       # proximidad para "pequeño pelotón"
E_AFTER = 36       # zona después del cruce para bloqueo
N_THRESHOLD = 6    # umbral contador en rojo para cambiar
U_MIN_GREEN = 60   # mínimo verde (frames)
Y_YELLOW = 30      # frames de amarillo
M_SMALL = 2        # tamaño max pelotón pequeño

BG_GRASS = (20, 120, 40)
ROAD_COLOR = (60, 60, 60)
CAR_COLOR = (30, 80, 200)
TL_GREEN = (50, 200, 50)
TL_YELLOW = (240, 200, 50)
TL_RED = (200, 40, 40)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Semáforos inteligentes — cuadrícula 3x3 (calles intermedias)")
clock = pygame.time.Clock()

# ---------------- Utility ----------------
def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

# ---------------- Traffic Light & Intersection ----------------
class TrafficLight:
    """
    Estados: GREEN_NS, YELLOW_NS, GREEN_EW, YELLOW_EW, ALL_RED
    Implementa reglas básicas: contador en rojo, mínimo verde, no cortar pequeños pelotones,
    demanda asimétrica y detección de bloqueo (simplificado).
    """
    def __init__(self, cx, cy):
        self.cx = cx
        self.cy = cy
        self.state = "GREEN_NS"
        self.time_in_state = 0
        self.red_counter_NS = 0.0   # demanda acumulada para NS cuando está en rojo
        self.red_counter_EW = 0.0
        # parámetros (puedes exponer para tuning)
        self.d = D_DETECT
        self.r = R_CLOSE
        self.e = E_AFTER
        self.n = N_THRESHOLD
        self.u = U_MIN_GREEN
        self.y = Y_YELLOW
        self.m = M_SMALL

    def update(self, vehicles):
        """Actualizar estado según reglas y conteos dados los vehículos (lista de Vehicle)."""
        self.time_in_state += 1

        # Contar vehículos aproximándose (a distancia d) por dirección (NS vs EW)
        cars_NS_upstream = 0
        cars_EW_upstream = 0
        cars_NS_near = 0
        cars_EW_near = 0
        blocked_NS_after = 0
        blocked_EW_after = 0

        # límites horizontales de la carretera alrededor de cx/cy
        lane_tol = ROAD_W // 2 + 6

        for v in vehicles:
            # considerar solo vehículos que están en la franja de esta intersección
            if abs(v.x - self.cx) <= lane_tol or abs(v.y - self.cy) <= lane_tol:
                # NS (vehículos que circulan verticalmente)
                if v.dir in ("S", "N"):
                    # para S: viene desde arriba (y < cy). para N: viene desde abajo (y > cy)
                    # distancia en coordenada longitudinal al cruce:
                    if v.dir == "S" and v.y < self.cy:
                        d_up = self.cy - v.y
                        if d_up <= self.d and abs(v.x - self.cx) <= lane_tol:
                            cars_NS_upstream += 1
                        if d_up <= self.r and abs(v.x - self.cx) <= lane_tol:
                            cars_NS_near += 1
                    elif v.dir == "N" and v.y > self.cy:
                        d_up = v.y - self.cy
                        if d_up <= self.d and abs(v.x - self.cx) <= lane_tol:
                            cars_NS_upstream += 1
                        if d_up <= self.r and abs(v.x - self.cx) <= lane_tol:
                            cars_NS_near += 1

                    # detectar bloqueo después del cruce (en [0, e]) -> para S: y in (cy, cy+e)
                    if v.dir == "S" and v.y > self.cy and v.y - self.cy <= self.e:
                        # considerar como bloqueo si está casi detenido (velocidad baja)
                        if v.stopped:
                            blocked_NS_after += 1
                    if v.dir == "N" and self.cy - v.y <= self.e and v.y < self.cy:
                        if v.stopped:
                            blocked_NS_after += 1

                # EW (vehículos que circulan horizontalmente)
                if v.dir in ("E", "W"):
                    if v.dir == "E" and v.x < self.cx:
                        d_up = self.cx - v.x
                        if d_up <= self.d and abs(v.y - self.cy) <= lane_tol:
                            cars_EW_upstream += 1
                        if d_up <= self.r and abs(v.y - self.cy) <= lane_tol:
                            cars_EW_near += 1
                    elif v.dir == "W" and v.x > self.cx:
                        d_up = v.x - self.cx
                        if d_up <= self.d and abs(v.y - self.cy) <= lane_tol:
                            cars_EW_upstream += 1
                        if d_up <= self.r and abs(v.y - self.cy) <= lane_tol:
                            cars_EW_near += 1

                    if v.dir == "E" and v.x > self.cx and v.x - self.cx <= self.e:
                        if v.stopped:
                            blocked_EW_after += 1
                    if v.dir == "W" and self.cx - v.x <= self.e and v.x < self.cx:
                        if v.stopped:
                            blocked_EW_after += 1

        # Actualizar contadores en rojo: al dirección que está en rojo le sumamos la demanda upstream
        if self.state in ("GREEN_NS", "YELLOW_NS"):
            # EW está en rojo -> acumular para EW
            self.red_counter_EW += cars_EW_upstream
        elif self.state in ("GREEN_EW", "YELLOW_EW"):
            self.red_counter_NS += cars_NS_upstream
        elif self.state == "ALL_RED":
            # si está ALL_RED, no acumular
            pass

        # Reglas:
        # 1. mínimo verde (u)
        # 2. si bloqueo aguas abajo en la dirección verde -> cambiar
        # 3. si contador rojo supera n -> cambiar
        # 4. no cortar pequeños pelotones: si hay 1..m en la dirección verde muy cerca (r) -> no cambiar
        # 5. demanda asimétrica: si no hay acercando al verde pero sí al rojo -> cambiar
        # 6. doble bloqueo: si bloqueo en ambas direcciones -> ALL_RED

        # detect double blockage
        if blocked_NS_after > 0 and blocked_EW_after > 0 and self.state != "ALL_RED":
            self.state = "ALL_RED"
            self.time_in_state = 0
            return

        if self.state == "ALL_RED":
            # esperar hasta que se libere alguna dirección
            self.time_in_state += 0  # ya se aumentó arriba
            # si NS ya no bloqueado -> volver verde NS; si EW no bloqueado -> regresar EW
            if blocked_NS_after == 0 and (cars_NS_upstream > 0 or cars_NS_near > 0):
                self.state = "GREEN_NS"
                self.time_in_state = 0
                self.red_counter_NS = 0
                self.red_counter_EW = 0
            elif blocked_EW_after == 0 and (cars_EW_upstream > 0 or cars_EW_near > 0):
                self.state = "GREEN_EW"
                self.time_in_state = 0
                self.red_counter_NS = 0
                self.red_counter_EW = 0
            return

        # Helper booleans
        is_green_NS = self.state == "GREEN_NS"
        is_green_EW = self.state == "GREEN_EW"

        # do nothing if min green not reached
        if self.time_in_state < self.u:
            return

        # If green is NS:
        if is_green_NS:
            # rule: don't cut small platoon
            if 1 <= cars_NS_near <= self.m:
                return
            # if blocked after in NS -> switch
            if blocked_NS_after > 0:
                self.state = "YELLOW_NS"
                self.time_in_state = 0
                return
            # demand asymmetry: if no approaching NS but some approaching EW -> switch
            if cars_NS_upstream == 0 and cars_EW_upstream > 0:
                self.state = "YELLOW_NS"
                self.time_in_state = 0
                return
            # counter threshold
            if self.red_counter_EW >= self.n:
                self.state = "YELLOW_NS"
                self.time_in_state = 0
                self.red_counter_EW = 0
                return

        if is_green_EW:
            if 1 <= cars_EW_near <= self.m:
                return
            if blocked_EW_after > 0:
                self.state = "YELLOW_EW"
                self.time_in_state = 0
                return
            if cars_EW_upstream == 0 and cars_NS_upstream > 0:
                self.state = "YELLOW_EW"
                self.time_in_state = 0
                return
            if self.red_counter_NS >= self.n:
                self.state = "YELLOW_EW"
                self.time_in_state = 0
                self.red_counter_NS = 0
                return

        # if in a YELLOW state and yellow time passed -> change to opposite GREEN
        if self.state == "YELLOW_NS":
            if self.time_in_state >= self.y:
                self.state = "GREEN_EW"
                self.time_in_state = 0
                # reset counters
                self.red_counter_EW = 0
                return
        elif self.state == "YELLOW_EW":
            if self.time_in_state >= self.y:
                self.state = "GREEN_NS"
                self.time_in_state = 0
                self.red_counter_NS = 0
                return

    def color_for(self, direction):
        """Devuelve TL_GREEN/TL_YELLOW/TL_RED para una dirección dada ('N','S','E','W')."""
        if self.state == "ALL_RED":
            return TL_RED
        if direction in ("N", "S"):
            if self.state == "GREEN_NS":
                return TL_GREEN
            if self.state == "YELLOW_NS":
                return TL_YELLOW
            return TL_RED
        else:
            if self.state == "GREEN_EW":
                return TL_GREEN
            if self.state == "YELLOW_EW":
                return TL_YELLOW
            return TL_RED

    def draw(self, surf):
        # dibujar 4 pequeños círculos alrededor del cruce: N S E W
        r = 8
        # N
        pygame.draw.circle(surf, self.color_for("N"), (int(self.cx), int(self.cy - 16)), r)
        # S
        pygame.draw.circle(surf, self.color_for("S"), (int(self.cx), int(self.cy + 16)), r)
        # E
        pygame.draw.circle(surf, self.color_for("E"), (int(self.cx + 16), int(self.cy)), r)
        # W
        pygame.draw.circle(surf, self.color_for("W"), (int(self.cx - 16), int(self.cy)), r)

# ---------------- Vehicle ----------------
class Vehicle:
    """
    Vehicle circula en carril fijo (para vertical -> lane_x, para horizontal -> lane_y).
    dir: 'S' (hacia abajo), 'N' (hacia arriba), 'E' (hacia derecha), 'W' (izquierda)
    stopped: True si está parado (por semáforo o por coche adelante)
    """
    def __init__(self, x, y, dir_char, lane_center_coord):
        self.x = float(x)
        self.y = float(y)
        self.dir = dir_char
        self.speed = CAR_SPEED
        self.size = CAR_SIZE
        self.lane_center = lane_center_coord   # x for vertical lanes, y for horizontal lanes
        self.stopped = False

    def update(self, intersections, other_vehicles):
        """
        - Mantiene la posición en el centro del carril (corrige lateralmente si hace falta).
        - Respeta semáforos (se detiene antes del stop line si la luz está roja/amarilla).
        - Respeta distancia con vehículo que va delante en el mismo carril.
        """
        # mantener alineacion en carril
        lane_tol = 2
        if self.dir in ("S", "N"):
            # lane_center is x coordinate
            if abs(self.x - self.lane_center) > lane_tol:
                # corregir suavemente
                self.x += (self.lane_center - self.x) * 0.4
        else:
            # horizontal lanes: lane_center is y coordinate
            if abs(self.y - self.lane_center) > lane_tol:
                self.y += (self.lane_center - self.y) * 0.4

        # comprobar vehículo adelante en mismo carril (para mantener separación)
        safe_gap = 14
        slowed_by_vehicle = False
        for other in other_vehicles:
            if other is self:
                continue
            # mismo carril: mismas coordenadas laterales aproximadas y misma dirección
            if self.dir == other.dir:
                if self.dir in ("S", "N"):
                    if abs(other.lane_center - self.lane_center) < 4:
                        # si other está delante en la dirección de movimiento:
                        if self.dir == "S" and other.y > self.y:
                            if other.y - self.y < safe_gap:
                                slowed_by_vehicle = True
                        if self.dir == "N" and other.y < self.y:
                            if self.y - other.y < safe_gap:
                                slowed_by_vehicle = True
                else:
                    if abs(other.lane_center - self.lane_center) < 4:
                        if self.dir == "E" and other.x > self.x:
                            if other.x - self.x < safe_gap:
                                slowed_by_vehicle = True
                        if self.dir == "W" and other.x < self.x:
                            if self.x - other.x < safe_gap:
                                slowed_by_vehicle = True

        # comprobar semáforos: si hay uno adelante en el camino y la luz está roja/amarilla -> detener en stop line
        stopped_by_light = False
        for inter in intersections:
            # consider only intersections that lie on our road lane (approx)
            if self.dir in ("S", "N") and abs(self.lane_center - inter.cx) <= ROAD_W//2 + 6:
                # vertical travel intersects this intersection
                if self.dir == "S" and self.y < inter.cy:
                    # approaching from top
                    stop_line_y = inter.cy - ROAD_W/2 - 6  # justo antes de la franja de la intersección
                    # if close enough to stop line
                    if self.y + self.size >= stop_line_y - 1:
                        color = inter.color_for("S")
                        if color == TL_RED or color == TL_YELLOW:
                            stopped_by_light = True
                if self.dir == "N" and self.y > inter.cy:
                    stop_line_y = inter.cy + ROAD_W/2 + 6
                    if self.y - self.size <= stop_line_y + 1:
                        color = inter.color_for("N")
                        if color == TL_RED or color == TL_YELLOW:
                            stopped_by_light = True

            if self.dir in ("E", "W") and abs(self.lane_center - inter.cy) <= ROAD_W//2 + 6:
                if self.dir == "E" and self.x < inter.cx:
                    stop_line_x = inter.cx - ROAD_W/2 - 6
                    if self.x + self.size >= stop_line_x - 1:
                        color = inter.color_for("E")
                        if color == TL_RED or color == TL_YELLOW:
                            stopped_by_light = True
                if self.dir == "W" and self.x > inter.cx:
                    stop_line_x = inter.cx + ROAD_W/2 + 6
                    if self.x - self.size <= stop_line_x + 1:
                        color = inter.color_for("W")
                        if color == TL_RED or color == TL_YELLOW:
                            stopped_by_light = True

        # final decision
        if slowed_by_vehicle or stopped_by_light:
            self.stopped = True
        else:
            self.stopped = False

        # mover si no parado
        if not self.stopped:
            if self.dir == "S":
                self.y += self.speed
            elif self.dir == "N":
                self.y -= self.speed
            elif self.dir == "E":
                self.x += self.speed
            elif self.dir == "W":
                self.x -= self.speed

    def draw(self, surf):
        pygame.draw.rect(surf, CAR_COLOR, (int(self.x - CAR_SIZE/2), int(self.y - CAR_SIZE/2), CAR_SIZE, CAR_SIZE))

# ---------------- Simulation ----------------
class Simulation:
    def __init__(self):
        # calcular coordenadas de las calles intermedias (líneas entre celdas)
        self.road_xs = [i * CELL_W for i in range(1, GRID_SIZE)]  # p.e. [CELL_W, 2*CELL_W] para GRID_SIZE=3
        self.road_ys = [i * CELL_H for i in range(1, GRID_SIZE)]
        # crear intersecciones en todas las intersecciones de road_xs x road_ys
        self.intersections = []
        for x in self.road_xs:
            for y in self.road_ys:
                self.intersections.append(TrafficLight(x + 0.0, y + 0.0))

        self.vehicles = []
        self.frame = 0

        # construir posiciones de carriles (2 carriles por carretera: uno por sentido)
        self.vertical_lane_x = []  # lista de lane x positions (one for each road & side)
        for rx in self.road_xs:
            # lane for northbound (left lane), lane for southbound (right lane) relative to road center
            self.vertical_lane_x.append(rx - LANE_OFFSET)  # lane for S (coming from top -> down)
            self.vertical_lane_x.append(rx + LANE_OFFSET)  # lane for N (coming from bottom -> up)

        self.horizontal_lane_y = []
        for ry in self.road_ys:
            self.horizontal_lane_y.append(ry - LANE_OFFSET)  # lane for E (from left -> right)
            self.horizontal_lane_y.append(ry + LANE_OFFSET)  # lane for W (from right -> left)

    def spawn_vehicle(self):
        # spawn only on intermedate roads (not anywhere) - choose one road and a direction
        spawn_margin = 10
        # choose direction from top/bottom/left/right equally, and choose one of the internal roads
        side = random.choice(["top", "bottom", "left", "right"])
        if side in ("top", "bottom"):
            rx = random.choice(self.road_xs)
            # choose which vertical lane to use for this direction:
            # if side == top -> vehicle goes S (down) -> lane x = rx - LANE_OFFSET (we assigned earlier)
            if side == "top":
                lane_x = rx - LANE_OFFSET
                x = lane_x
                y = -spawn_margin
                dir_char = "S"
            else:
                lane_x = rx + LANE_OFFSET
                x = lane_x
                y = HEIGHT + spawn_margin
                dir_char = "N"
            v = Vehicle(x, y, dir_char, lane_x)
            self.vehicles.append(v)
        else:  # left or right
            ry = random.choice(self.road_ys)
            if side == "left":
                lane_y = ry - LANE_OFFSET
                x = -spawn_margin
                y = lane_y
                dir_char = "E"
            else:
                lane_y = ry + LANE_OFFSET
                x = WIDTH + spawn_margin
                y = lane_y
                dir_char = "W"
            v = Vehicle(x, y, dir_char, lane_y)
            self.vehicles.append(v)

    def update(self):
        # actualizar intersecciones (sems) con la lista actual de vehículos
        for inter in self.intersections:
            inter.update(self.vehicles)

        # actualizar vehículos (orden por trayectoria para una detección coherente)
        # actualizar todos, pero pasamos la lista completa para chequeos de delante/parada
        for v in self.vehicles:
            v.update(self.intersections, self.vehicles)

        # remover vehículos que salieron del mapa (para reciclar)
        self.vehicles = [v for v in self.vehicles if -50 <= v.x <= WIDTH + 50 and -50 <= v.y <= HEIGHT + 50]

    def draw(self, surf):
        # fondo
        surf.fill(BG_GRASS)

        # dibujar calles horizontales y verticales (solo en las líneas intermedias)
        for ry in self.road_ys:
            pygame.draw.rect(surf, ROAD_COLOR, (0, ry - ROAD_W//2, WIDTH, ROAD_W))
        for rx in self.road_xs:
            pygame.draw.rect(surf, ROAD_COLOR, (rx - ROAD_W//2, 0, ROAD_W, HEIGHT))

        # opcional: dibujar marcas de carril (líneas discontinuas)
        mark_len = 18
        mark_gap = 20
        for rx in self.road_xs:
            # vertical: pintar marcas al centro de carril para el sentido S (en la parte superior) y sentido N (inferior)
            x_center = rx
            # center dashed line vertical
            y = -mark_gap
            while y < HEIGHT + mark_len:
                pygame.draw.rect(surf, (200,200,200), (int(x_center-2), int(y), 4, mark_len))
                y += mark_len + mark_gap
        for ry in self.road_ys:
            # horizontal dashed
            y_center = ry
            x = -mark_gap
            while x < WIDTH + mark_len:
                pygame.draw.rect(surf, (200,200,200), (int(x), int(y_center-2), mark_len, 4))
                x += mark_len + mark_gap

        # dibujar intersecciones (semáforos)
        for inter in self.intersections:
            inter.draw(surf)

        # dibujar vehículos
        for v in self.vehicles:
            v.draw(surf)

    def step(self):
        # spawn policy (más tráfico)
        if self.frame % SPAWN_INTERVAL_FRAMES == 0:
            self.spawn_vehicle()
        self.update()
        self.frame += 1

# ---------------- Main ----------------
def main():
    sim = Simulation()
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE or ev.key == pygame.K_q:
                    running = False

        sim.step()
        sim.draw(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
