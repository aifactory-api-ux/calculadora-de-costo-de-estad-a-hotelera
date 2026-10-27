# hotel-booking

Librería Python para calcular el costo de estadías hoteleras. Expone tres funciones
públicas —`nights`, `nightly_rate` y `stay_total`— que operan con `datetime.date` y
`decimal.Decimal`.

## Alcance

- Uso previsto: dependencia en los scripts Python del equipo de revenue.
- Solo biblioteca estándar (`datetime`, `decimal`, `typing`); sin dependencias de runtime.
- Sin servidor, sin interfaz, sin base de datos ni servicios externos. La librería no
  requiere Docker: el `docker-compose.yml` del repositorio solo ejecuta la suite de
  pruebas en un contenedor aislado y es opcional.
- Módulo puro: sin I/O, sin variables de entorno y sin estado global mutable; importar
  `booking` no produce efectos secundarios.

## Requisitos

- Python >= 3.10.
- `pytest` solo para el desarrollo.

## Instalación

Desde la raíz del proyecto:

```bash
pip install -e ".[dev]"
```

El extra `dev` instala `pytest`, `mypy` y `black`. La instalación expone el módulo
`booking` (layout `src/`) para `import booking`.

Alternativa sin instalar: usar el `pythonpath` de la configuración de pytest, que ya
apunta a `src/`.

```bash
PYTHONPATH=src pytest -q
```

## Uso rápido

Ejemplo verificado: del `2026-01-02` (viernes) al `2026-01-04`, habitación `double`,
2 huéspedes → `100.00 + 100.00 + 10.00 = 210.00`.

```python
import sys

sys.path.insert(0, "src")  # solo si la librería no está instalada

from datetime import date

from booking import nightly_rate, nights, stay_total

noches = nights(date(2026, 1, 2), date(2026, 1, 4))
viernes = nightly_rate(date(2026, 1, 2), "double")
sabado = nightly_rate(date(2026, 1, 3), "double")
total = stay_total(date(2026, 1, 2), date(2026, 1, 4), "double", 2)

print(noches)  # 2
print(viernes)  # 100.00
print(sabado)  # 100.00
print(total)  # 210.00
```

## API

### `nights(check_in: date, check_out: date) -> int`

Cantidad de noches de una estadía: la diferencia entre ambas fechas en días calendario
completos, `(check_out - check_in).days` (equivalente a la diferencia de sus números
ordinales). No interviene el reloj, la hora del día ni el huso horario: el resultado depende
solo de las dos fechas.

- `check_out` debe ser estrictamente posterior a `check_in`.
- La estadía máxima es de 30 noches (`MAX_NIGHTS`); 30 se admite, 31 se rechaza.
- Devuelve un `int` en el rango `[1, 30]`.
- Las fechas deben ser `datetime.date` planos: un `datetime.datetime` se rechaza.

### `nightly_rate(day: date, room: str) -> Decimal`

Tarifa de la noche que **empieza** en `day`.

- El estado de fin de semana se deriva de `day.weekday()` (lunes = 0 … domingo = 6): la
  noche que empieza el viernes se cobra con recargo aunque termine el sábado; la noche que
  empieza el domingo se cobra a tarifa base.
- Recargo de fin de semana: `base * (1 + WEEKEND_SURCHARGE_RATE)`, con
  `WEEKEND_SURCHARGE_RATE = 0.25` (25 %) para viernes y sábado.
- `room` debe ser `"single"`, `"double"` o `"suite"` (minúsculas, sensible a mayúsculas).
- Devuelve un `Decimal` con exactamente dos decimales, redondeado con `ROUND_HALF_UP`.

### `stay_total(check_in: date, check_out: date, room: str, guests: int) -> Decimal`

Costo total de una estadía.

- Subtotal de habitación: suma de `nightly_rate` de cada noche, desde `check_in` hasta el
  día previo a `check_out`.
- Tasa turística: `TOURIST_TAX_PER_GUEST_NIGHT` (2.50) por huésped y por noche.
- Descuento por estadía larga: desde 7 noches (`LONG_STAY_NIGHTS`) se aplica un 10 %
  (`LONG_STAY_DISCOUNT_RATE`) **solo sobre el subtotal de habitación**; la tasa turística se
  suma después y no recibe descuento.
