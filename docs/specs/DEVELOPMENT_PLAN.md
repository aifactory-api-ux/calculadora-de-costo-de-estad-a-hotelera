# DEVELOPMENT PLAN: Calculadora de Costo de Estadía Hotelera

## 1. ARCHITECTURE OVERVIEW

**Naturaleza del proyecto:** librería Python pura, sin estado, sin I/O, sin servidor, sin interfaz y sin Docker (explícitamente excluidos por el requerimiento). Se consume únicamente como dependencia (`import booking`) en los scripts del equipo de revenue.

**Alcance técnico:** Python ≥ 3.10, solo biblioteca estándar (`datetime`, `decimal`, `typing`). `pytest` como dependencia exclusiva de desarrollo. Cero dependencias de runtime.

**Estructura de carpetas (según §4 del contrato técnico):**

```text
.
├── pyproject.toml            # PEP 621, setuptools, pythonpath=["src"], testpaths=["tests"], extra dev
├── README.md                 # uso breve + contrato de errores + ejemplo verificado
├── src/
│   ├── __init__.py           # marcador de paquete (sin re-exports)
│   └── booking.py            # módulo completo de la librería
└── tests/
    └── test_booking.py       # suite pytest
```

**Superficie pública (`src/booking.py`):**

| Export | Firma | Retorno |
|---|---|---|
| `RoomType` | `Literal["single","double","suite"]` | alias de tipo |
| `nights` | `(check_in: date, check_out: date) -> int` | `int` en `[1,30]` |
| `nightly_rate` | `(day: date, room: str) -> Decimal` | `Decimal` con 2 decimales |
| `stay_total` | `(check_in: date, check_out: date, room: str, guests: int) -> Decimal` | `Decimal` con 2 decimales |
| `MAX_NIGHTS` | `Final[int] = 30` | — |
| `BASE_RATES` | `Final[dict[RoomType, Decimal]]` | single 50.00 / double 80.00 / suite 150.00 |
| `WEEKEND_DAYS` | `Final[frozenset[int]] = frozenset({4, 5})` | viernes y sábado (`date.weekday()`) |
| `WEEKEND_SURCHARGE_RATE` | `Final[Decimal] = Decimal("0.25")` | recargo 25 % (valor provisto por el requerimiento) |
| `TOURIST_TAX_PER_GUEST_NIGHT` | `Final[Decimal] = Decimal("2.50")` | tasa turística por huésped/noche |
| `ROOM_CAPACITY` | `Final[dict[RoomType, int]] = {"single":1,"double":2,"suite":4}` | capacidad máxima |
| `LONG_STAY_NIGHTS` | `Final[int] = 7` | umbral de descuento |
| `LONG_STAY_DISCOUNT_RATE` | `Final[Decimal] = Decimal("0.10")` | 10 % solo sobre subtotal de habitación |
| `CENTS` | `Final[Decimal] = Decimal("0.01")` | exponente de cuantización |

**Reglas de negocio fijadas:**
- La tarifa pertenece a la noche que **empieza** en `day`; el estado de fin de semana se deriva de `day.weekday()`, nunca del día siguiente.
- Recargo de fin de semana: `base * (Decimal(1) + WEEKEND_SURCHARGE_RATE)`, luego `quantize(CENTS, ROUND_HALF_UP)`.
- `stay_total`: subtotal de habitación = suma de `nightly_rate` de cada noche desde `check_in` hasta `check_out - 1 día`; si noches ≥ 7 se aplica `* (1 - LONG_STAY_DISCOUNT_RATE)` **solo** al subtotal de habitación; la tasa turística (`2.50 × huéspedes × noches`) se suma **después** y no recibe descuento; el total se cuantiza a 2 decimales con `ROUND_HALF_UP`.
- Dinero siempre `Decimal` construido desde `str`; jamás `float`.
- Orden de validación obligatorio en `stay_total`: fechas (vía `nights`) → `room` (tipo, luego pertenencia) → `guests` (tipo, luego rango).
- Detección de `datetime`: `isinstance(v, datetime)` se evalúa **antes** de `isinstance(v, date)` porque `datetime` es subclase de `date`.
- `bool` se rechaza en `guests` antes de la comprobación de `int` (`bool` es subclase de `int`).

**Contrato de errores (exhaustivo, mensajes fijos en inglés para permitir aserciones estables; docstrings y comentarios en español según convención del equipo):**

