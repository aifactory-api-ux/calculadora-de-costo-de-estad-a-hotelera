"""Cálculo de costos de estadías hoteleras.

Librería pura, sin estado ni efectos secundarios: expone tres funciones
públicas que operan exclusivamente con ``datetime.date`` y ``decimal.Decimal``
para resolver la tarifa de una noche, la cantidad de noches de una estadía y
el costo total de una estadía.

Reglas de negocio implementadas:

* La tarifa corresponde a la noche que **empieza** en el día indicado: el
  estado de fin de semana se deriva de ``day.weekday()`` y no del día en que
  termina la noche.
* Las noches de fin de semana (viernes y sábado) llevan un recargo del 25 %
  sobre la tarifa base.
* Los importes se construyen siempre desde cadenas y se cuantizan a dos
  decimales con ``ROUND_HALF_UP``: ningún ``float`` interviene en el cálculo.

El módulo no lee variables de entorno, no abre archivos, no realiza I/O de red
y no depende de paquetes de terceros: solo usa la biblioteca estándar.
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal, cast

__all__ = [
    "BASE_RATES",
    "CENTS",
    "LONG_STAY_DISCOUNT_RATE",
    "LONG_STAY_NIGHTS",
    "MAX_NIGHTS",
    "ROOM_CAPACITY",
    "TOURIST_TAX_PER_GUEST_NIGHT",
    "WEEKEND_DAYS",
    "WEEKEND_SURCHARGE_RATE",
    "RoomType",
    "nightly_rate",
    "nights",
    "stay_total",
]

#: Identificadores de habitación admitidos (minúsculas, sensible a mayúsculas).
RoomType = Literal["single", "double", "suite"]

#: Cantidad máxima de noches admitida en una estadía.
#:
#: La estadía máxima es de 30 noches: una estadía de exactamente ``MAX_NIGHTS``
#: noches se admite y una de ``MAX_NIGHTS + 1`` noches o más se rechaza con
#: ``ValueError`` (error E5, mensaje ``"stay cannot exceed 30 nights"``).
MAX_NIGHTS: Final[int] = 30

#: Tarifa base por tipo de habitación, sin recargo de fin de semana:
#:
#: * ``BASE_RATES["single"] = Decimal("50.00")``
#: * ``BASE_RATES["double"] = Decimal("80.00")``
#: * ``BASE_RATES["suite"] = Decimal("150.00")``
#:
#: Los importes se construyen desde cadenas y nunca desde literales binarios,
#: para que las sumas posteriores no arrastren error de representación.
BASE_RATES: Final[dict[RoomType, Decimal]] = {
    "single": Decimal("50.00"),
    "double": Decimal("80.00"),
    "suite": Decimal("150.00"),
}

#: Noches con recargo, según ``date.weekday()`` (lunes = 0 … domingo = 6):
#: 4 = viernes y 5 = sábado. La noche se identifica por el día en que
#: **empieza**, no por el día en que termina.
WEEKEND_DAYS: Final[frozenset[int]] = frozenset({4, 5})

#: Recargo aplicado a las noches de fin de semana: fracción sobre la tarifa
#: base (25 % → la tarifa se multiplica por ``1 + WEEKEND_SURCHARGE_RATE``).
WEEKEND_SURCHARGE_RATE: Final[Decimal] = Decimal("0.25")

#: Tasa turística por huésped y noche.
TOURIST_TAX_PER_GUEST_NIGHT: Final[Decimal] = Decimal("2.50")

#: Capacidad máxima de huéspedes por tipo de habitación.
ROOM_CAPACITY: Final[dict[RoomType, int]] = {
    "single": 1,
    "double": 2,
    "suite": 4,
}

#: Umbral de noches a partir del cual se aplica el descuento por estadía larga.
LONG_STAY_NIGHTS: Final[int] = 7

#: Descuento por estadía larga (fracción sobre el subtotal de habitación).
LONG_STAY_DISCOUNT_RATE: Final[Decimal] = Decimal("0.10")

#: Exponente de cuantización de los importes monetarios.
CENTS: Final[Decimal] = Decimal("0.01")


def _require_plain_date(value: object, name: str) -> date:
    """Valida que un parámetro sea un ``datetime.date`` que no sea ``datetime``.

    ``datetime.datetime`` es subclase de ``datetime.date``, por lo que la
    comprobación del ``datetime`` debe ejecutarse antes de la del ``date``.

    Args:
        value: Valor a validar.
        name: Nombre del parámetro, usado en el mensaje de error.

    Returns:
        El mismo valor, ya validado como ``datetime.date``.

    Raises:
        TypeError: Si el valor no es un ``datetime.date`` plano.
    """
    if isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime.date, not datetime.datetime")
    if not isinstance(value, date):
        raise TypeError(f"{name} must be a datetime.date, got {type(value).__name__}")
    return value


def _require_room(room: object) -> RoomType:
    """Valida el identificador de habitación: tipo y pertenencia a la tabla.

    El tipo se comprueba antes que el valor: un identificador que no es
    ``str`` produce ``TypeError`` (E7) y un ``str`` que no corresponde a una de
    las tres habitaciones documentadas produce ``ValueError`` (E8).

    Args:
        room: Identificador de habitación a validar.

    Returns:
        El mismo identificador, restringido a ``RoomType``.

    Raises:
        TypeError: Si el identificador no es un ``str``.
        ValueError: Si el identificador no corresponde a una habitación conocida.
    """
    if not isinstance(room, str):
        raise TypeError(f"room must be a str, got {type(room).__name__}")
    if room not in BASE_RATES:
        raise ValueError(f"unknown room: {room!r}")
    return cast(RoomType, room)


def _calendar_days_between(start: date, end: date) -> int:
    """Calcula los días calendario completos entre dos fechas.

    La diferencia entre dos ``datetime.date`` es un ``timedelta`` exacto: como
    los operandos no llevan hora ni zona horaria, el resultado son días
    calendario enteros, sin horas ni minutos residuales. El conteo depende
    únicamente del par de fechas: no intervienen el reloj, la hora del día ni
    el huso horario, y equivale a la diferencia de los números ordinales del
    calendario gregoriano proleptico (``end.toordinal() - start.toordinal()``).

    Args:
        start: Fecha inicial.
        end: Fecha final.

    Returns:
        La cantidad de días calendario entre ambas fechas; es negativa si
        ``end`` es anterior a ``start``.
    """
    return (end - start).days


def nights(check_in: date, check_out: date) -> int:
    """Calcula la cantidad de noches de una estadía.

    La cantidad de noches es la diferencia entre ambas fechas expresada en días
    calendario completos: ``(check_out - check_in).days``, calculada en
    ``_calendar_days_between``. Como los operandos son ``datetime.date`` —sin
    hora ni zona horaria— la resta produce un ``timedelta`` de días exactos: el
    resultado no depende del reloj, de la hora del día ni de conversiones de
    huso horario, solo de las dos fechas.

    La estadía máxima es de ``MAX_NIGHTS`` noches (30): una estadía de 30
    noches se admite y una de 31 noches o más se rechaza con ``ValueError``.

    Args:
        check_in: Fecha de ingreso; debe ser un ``datetime.date`` plano.
        check_out: Fecha de egreso; debe ser un ``datetime.date`` plano y
            estrictamente posterior a ``check_in``.

    Returns:
        La cantidad de noches de la estadía, entre 1 y ``MAX_NIGHTS``.

    Raises:
        TypeError: Si alguna de las fechas no es un ``datetime.date`` plano.
        ValueError: Si ``check_out`` no es posterior a ``check_in``
            (``"check_out must be after check_in"``) o si la estadía supera
            ``MAX_NIGHTS`` noches (``"stay cannot exceed 30 nights"``).
    """
    check_in = _require_plain_date(check_in, "check_in")
    check_out = _require_plain_date(check_out, "check_out")

    # R3: el conteo sale de la diferencia entre las dos fechas, es decir de
    # días calendario completos; el cálculo vive en ``_calendar_days_between``
    # para que la regla quede en un único punto de la librería.
    delta = _calendar_days_between(check_in, check_out)
    # E4: ``check_out`` debe ser estrictamente posterior a ``check_in``. La
    # comparación con cero cubre las fechas iguales y las invertidas; se
    # comprueba antes que el límite de duración para que un rango inválido
    # siempre se reporte con el mismo error.
    if delta <= 0:
        raise ValueError("check_out must be after check_in")
    # E5: la estadía máxima es de 30 noches (``MAX_NIGHTS``). El límite se
    # compara contra la constante para que el valor y el mensaje de error no
    # puedan divergir; el texto del mensaje es parte del contrato de errores y
    # por eso se escribe de forma literal. La prueba
    # ``test_nights_el_mensaje_del_maximo_coincide_con_la_constante`` verifica
    # que el mensaje sigue nombrando el valor vigente de ``MAX_NIGHTS``.
    if delta > MAX_NIGHTS:
        raise ValueError("stay cannot exceed 30 nights")
    return delta


def nightly_rate(day: date, room: str) -> Decimal:
    """Devuelve la tarifa de la noche que comienza en ``day``.

    La tarifa corresponde a la noche que **empieza** en ``day``: el estado de
    fin de semana se decide con ``day.weekday()`` —no con el día siguiente—,
    de modo que la noche del viernes se cobra con recargo aunque termine el
    sábado, y la noche del domingo se cobra a tarifa base aunque termine el
    lunes.

    El importe parte siempre de la tarifa base de ``BASE_RATES``; para las
    noches de fin de semana se aplica el recargo como fracción
    (``base * (1 + WEEKEND_SURCHARGE_RATE)``) y el resultado se cuantiza a dos
    decimales con ``ROUND_HALF_UP``. El tipo de retorno es siempre ``Decimal``.

    Args:
        day: Día en el que comienza la noche; debe ser un ``datetime.date`` plano.
        room: Identificador de habitación: ``"single"``, ``"double"`` o ``"suite"``.

    Returns:
        La tarifa de la noche como ``Decimal`` con exactamente dos decimales.

    Raises:
        TypeError: Si ``day`` no es un ``datetime.date`` plano (E6) o si
            ``room`` no es un ``str`` (E7).
        ValueError: Si ``room`` no corresponde a una de las tres habitaciones
            documentadas (E8).
    """
    # E6: ``day`` debe ser una fecha plana; ``_require_plain_date`` rechaza
    # también los ``datetime.datetime``.
    day = _require_plain_date(day, "day")
    # E7/E8: ``room`` debe ser un ``str`` y una de las tres habitaciones
    # documentadas; la validación vive en ``_require_room``.
    room_type = _require_room(room)

    rate = BASE_RATES[room_type]
    # La noche se identifica por el día en que **empieza**: el recargo se
    # decide con ``day.weekday()`` y no con el día en que la noche termina.
    if day.weekday() in WEEKEND_DAYS:
        rate = rate * (Decimal(1) + WEEKEND_SURCHARGE_RATE)
    return rate.quantize(CENTS, rounding=ROUND_HALF_UP)


def stay_total(check_in: date, check_out: date, room: str, guests: int) -> Decimal:
    """Calcula el costo total de una estadía.

    El total es el subtotal de habitación (la suma de la tarifa de cada noche,
    desde ``check_in`` hasta el día previo a ``check_out``) más la tasa
    turística por huésped y noche. Las estadías de ``LONG_STAY_NIGHTS`` noches o
    más aplican ``LONG_STAY_DISCOUNT_RATE`` únicamente sobre el subtotal de
    habitación: la tasa turística se suma después y no recibe descuento.

    Args:
        check_in: Fecha de ingreso; debe ser un ``datetime.date`` plano.
        check_out: Fecha de egreso; debe ser un ``datetime.date`` plano y
            estrictamente posterior a ``check_in``.
        room: Identificador de habitación: ``"single"``, ``"double"`` o ``"suite"``.
        guests: Cantidad de huéspedes; debe ser un ``int`` entre 1 y la
            capacidad de la habitación.

    Returns:
        El costo total de la estadía como ``Decimal`` con exactamente dos
        decimales.

    Raises:
        TypeError: Si alguna fecha no es un ``datetime.date`` plano o si
            ``guests`` no es un ``int``.
        ValueError: Si el rango de fechas es inválido, si la habitación es
            desconocida o si ``guests`` excede el rango admitido.
    """
    total_nights = nights(check_in, check_out)
    room_type = _require_room(room)

    # ``bool`` es subclase de ``int``: se descarta antes de validar el tipo.
    if isinstance(guests, bool) or not isinstance(guests, int):
        raise TypeError(f"guests must be an int, got {type(guests).__name__}")

    capacity = ROOM_CAPACITY[room_type]
    if not 1 <= guests <= capacity:
        raise ValueError(f"guests must be between 1 and {capacity} for room {room_type!r}")

    room_subtotal = sum(
        (
            nightly_rate(check_in + timedelta(days=offset), room_type)
            for offset in range(total_nights)
        ),
        Decimal("0.00"),
    )
    if total_nights >= LONG_STAY_NIGHTS:
        room_subtotal = room_subtotal * (Decimal(1) - LONG_STAY_DISCOUNT_RATE)

    tourist_tax = TOURIST_TAX_PER_GUEST_NIGHT * guests * total_nights
    return (room_subtotal + tourist_tax).quantize(CENTS, rounding=ROUND_HALF_UP)