- `guests` debe ser un `int` entre 1 y la capacidad de la habitación (`single` 1, `double`
  2, `suite` 4). Un `bool` se rechaza.
- Devuelve un `Decimal` con exactamente dos decimales, redondeado con `ROUND_HALF_UP`.

## Parámetros de negocio

Todos son constantes de módulo (`Final`), importables desde `booking`.

| Constante | Tipo | Valor | Descripción |
|---|---|---|---|
| `MAX_NIGHTS` | `int` | `30` | Estadía máxima admitida. |
| `BASE_RATES` | `dict[str, Decimal]` | `single` 50.00, `double` 80.00, `suite` 150.00 | Tarifa base por habitación. |
| `WEEKEND_DAYS` | `frozenset[int]` | `{4, 5}` | Valores de `date.weekday()` con recargo (viernes, sábado). |
| `WEEKEND_SURCHARGE_RATE` | `Decimal` | `0.25` | Recargo de fin de semana (fracción sobre la base). |
| `TOURIST_TAX_PER_GUEST_NIGHT` | `Decimal` | `2.50` | Tasa turística por huésped y noche. |
| `ROOM_CAPACITY` | `dict[str, int]` | `single` 1, `double` 2, `suite` 4 | Capacidad máxima de huéspedes. |
| `LONG_STAY_NIGHTS` | `int` | `7` | Umbral de noches para el descuento por estadía larga. |
| `LONG_STAY_DISCOUNT_RATE` | `Decimal` | `0.10` | Descuento por estadía larga (sobre el subtotal de habitación). |
| `CENTS` | `Decimal` | `0.01` | Exponente de cuantización de los importes. |

## Contrato de errores

La validación de tipo se ejecuta **antes** de la de valor o rango. Ninguna otra excepción
escapa de las funciones públicas.

| # | Condición | Excepción | Mensaje |
|---|---|---|---|
| E1 | `nights`: `check_in` no es un `date` | `TypeError` | `check_in must be a datetime.date, got {type}` |
| E2 | `nights`: `check_in` es un `datetime.datetime` | `TypeError` | `check_in must be a datetime.date, not datetime.datetime` |
| E3 | `nights`: `check_out` no es un `date` o es un `datetime.datetime` | `TypeError` | `check_out must be a datetime.date, got {type}` / `check_out must be a datetime.date, not datetime.datetime` |
| E4 | `nights`: `check_out <= check_in` (iguales o invertidas) | `ValueError` | `check_out must be after check_in` |
| E5 | `nights`: estadía de más de 30 noches | `ValueError` | `stay cannot exceed 30 nights` |
| E6 | `nightly_rate`: `day` no es un `date` o es un `datetime.datetime` | `TypeError` | `day must be a datetime.date, got {type}` / `day must be a datetime.date, not datetime.datetime` |
| E7 | `nightly_rate`: `room` no es un `str` | `TypeError` | `room must be a str, got {type}` |
| E8 | `nightly_rate`: `room` no es una habitación conocida | `ValueError` | `unknown room: {room!r}` |
| E9 | `stay_total`: `guests` no es un `int` (incluido `bool`) | `TypeError` | `guests must be an int, got {type}` |
| E10 | `stay_total`: `guests` fuera de `[1, capacidad]` | `ValueError` | `guests must be between 1 and {capacidad} for room {room!r}` |

`stay_total` propaga los errores de fechas (E1–E5), de habitación (E7–E8) y de huéspedes
(E9–E10), en ese orden de validación.

## Pruebas

```bash
pytest -q
```

La suite (`tests/test_booking.py`) cubre el conteo de noches y sus límites, las tarifas base
de las tres habitaciones, el recargo de fin de semana y su ausencia de lunes a jueves, la
tasa turística, el descuento de 7 noches aplicado solo al subtotal de habitación y el
contrato de errores E1–E10. No requiere variables de entorno ni servicios externos.

Atajo de verificación (ejemplo numérico + suite completa):

```bash
./run.sh
```

Si `pytest` no está disponible, `run.sh` instala el extra de desarrollo `dev` antes de
correr la suite. La misma suite puede ejecutarse en un contenedor aislado, sin publicar
puertos ni levantar dependencias externas:

```bash
docker compose run --rm tests
```
