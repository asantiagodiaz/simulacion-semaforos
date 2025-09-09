# Simulación Gráfica de Semáforos Auto‑Organizantes

Visualiza en tiempo real un cruce con dos direcciones (A: horizontal, B: vertical) donde los semáforos se auto‑organizan siguiendo 6 reglas. La app está hecha con Pygame y un motor de simulación simple en Python.

## Demo rápida

- Ejecuta la app y verás:
  - Carretera horizontal (A: izquierda → derecha).
  - Carretera vertical (B: arriba → abajo).
  - Círculos que muestran el estado de las luces (verde/amarillo/rojo).
  - Autos que llegan de forma aleatoria, respetan el semáforo y pueden bloquearse justo después del cruce.
  - En la esquina superior izquierda (HUD) aparecen fase, colas, contadores y parámetros.

## Requisitos

- Python 3.10+ (recomendado 3.11).
- Pygame 2.5+.

Instala dependencias:
```bash
pip install -r requirements.txt
```

Si no tienes `requirements.txt`, instala directamente:
```bash
pip install pygame
```

## Cómo ejecutar

Desde la carpeta del proyecto (donde está `app.py`):
```bash
python app.py
```
En Windows también puedes:
```bash
py app.py
```

Sugerido (Windows/PowerShell): crear un entorno virtual
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python app.py
```
Si PowerShell bloquea la activación:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1
```

## Controles

- P: pausar / reanudar la simulación.
- + / −: ajustar velocidad de la simulación.
- ESC o Q: salir.

## ¿Qué estás viendo?

- A (horizontal): autos avanzan de izquierda a derecha. La luz A está dibujada a la derecha del cruce.
- B (vertical): autos bajan desde arriba hacia abajo. La luz B está dibujada debajo del cruce.
- Guías finas:
  - Cian: distancia de detección `d` y proximidad `r` antes de la línea.
  - Amarillo: distancia `e` después del cruce (zona donde se detectan bloqueos).
- HUD: tiempo simulado, fase actual, tiempo en fase, tamaño de colas A/B, contadores de rojo (demanda acumulada) y cambios de fase.

## Reglas implementadas (Auto‑organización)

Suposiciones y notación (ver esquema original):
- d: distancia de detección desde la línea hacia aguas arriba.
- r: zona corta antes de la línea (vehículos “por cruzar”).
- e: zona corta después del cruce (para detectar bloqueos aguas abajo).
- n: umbral del contador en rojo.
- u: mínimo tiempo en verde.
- y: duración del amarillo.
- m: tamaño máximo del “pequeño pelotón”.

Reglas:
1) Contador en rojo: en cada paso se suma al contador de la dirección en rojo el número de vehículos en [-d, 0). Si el contador supera n, se cambia (y se reinicia el contador de la dirección que recibe verde).
2) Mínimo verde: un verde debe durar al menos u segundos antes de permitir cambios.
3) No cortar pequeños pelotones: si hay entre 1 y m vehículos muy cerca (a r) del semáforo que está en verde, no cambiar aún.
4) Demanda asimétrica: si no hay vehículos acercándose al verde a d y sí hay al rojo a d, cambiar hacia el rojo.
5) Bloqueo aguas abajo: si hay un vehículo detenido justo después del cruce (en [0, e]) en la dirección que está verde, cambiar para evitar bloquear la intersección.
6) Doble bloqueo: si hay vehículos detenidos en [0, e] en ambas direcciones, poner ambas luces en rojo (ALL_RED). Cuando una dirección se libere, restaurar el verde en esa dirección.

Notas:
- Las reglas 5–6 se aprecian mejor si habilitas bloqueos aleatorios (ver parámetros `p_block` y `t_block`).

## Parámetros principales (editar en `app.py`, objeto `SimConfig`)

- Reglas:
  - `n_threshold` (n): umbral del contador en rojo. Ej: 10.
  - `u_min_green` (u): mínimo verde en segundos. Ej: 8–12 s.
  - `y_yellow` (y): duración del amarillo. Ej: 2.0–3.0 s.
  - `m_small_platoon` (m): tamaño de pelotón pequeño. Ej: 1–3.
  - `d_detect` (d): distancia de detección aguas arriba. Ej: 40–70 m.
  - `r_close` (r): zona de proximidad antes de la línea. Ej: 6–12 m.
  - `e_after` (e): zona después del cruce para detectar bloqueo. Ej: 10–20 m.