| # | Condición | Excepción | Mensaje |
|---|---|---|---|
| E1 | parámetro de fecha que no es `date` | `TypeError` | `"{name} must be a datetime.date, got {type}"` |
| E2 | parámetro de fecha es `datetime.datetime` | `TypeError` | `"{name} must be a datetime.date, not datetime.datetime"` |
| E4 | `check_out <= check_in` | `ValueError` | `"check_out must be after check_in"` |
| E5 | `(check_out - check_in).days > 30` | `ValueError` | `"stay cannot exceed 30 nights"` |
| E7 | `room` no es `str` | `TypeError` | `"room must be a str, got {type}"` |
| E8 | `room` desconocida | `ValueError` | `"unknown room: {room!r}"` |
| E9 | `guests` no es `int` (incluye `bool`) | `TypeError` | `"guests must be an int, got {type}"` |
| E10 | `guests` fuera de `1..ROOM_CAPACITY[room]` | `ValueError` | `"guests must be between 1 and {capacity} for room {room!r}"` |

**Fuera de alcance (deliberadamente ausente):** HTTP/FastAPI/Flask, base de datos, caché, logging, Docker, docker-compose, `run.sh`, `.env`, frontend, i18n, impuestos adicionales, disponibilidad o cancelaciones. No se añaden archivos fuera de §4.

## 2. ACCEPTANCE CRITERIA

1. `python -c "import sys; sys.path.insert(0,'src'); from booking import stay_total; from datetime import date; print(stay_total(date(2026,1,2), date(2026,1,4),'double',2))"` imprime `210.00`.
2. `pytest -q` pasa en verde la totalidad de la suite (`tests/test_booking.py`) sin variables de entorno y sin servicios externos, cubriendo: conteo de noches, límite 30/31, fechas invertidas o iguales, rechazo de `datetime` y de `str`, tarifas base de las tres habitaciones, recargo viernes/sábado (25 %), no recargo de lunes a jueves, descuento de 7 noches aplicado solo al subtotal de habitación, tasa turística, y validaciones de `room`/`guests` (tipo y rango, incluido `bool`).
3. `stay_total` y `nightly_rate` devuelven `Decimal` (nunca `float`) con exactamente 2 decimales; `nights` devuelve `int` en `[1, 30]`; ninguna función realiza I/O ni muta estado global (importar `booking` no tiene efectos secundarios).
4. `README.md` documenta las tres funciones, el ejemplo numérico verificado y la tabla completa de errores E1–E10, sin prosa de marketing.

## 3. EXECUTABLE ITEMS

### ITEM 1: Foundation — empaquetado PEP 621, configuración de pytest y marcador de paquete
**Goal:** Crear la base de configuración que todos los demás ítems consumen: metadatos del paquete `hotel-booking`, backend de build `setuptools`, resolución de importación (`pythonpath = ["src"]`, `testpaths = ["tests"]`) y el marcador `src/__init__.py` que hace importable el layout `src/`. `pyproject.toml` debe declarar `requires-python = ">=3.10"`, `[build-system] requires = ["setuptools>=68"]`, `[project.optional-dependencies] dev = ["pytest>=8.0", "mypy>=1.8", "black>=24.0"]`, `[tool.setuptools] package-dir = {"" = "src"}` con `py-modules = ["booking"]`, y `[tool.pytest.ini_options]` con `pythonpath`/`testpaths`. Sin dependencias de runtime (solo biblioteca estándar). No se crea `.env` real en ningún ítem.
**Files to create:**
- `pyproject.toml` (create) — PEP 621: nombre `hotel-booking`, versión, `requires-python`, build-system setuptools, `package-dir`, `py-modules`, extra `dev` con pytest/mypy/black, `[tool.pytest.ini_options]` con `pythonpath = ["src"]` y `testpaths = ["tests"]`
- `src/__init__.py` (create) — archivo vacío con docstring de una línea; sin re-exports
**Dependencies:** None
**Validation:** `python -c "import tomllib,pathlib; d=tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print(d['project']['name'], d['tool']['pytest']['ini_options'])"` imprime `hotel-booking {'pythonpath': ['src'], 'testpaths': ['tests']}`; `python -m compileall -q src` no reporta errores.
**Role:** role-dev (backend_developer)

