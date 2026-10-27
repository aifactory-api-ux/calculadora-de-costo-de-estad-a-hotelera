# SPEC.md

## 0. SCOPE NOTE — CONTEXT TRUNCATION (READ FIRST)

The authoritative request is a single, small Python library. The requirement text supplied to this SPEC is **truncated mid-sentence** at:

> `Las noches de viernes y sábado tienen rec`

Everything before that point is fully specified and is captured verbatim below. Everything after it is **absent**: the magnitude of the weekend surcharge, and any further functions beyond `nights` and `nightly_rate` (if any existed) are not present in the provided context.

Per the "fail honestly, do not mock" rule, this SPEC:

1. **Pins the mechanism** for the weekend surcharge (where it is applied, in what type, with which rounding) so no design decision is left open.
2. **Does NOT invent** the surcharge magnitude. The constant `WEEKEND_SURCHARGE_RATE` in `src/booking.py` is a required, named, typed constant whose value MUST be supplied by the requirement owner. Any value fabricated by the code generator (e.g. `0.10`, `0.20`, a fixed `+30.00`) is a defect, not a requirement.
3. **Does NOT add** any function that was not literally listed. The library exposes exactly `nights` and `nightly_rate`; any total-cost helper is caller-side composition (`nights(...) * nightly_rate(...)` per night) and is out of scope.

Everything else in this document is derived strictly from the text above that truncation point.

---

## 1. TECHNOLOGY STACK

| Component | Choice | Version | Justification |
|---|---|---|---|
| Language | Python | `>=3.10` (target 3.11) | `datetime.date`, `decimal.Decimal`, `frozenset` literals; no third-party runtime deps required by the request. |
| Runtime dependencies | **None** — standard library only (`datetime`, `decimal`, `typing`) | — | The request asks for a "librería Python pequeña"; nothing in it requires a package. |
| Arbitrary-precision money type | `decimal.Decimal` | stdlib | The request mandates `-> Decimal` for `nightly_rate`, never `float`. |
| Test runner | `pytest` | `>=8.0` | Dev-only dependency; used to prove the explicit `ValueError`/`TypeError` contract. |
| Packaging / config | `pyproject.toml` (PEP 621) | — | Declares the package, `requires-python`, and `pytest` `pythonpath = ["src"]`. |
| Build backend | `setuptools>=68` | — | Minimal pure-Python wheel/sdist; no containerization, no services, no database. |
| Type checking | `mypy` (optional dev tool) | `>=1.8` | Verifies the annotated signatures (`-> int`, `-> Decimal`). |
| Formatting | `black` (optional dev tool) | `>=24.0` | Consistent style; not a functional requirement. |

**Explicitly NOT in scope** (not requested by the goal): HTTP servers, FastAPI/Flask, databases, caches, Docker, Kubernetes, CI pipelines, logging frameworks, tracing, metrics, frontends, message queues, external APIs, persistence of any kind. This is a **pure, stateless, side-effect-free module**.

---

## 2. DATA CONTRACTS

This library has **no ORM models, no Pydantic models, and no persistence schema** — it is a stateless computation module. The data contract is therefore expressed as type aliases, the immutable rate table, and the module-level constants, all of which are part of the public contract and must appear with these **exact names**.

### 2.1 Type aliases (`src/booking.py`)

```python
from datetime import date
from decimal import Decimal
from typing import Final, Literal

RoomType = Literal["single", "double", "suite"]
```

| Name | Kind | Exact type | Notes |
|---|---|---|---|
| `RoomType` | type alias | `Literal["single", "double", "suite"]` | The only three accepted room identifiers. Case-sensitive, lowercase. |
| `check_in` | parameter | `datetime.date` | Must be a plain `date`; `datetime.datetime` is rejected. |
| `check_out` | parameter | `datetime.date` | Must be a plain `date`; `datetime.datetime` is rejected. |
| `day` | parameter | `datetime.date` | The calendar day on which the night **starts**. Must be a plain `date`. |
| `room` | parameter | `str` (narrowed to `RoomType`) | Must be one of the three literals. |
| return of `nights` | value | `int` | `(check_out - check_in).days`, 1..30 inclusive. |
| return of `nightly_rate` | value | `decimal.Decimal` | Quantized to exactly 2 decimal places, `ROUND_HALF_UP`. |

### 2.2 Constants (module-level, exact names, `Final`)