- Flujo:
  - `lambda_a`, `lambda_b`: tasas de llegada Poisson [veh/s]. Ej: 0.2–0.5.
- Dinámica:
  - `v_max`: velocidad libre [m/s] (~12–14 m/s ~ 43–50 km/h).
  - `safe_gap`: distancia de seguridad entre vehículos [m].
  - `intersection_len`: longitud del cruce [m] (visual).
  - `road_length`: longitud modelada aguas arriba [m].
- Bloqueo (para activar reglas 5–6):
  - `p_block`: probabilidad de que un vehículo que ya cruzó se quede detenido en [0, e] (0 para desactivar).
  - `t_block`: tiempo de bloqueo (segundos).

Ejemplo dentro de `app.py`:
```python
cfg = SimConfig(
    duration=1e9, dt=0.2, seed=42,
    n_threshold=10.0, u_min_green=8.0, y_yellow=2.5, m_small_platoon=2,
    d_detect=45.0, r_close=8.0, e_after=14.0,
    lambda_a=0.35, lambda_b=0.25,
    v_max=12.0, safe_gap=5.0, intersection_len=10.0, road_length=180.0,
    p_block=0.02, t_block=6.0, log_every=9999.0,
)
```

## ¿Cómo funciona por dentro?

- Motor discreto (paso `dt`):
  1. Generación de llegadas Poisson en cada carril (tasas `lambda_a`, `lambda_b`).
  2. Sensores:
     - Vehículos en zona roja [-d, 0) por cada dirección.
     - Vehículos “cerca” de la línea a r para la dirección actualmente verde.
     - Presencia de demanda a distancia d en cada dirección.
     - Detección de bloqueo en [0, e] después del cruce.
  3. Controlador de fases:
     - Implementa reglas 1–6 y administra estados: GREEN_A, YELLOW_A, GREEN_B, YELLOW_B, ALL_RED.
  4. Dinámica:
     - Avance de vehículos con velocidad objetivo, respetando el semáforo y la distancia de seguridad.
     - Ocasionalmente, se induce un bloqueo en [0, e] para simular regla 5–6.
  5. Remoción de vehículos que ya salieron del “escenario”.
- Representación:
  - Sistema 1D por carril con `x=0` en la línea de alto; `x<0` antes del cruce y `x>0` después.
  - La capa gráfica convierte metros a pixeles (escala ajustable).

## Estructura del proyecto

```
simulacion-semaforos/
├─ app.py
├─ requirements.txt
├─ README.md
└─ src/
   ├─ __init__.py
   ├─ sim_core.py     # motor de simulación (tiempo, llegadas, sensores, movimiento)
   ├─ controller.py   # controlador con reglas 1–6 y fases
   ├─ lanes.py        # carriles, sensores (d, r, e), bloqueos, movimiento
   └─ vehicle.py      # entidad vehículo
```

## Calibración y pruebas

- Escenario simétrico: usa `lambda_a = lambda_b` y observa que los verdes se reparten.
- Demanda desequilibrada: aumenta `lambda_a` y verifica que A recibe más verde (reglas 1 y 4).
- Prueba reglas 5–6:
  - Sube `p_block` a 0.05–0.10 para ver bloqueos frecuentes en `[0, e]`.
  - Debería entrar a `ALL_RED` si ambas direcciones quedan bloqueadas.

## Problemas comunes y solución

- “Se abre y se cierra la ventana rápido”:
  - Ejecuta desde la consola (no doble clic): `python app.py` para ver el error.
  - Asegúrate de haber instalado `pygame` en el mismo entorno.
- ImportErrors o AttributeError:
  - Verifica que estás ejecutando desde la raíz (donde está `app.py`).
  - Si ves `AttributeError: 'Lane' object has no attribute 'count_red_zone'`, actualiza `src/lanes.py` para incluir el alias:
    ```python
    def count_red_zone(self, d: float) -> int:
        return self.count_in_range_upstream(d, 0.0)
    ```
- En PowerShell no se activa el venv:
  - Usa `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` y vuelve a activar.

## Entrega en GitHub

1) Crea un repo vacío llamado `simulacion-semaforos` en tu cuenta.
2) Desde esta carpeta:
```bash
git init
git add .
git commit -m "Simulación gráfica de semáforos auto-organizantes"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/simulacion-semaforos.git
git push -u origin main
```

¿Quieres que prepare issues o un plan de mejoras (GUI extra, sonidos, métricas CSV, pruebas automáticas)? Pídelo y te los dejo listos.