### ITEM 2: Librería núcleo — `nights`, `nightly_rate`, `stay_total` en `src/booking.py` + suite `tests/test_booking.py`
**Goal:** Implementar íntegramente el módulo `src/booking.py` (biblioteca estándar únicamente: `datetime`, `decimal`, `typing`) y su suite pytest `tests/test_booking.py`, sin placeholders y con docstrings en español en cada función pública.
Contenido obligatorio de `src/booking.py`: alias `RoomType = Literal["single","double","suite"]`; constantes `MAX_NIGHTS`, `BASE_RATES`, `WEEKEND_DAYS`, `WEEKEND_SURCHARGE_RATE = Decimal("0.25")`, `TOURIST_TAX_PER_GUEST_NIGHT = Decimal("2.50")`, `ROOM_CAPACITY`, `LONG_STAY_NIGHTS = 7`, `LONG_STAY_DISCOUNT_RATE = Decimal("0.10")`, `CENTS = Decimal("0.01")`; helper privado `_require_plain_date(value, name) -> date` que comprueba `isinstance(value, datetime)` **antes** de `isinstance(value, date)`; helper privado `_require_room(room) -> str` (tipo E7, pertenencia E8); `nights(check_in, check_out) -> int`; `nightly_rate(day, room) -> Decimal`; `stay_total(check_in, check_out, room, guests) -> Decimal`.
Semántica fijada de `stay_total`: (1) obtener `n = nights(check_in, check_out)` —propaga E1–E5—; (2) validar `room` con `_require_room`; (3) validar `guests` con `isinstance(guests, bool)` primero (E9) y luego rango `1..ROOM_CAPACITY[room]` (E10); (4) `subtotal = sum(nightly_rate(check_in + timedelta(days=i), room) for i in range(n))`; (5) si `n >= LONG_STAY_NIGHTS`, `subtotal = subtotal * (Decimal(1) - LONG_STAY_DISCOUNT_RATE)`; (6) `tax = TOURIST_TAX_PER_GUEST_NIGHT * guests * n`; (7) `(subtotal + tax).quantize(CENTS, rounding=ROUND_HALF_UP)`. Dinero siempre desde `str`, nunca desde `float`. Prohibido `pass` aislado, `TODO`, `NotImplementedError`, `logging`, `os`, `sys`, `random` y cualquier paquete de terceros.
Casos que la suite `tests/test_booking.py` debe cubrir (parametrizados donde aplique): 1 noche; 30 noches (permitido); 31 noches (`ValueError` E5); fechas iguales y fechas invertidas (`ValueError` E4); `datetime` en `check_in` y en `check_out` (`TypeError` E2/E3); `str`/`None` en cada slot de fecha (`TypeError` E1/E3); tarifas base de las tres habitaciones en día hábil; recargo del 25 % en viernes y sábado para cada habitación; ausencia de recargo lunes–jueves; `isinstance(resultado, Decimal)` y `as_tuple().exponent == -2`; `room` no `str` (`TypeError` E7), `room` desconocida (`ValueError` E8); `guests` `bool` (`TypeError` E9), `guests` `float`/`str` (`TypeError` E9), `guests = 0` y `guests` por encima de la capacidad de cada habitación (`ValueError` E10); ejemplo canónico `stay_total(2026-01-02, 2026-01-04, "double", 2) == Decimal("210.00")`; estadía de 6 noches sin descuento frente a 7 noches con 10 % aplicado **solo** al subtotal de habitación (la tasa turística no se descuenta); verificación explícita de que la tasa turística total es `2.50 × huéspedes × noches`.
**Files to create:**
- `src/booking.py` (create) — módulo completo: imports, `RoomType`, las nueve constantes, `_require_plain_date`, `_require_room`, `nights`, `nightly_rate`, `stay_total`, con docstrings en español y type hints en todas las funciones
- `tests/test_booking.py` (create) — suite pytest parametrizada que prueba E1–E10, límites de noches, recargo de fin de semana, descuento de 7 noches, tasa turística y ejemplo canónico
**Dependencies:** Item 1
**Validation:** `pytest -q` pasa en verde; `python -c "import sys; sys.path.insert(0,'src'); from booking import stay_total; from datetime import date; assert stay_total(date(2026,1,2), date(2026,1,4), 'double', 2) == __import__('decimal').Decimal('210.00'); print('ok')"` imprime `ok`; `mypy src/booking.py` no reporta errores (herramienta opcional de desarrollo).
**Role:** role-dev (backend_developer)

### ITEM 3: Documentación y verificación de entrega — `README.md` con uso, contrato de errores y ejemplo verificado
**Goal:** Redactar `README.md` breve (en español, sin prosa de marketing) que documente: propósito y alcance de la librería (dependencia para los scripts Python del equipo de revenue; sin servidor, sin interfaz, sin Docker); instalación local (`pip install -e ".[dev]"` o uso directo con `pythonpath = ["src"]`); firma y semántica de `nights`, `nightly_rate` y `stay_total`, incluyendo la regla de que la tarifa corresponde a la noche que empieza en `day`; tabla completa del contrato de errores con columnas condición / excepción / mensaje; ejemplo numérico verificado `2026-01-02 (viernes) → 2026-01-04, double, 2 huéspedes = 100.00 + 100.00 + 10.00 = 210.00`; y comandos de ejecución de la suite (`pytest -q`). Cerrar con la ejecución final de la suite para confirmar la entrega.
**Files to create:**
- `README.md` (create) — alcance, instalación, API de las tres funciones, tabla de errores E1–E10, ejemplo canónico y comandos de prueba
**Dependencies:** Item 1, Item 2
**Validation:** `pytest -q` pasa en verde tras la documentación y cada comando y bloque de código citado en `README.md` se ejecuta literalmente sin errores (incluido el ejemplo que imprime `210.00`).
**Role:** role-dev (backend_developer)