```python
MAX_NIGHTS: Final[int] = 30

BASE_RATES: Final[dict[RoomType, Decimal]] = {
    "single": Decimal("50.00"),
    "double": Decimal("80.00"),
    "suite":  Decimal("150.00"),
}

WEEKEND_DAYS: Final[frozenset[int]] = frozenset({4, 5})   # date.weekday(): Mon=0 … Sun=6

WEEKEND_SURCHARGE_RATE: Final[Decimal] = Decimal("<supplied by requirement owner>")

CENTS: Final[Decimal] = Decimal("0.01")
```

| Constant | Type | Value / contract |
|---|---|---|
| `MAX_NIGHTS` | `int` | `30`. Maximum permitted stay length. Exceeding it → `ValueError`. |
| `BASE_RATES` | `dict[RoomType, Decimal]` | `"single" → 50.00`, `"double" → 80.00`, `"suite" → 150.00`. Values constructed from **strings**, never from `float`. |
| `WEEKEND_DAYS` | `frozenset[int]` | `{4, 5}` = Friday, Saturday (Python's `date.weekday()` numbering, Monday = 0). `date.weekday()` of the night's **starting day** is the lookup key. |
| `WEEKEND_SURCHARGE_RATE` | `Decimal` | A **fraction**, applied as `base * (1 + WEEKEND_SURCHARGE_RATE)`. Example of the *shape* only (not the value): `Decimal("0.20")` would mean +20%. **The magnitude is not present in the provided requirements** — see §0. |
| `CENTS` | `Decimal` | `Decimal("0.01")`, the quantization exponent used by `nightly_rate`. |

### 2.3 Error contract (exhaustive)

| # | Condition | Exception | Message pattern |
|---|---|---|---|
| E1 | `nights`: `check_in` is not a `date` at all (e.g. `str`, `int`, `None`) | `TypeError` | `"check_in must be a datetime.date, got {type}"` |
| E2 | `nights`: `check_in` is a `datetime.datetime` | `TypeError` | `"check_in must be a datetime.date, not datetime.datetime"` |
| E3 | `nights`: `check_out` is not a `date` / is a `datetime.datetime` | `TypeError` | same pattern for `check_out` |
| E4 | `nights`: `check_out <= check_in` (equal **or** earlier) | `ValueError` | `"check_out must be after check_in"` |
| E5 | `nights`: stay longer than 30 nights (`(check_out - check_in).days > 30`) | `ValueError` | `"stay cannot exceed 30 nights"` |
| E6 | `nightly_rate`: `day` is not a `date` / is a `datetime.datetime` | `TypeError` | same pattern for `day` |
| E7 | `nightly_rate`: `room` is not a `str` | `TypeError` | `"room must be a str, got {type}"` |
| E8 | `nightly_rate`: `room` is a `str` but not in `BASE_RATES` | `ValueError` | `"unknown room: {room!r}"` |

**Ordering rule (mandatory):** type validation runs **before** any value/range validation. `nights(datetime(2024,1,1,12), date(2024,1,2))` must raise `TypeError` (E2), never reach the E4/E5 comparisons. Likewise E7 precedes E8.

**`datetime` detection rule (mandatory):** because `datetime.datetime` is a subclass of `datetime.date`, `isinstance(x, date)` alone is insufficient. Validation must test `isinstance(x, datetime.datetime)` **first**:

```python
def _require_plain_date(value: object, name: str) -> date:
    if isinstance(value, datetime):          # checked FIRST — datetime ⊂ date
        raise TypeError(f"{name} must be a datetime.date, not datetime.datetime")
    if not isinstance(value, date):
        raise TypeError(f"{name} must be a datetime.date, got {type(value).__name__}")
    return value
```

---

## 3. API ENDPOINTS

There is **no HTTP layer** in this project (none was requested). The public API surface is the module's exported callables. Each is specified with the same rigor as an HTTP endpoint: inputs, outputs, and failure modes.

### 3.1 `nights(check_in, check_out) -> int`

- **Import:** `from booking import nights`
- **Input:** `check_in: datetime.date`, `check_out: datetime.date` — positional or keyword.
- **Behaviour:**
  1. Validate `check_in` → E1/E2. Validate `check_out` → E3.
  2. `delta = (check_out - check_in).days`.
  3. `delta <= 0` → E4.
  4. `delta > MAX_NIGHTS` (30) → E5.
  5. Return `delta`.
- **Output:** `int` in `[1, 30]`.
- **Errors:** `TypeError` (E1–E3), `ValueError` (E4–E5). No other exception may escape.
- **Boundary examples:**

| `check_in` | `check_out` | Result |
|---|---|---|
| `2024-03-01` | `2024-03-02` | `1` |
| `2024-03-01` | `2024-03-31` | `30` (allowed) |
| `2024-03-01` | `2024-04-01` | `ValueError` (31 > 30) |
| `2024-03-05` | `2024-03-05` | `ValueError` (not strictly after) |
| `2024-03-05` | `2024-03-01` | `ValueError` |
| `datetime(2024,3,1,15,0)` | `2024-03-02` | `TypeError` |
| `"2024-03-01"` | `2024-03-02` | `TypeError` |

### 3.2 `nightly_rate(day, room) -> Decimal`

- **Import:** `from booking import nightly_rate`
- **Input:** `day: datetime.date` (the calendar day the **night begins**), `room: str` ∈ `{"single","double","suite"}`.
- **Behaviour:**
  1. Validate `day` → E6 (plain-date rule, `datetime` rejected).
  2. Validate `room` → E7 (type) then E8 (membership in `BASE_RATES`).
  3. `rate = BASE_RATES[room]`.
  4. If `day.weekday() in WEEKEND_DAYS` → `rate = rate * (Decimal(1) + WEEKEND_SURCHARGE_RATE)`.
  5. Return `rate.quantize(CENTS, rounding=ROUND_HALF_UP)`.
- **Output:** `Decimal` with exactly 2 decimal places. **Never `float`.**
- **Errors:** `TypeError` (E6, E7), `ValueError` (E8).
- **Semantics note (explicit in the request):** the rate belongs to the night that **starts** on `day`. A stay checking in on Friday and out on Sunday bills: Friday-night rate (weekend), Saturday-night rate (weekend). A stay checking in on Sunday bills the Sunday-night rate (base).

### 3.3 Public surface summary

| Export | Signature | Returns |
|---|---|---|
| `nights` | `(check_in: date, check_out: date) -> int` | `int` |
| `nightly_rate` | `(day: date, room: str) -> Decimal` | `Decimal` |
| `MAX_NIGHTS` | `Final[int]` | `30` |
| `BASE_RATES` | `Final[dict[RoomType, Decimal]]` | rate table |
| `WEEKEND_DAYS` | `Final[frozenset[int]]` | `frozenset({4, 5})` |
| `WEEKEND_SURCHARGE_RATE` | `Final[Decimal]` | surcharge fraction (value per §0) |
| `CENTS` | `Final[Decimal]` | `Decimal("0.01")` |
| `RoomType` | type alias | `Literal[...]` |

`_require_plain_date` is private (underscore-prefixed) and MUST NOT be imported by consumers.

---

## 4. FILE STRUCTURE

```text
.
├── pyproject.toml                  # PEP 621 metadata, setuptools backend, pytest pythonpath=["src"]
├── README.md                       # 15-line usage + the error contract table (no marketing prose)
├── src/
│   ├── __init__.py                 # empty marker making src/ importable; no re-exports
│   └── booking.py                  # ENTIRE library: nights, nightly_rate, constants, _require_plain_date
└── tests/
    └── test_booking.py             # pytest suite proving every explicit rule E1–E8 + weekend boundary
```

| File | One-line description |
|---|---|
| `pyproject.toml` | Declares `name = "hotel-booking"`, `requires-python = ">=3.10"`, `[tool.pytest.ini_options] pythonpath = ["src"]`, `testpaths = ["tests"]`, dev extra `pytest>=8.0`. |
| `README.md` | Documents `nights` and `nightly_rate`, the two examples, and the E1–E8 error table. |
| `src/__init__.py` | Empty file; exists only so `src` is a package on `sys.path` during tests. |
| `src/booking.py` | The sole implementation file: imports, `RoomType`, the five constants, `_require_plain_date`, `nights`, `nightly_rate`. |
| `tests/test_booking.py` | Parameterized tests: night counting, 30/31-night boundary, reversed/equal dates, `datetime` rejection, unknown room, base rates for each room, Friday/Saturday surcharge application, Monday–Thursday non-application, `Decimal` return type. |

**No port table** — this project has no services and binds no sockets.

**No shared modules** — a single module, no cross-service imports.

**No infrastructure files** — containerization, `.env`, Dockerfiles, and compose files were not requested and are therefore absent.

---

## 5. ENVIRONMENT VARIABLES

**None.** The library reads no environment variables, opens no files, performs no network I/O, and holds no global mutable state. This is a hard constraint: importing `booking` must be side-effect free.

Because nothing is configurable via the environment, the tunable values are **module-level constants** (see §2.2). They are listed here so their names, types, and defaults are unambiguous:

| Name | Type | Default | Description |
|---|---|---|---|
| `MAX_NIGHTS` | `int` | `30` | Maximum stay length accepted by `nights`; longer stays raise `ValueError`. |
| `BASE_RATES["single"]` | `Decimal` | `Decimal("50.00")` | Weekday base rate, single room. |
| `BASE_RATES["double"]` | `Decimal` | `Decimal("80.00")` | Weekday base rate, double room. |
| `BASE_RATES["suite"]` | `Decimal` | `Decimal("150.00")` | Weekday base rate, suite. |
| `WEEKEND_DAYS` | `frozenset[int]` | `frozenset({4, 5})` | `date.weekday()` values treated as weekend nights (Friday, Saturday). |
| `WEEKEND_SURCHARGE_RATE` | `Decimal` | *supplied per §0* | Fraction added to the base rate on weekend nights. |
| `CENTS` | `Decimal` | `Decimal("0.01")` | Quantization exponent for `nightly_rate`. |

The test suite configures no environment; `pytest` must pass with an empty environment.

---

## 6. IMPORT CONTRACTS

`src/booking.py` is the single foundation file. Its exports, consumed by tests and by any downstream caller:

```python
from booking import (
    nights,                   # (check_in: date, check_out: date) -> int
    nightly_rate,             # (day: date, room: str) -> Decimal
    MAX_NIGHTS,               # Final[int] == 30
    BASE_RATES,               # Final[dict[RoomType, Decimal]]
    WEEKEND_DAYS,             # Final[frozenset[int]] == frozenset({4, 5})
    WEEKEND_SURCHARGE_RATE,   # Final[Decimal]
    CENTS,                    # Final[Decimal] == Decimal("0.01")
    RoomType,                 # Literal["single", "double", "suite"]
)
```

Internal dependency graph (must not grow):

```python
# src/booking.py
import datetime                 # for datetime.datetime detection + date
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Final, Literal
```

```python
# tests/test_booking.py
import datetime
from decimal import Decimal
import pytest
from booking import nightly_rate, nights, BASE_RATES, MAX_NIGHTS, WEEKEND_DAYS
```

**Forbidden imports** in `src/booking.py`: `float`-producing helpers, `requests`, `logging`, `os`, `sys` mutation, `time`, `random`, any third-party package. The module must remain importable with an empty `site-packages`.

---

## 7. FRONTEND STATE & COMPONENT CONTRACTS

**Not applicable.** The goal specifies a Python library only; no UI framework, no components, no client state, and no HTTP surface were requested. Adding a frontend would be out-of-scope expansion, so no state primitives, hooks, composables, services, or component props are defined.

---

## 8. FILE EXTENSION CONVENTION

- **Language:** Python 3.10+ — the project is a **Python** project, not JavaScript/TypeScript.
- **Source files:** `.py` only (`src/booking.py`, `src/__init__.py`, `tests/test_booking.py`).
- **No `.jsx`, `.tsx`, `.js`, or `.ts` files exist anywhere.** There is no `index.html`, no bundler, and therefore **no `<script src>` entry point**.
- **Module import path:** `booking` (resolved because `pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["src"]`, and because `pip install -e .` exposes `booking` from the `src/` layout).
- **Config file:** `pyproject.toml` (TOML), not `setup.py`, not `package.json`.

---

## 9. DESIGN TOKENS

**Omitted by rule.** No UI/UX Design Implementation Contract was supplied with the project context, so `frontend/src/styles/tokens.ts` does not exist in this project and no color, typography, spacing, radius, or shadow values may be invented.

---

## 10. FUNCTIONAL REQUIREMENTS COVERAGE

| # | Requirement (verbatim from goal) | Implementation | Files |
|---|---|---|---|
| R1 | "una librería Python pequeña … en `src/booking.py`" | Single module, stdlib only, no side effects on import | `src/booking.py`, `src/__init__.py`, `pyproject.toml` |
| R2 | `nights(check_in, check_out) -> int` | `def nights(check_in: date, check_out: date) -> int` returns `(check_out - check_in).days` | `src/booking.py` |
| R3 | "noches entre ambas fechas (`datetime.date`)" | Difference of two `date` objects yields whole calendar days — no timezone/clock arithmetic | `src/booking.py::nights` |
| R4 | "`check_out` debe ser posterior a `check_in`" — otherwise `ValueError` | `delta <= 0` → `raise ValueError("check_out must be after check_in")` (E4); covers equal and reversed dates | `src/booking.py::nights`, `tests/test_booking.py` |
| R5 | "la estadía máxima es 30 noches (si no, `ValueError`)" | `delta > MAX_NIGHTS` where `MAX_NIGHTS = 30` → `raise ValueError("stay cannot exceed 30 nights")` (E5). 30 passes, 31 fails | `src/booking.py::nights`, `src/booking.py::MAX_NIGHTS`, `tests/test_booking.py` |
| R6 | "Si alguna no es `date`, o es `datetime`, `TypeError`" | `_require_plain_date` checks `isinstance(v, datetime)` **before** `isinstance(v, date)`; applied to both parameters (E1–E3) | `src/booking.py::_require_plain_date`, `tests/test_booking.py` |
| R7 | `nightly_rate(day, room) -> Decimal` | `def nightly_rate(day: date, room: str) -> Decimal`, returns quantized `Decimal` | `src/booking.py` |
| R8 | "tarifa de la noche que **empieza** en `day`" | `day.weekday()` and `day` itself are the *starting* day of the night; weekend status is derived from `day`, not from the following morning | `src/booking.py::nightly_rate` |
| R9 | Base `"single" 50.00` | `BASE_RATES["single"] = Decimal("50.00")` (string construction — no float drift) | `src/booking.py::BASE_RATES`, `tests/test_booking.py` |
| R10 | Base `"double" 80.00` | `BASE_RATES["double"] = Decimal("80.00")` | `src/booking.py::BASE_RATES`, `tests/test_booking.py` |
| R11 | Base `"suite" 150.00` | `BASE_RATES["suite"] = Decimal("150.00")` | `src/booking.py::BASE_RATES`, `tests/test_booking.py` |
| R12 | "Las noches de viernes y sábado tienen rec[argo]" | `if day.weekday() in WEEKEND_DAYS: rate *= (Decimal(1) + WEEKEND_SURCHARGE_RATE)`. `WEEKEND_DAYS = frozenset({4, 5})` = Fri/Sat. **Magnitude not present in context — see §0; the mechanism is fixed, the value must be supplied and must not be fabricated.** | `src/booking.py::nightly_rate`, `src/booking.py::WEEKEND_DAYS`, `src/booking.py::WEEKEND_SURCHARGE_RATE` |
| R13 | Monetary result must be `Decimal` (per the declared return type) | No `float` ever enters the computation; `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` guarantees exactly 2 dp | `src/booking.py::nightly_rate`, `src/booking.py::CENTS` |
| R14 | Room identifier must be one of the three documented values | `isinstance(room, str)` → `TypeError` (E7); not in `BASE_RATES` → `ValueError` (E8). *Derived rule — error type unspecified by the goal, chosen for consistency with the explicit `ValueError`/`TypeError` split.* | `src/booking.py::nightly_rate`, `tests/test_booking.py` |
| R15 | Deterministic, dependency-free computation | Pure functions; no I/O, no globals mutated, no clock/random reads | `src/booking.py` |
| R16 | Explicit error behaviour is testable | Parameterized `pytest` tests: 1-night, 30-night, 31-night, equal dates, reversed dates, `datetime` in each slot, `str`/`None` inputs, all three rooms, Fri/Sat vs Mon–Thu, `isinstance(result, Decimal)` | `tests/test_booking.py`, `pyproject.toml` |

### 10.1 Constraints and honest gaps

- **GAP-1 (blocking for R12):** the surcharge magnitude is missing from the supplied context (text cut at `"tienen rec"`). The code generator MUST emit `WEEKEND_SURCHARGE_RATE` as a `Final[Decimal]` and MUST NOT choose a number on its own; the value is an input from the requirement owner. No test may assert a specific surcharged amount until that value is supplied; tests assert the *mechanism* (result > base rate on `weekday() in {4,5}`; result == base rate otherwise) without pinning the magnitude.
- **GAP-2:** no total-cost function was listed; composition is caller-side. The library deliberately exposes only `nights` and `nightly_rate`.
- **GAP-3:** no persistence, currency, tax, occupancy, or cancellation rules appear anywhere in the provided text and are therefore out of scope. Implementing them would be scope creep.
- **GAP-4:** no localization/i18n requirement; exception messages are fixed English strings exactly as in §2.3 so tests can assert on them.