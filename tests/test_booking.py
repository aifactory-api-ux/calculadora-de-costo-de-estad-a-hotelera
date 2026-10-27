"""Suite de pruebas de la librería de cálculo de costos de estadías hoteleras.

Las pruebas cubren el conteo de noches y sus límites, las tarifas base, el
recargo de fin de semana, la tasa turística, el descuento por estadía larga y
el contrato de errores E1–E10.
"""

import ast
import inspect
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

import booking
from booking import (
    BASE_RATES,
    CENTS,
    LONG_STAY_DISCOUNT_RATE,
    LONG_STAY_NIGHTS,
    MAX_NIGHTS,
    ROOM_CAPACITY,
    TOURIST_TAX_PER_GUEST_NIGHT,
    WEEKEND_DAYS,
    WEEKEND_SURCHARGE_RATE,
    nightly_rate,
    nights,
    stay_total,
)

# Fechas de referencia de enero de 2026:
# 2026-01-02 es viernes, 2026-01-03 es sábado y 2026-01-05 es lunes.
FRIDAY = date(2026, 1, 2)
SATURDAY = date(2026, 1, 3)
MONDAY = date(2026, 1, 5)


# ---------------------------------------------------------------------------
# nights
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("check_in", "check_out", "expected"),
    [
        (date(2026, 1, 5), date(2026, 1, 6), 1),
        (date(2026, 1, 5), date(2026, 1, 7), 2),
        (date(2026, 1, 5), date(2026, 1, 12), 7),
        (date(2026, 1, 2), date(2026, 1, 4), 2),
        (date(2026, 2, 1), date(2026, 3, 3), 30),
    ],
)
def test_nights_cuenta_las_noches(check_in, check_out, expected):
    assert nights(check_in, check_out) == expected


def test_nights_devuelve_un_entero():
    resultado = nights(date(2026, 1, 5), date(2026, 1, 8))

    assert isinstance(resultado, int)
    assert not isinstance(resultado, bool)


def test_nights_admite_el_maximo_de_noches():
    check_in = date(2026, 1, 1)
    check_out = check_in + timedelta(days=MAX_NIGHTS)

    assert MAX_NIGHTS == 30
    assert nights(check_in, check_out) == MAX_NIGHTS


def test_nights_rechaza_estadias_mas_largas_del_maximo():
    check_in = date(2026, 1, 1)
    check_out = check_in + timedelta(days=MAX_NIGHTS + 1)

    with pytest.raises(ValueError, match="stay cannot exceed 30 nights"):
        nights(check_in, check_out)


def test_max_nights_es_una_constante_de_modulo():
    assert MAX_NIGHTS == 30
    assert "MAX_NIGHTS" in booking.__all__


@pytest.mark.parametrize("noches", [31, 32, 60, 365])
def test_nights_rechaza_toda_estadia_que_supere_el_maximo(noches):
    check_in = date(2026, 1, 1)
    check_out = check_in + timedelta(days=noches)

    with pytest.raises(ValueError) as excinfo:
        nights(check_in, check_out)

    assert str(excinfo.value) == "stay cannot exceed 30 nights"


def test_nights_el_mensaje_del_maximo_coincide_con_la_constante():
    # El mensaje de E5 es texto fijo del contrato: debe seguir nombrando el
    # valor vigente de ``MAX_NIGHTS``.
    check_in = date(2026, 1, 1)
    check_out = check_in + timedelta(days=MAX_NIGHTS + 1)

    with pytest.raises(ValueError) as excinfo:
        nights(check_in, check_out)

    assert str(MAX_NIGHTS) in str(excinfo.value)


def test_nights_la_estadia_maxima_es_de_30_noches():
    # R5: "la estadía máxima es 30 noches (si no, ValueError)". El valor de la
    # constante y el límite efectivo coinciden: 30 noches se admiten y 31 se
    # rechazan.
    check_in = date(2026, 1, 1)

    assert MAX_NIGHTS == 30
    assert nights(check_in, check_in + timedelta(days=MAX_NIGHTS)) == 30

    with pytest.raises(ValueError) as excinfo:
        nights(check_in, check_in + timedelta(days=MAX_NIGHTS + 1))

    assert str(excinfo.value) == "stay cannot exceed 30 nights"


def test_nights_el_limite_se_compara_contra_la_constante_max_nights():
    # La regla del máximo de noches se aplica comparando contra ``MAX_NIGHTS``,
    # de modo que el límite efectivo y la constante no puedan divergir.
    fuente = inspect.getsource(booking.nights)

    assert "delta > MAX_NIGHTS" in fuente
    assert "stay cannot exceed 30 nights" in fuente


@pytest.mark.parametrize("noches", [1, 15, MAX_NIGHTS])
def test_nights_devuelve_un_valor_dentro_del_rango_admitido(noches):
    check_in = date(2026, 1, 1)

    resultado = nights(check_in, check_in + timedelta(days=noches))

    assert 1 <= resultado <= MAX_NIGHTS


def test_nights_limite_de_30_noches_segun_los_ejemplos_de_la_especificacion():
    check_in = date(2024, 3, 1)

    assert nights(check_in, date(2024, 3, 31)) == 30

    with pytest.raises(ValueError, match="stay cannot exceed 30 nights"):
        nights(check_in, date(2024, 4, 1))


@pytest.mark.parametrize(
    ("check_in", "check_out"),
    [
        (date(2026, 1, 5), date(2026, 1, 5)),
        (date(2026, 1, 5), date(2026, 1, 4)),
        (date(2026, 1, 5), date(2025, 12, 31)),
    ],
)
def test_nights_rechaza_fechas_no_posteriores(check_in, check_out):
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        nights(check_in, check_out)


@pytest.mark.parametrize(
    ("check_in", "check_out"),
    [
        (date(2026, 1, 5), date(2026, 1, 5)),
        (date(2026, 1, 5), date(2026, 1, 4)),
        (date(2026, 1, 5), date(2025, 12, 31)),
        # Un rango invertido que supera las 30 noches se reporta como rango
        # inválido (E4), no como estadía demasiado larga (E5).
        (date(2026, 3, 1), date(2026, 1, 1)),
    ],
)
def test_nights_informa_el_rango_invalido_con_el_mensaje_exacto(check_in, check_out):
    with pytest.raises(ValueError) as excinfo:
        nights(check_in, check_out)

    assert str(excinfo.value) == "check_out must be after check_in"


def test_nights_las_fechas_no_posteriores_producen_value_error_y_no_type_error():
    with pytest.raises(ValueError):
        nights(date(2026, 1, 5), date(2026, 1, 5))

    with pytest.raises(ValueError):
        nights(date(2026, 1, 5), date(2026, 1, 4))


@pytest.mark.parametrize(
    ("check_in", "check_out"),
    [
        (datetime(2026, 1, 5, 12, 0), date(2026, 1, 6)),
        (date(2026, 1, 5), datetime(2026, 1, 6, 12, 0)),
    ],
)
def test_nights_rechaza_datetime(check_in, check_out):
    with pytest.raises(TypeError, match="not datetime.datetime"):
        nights(check_in, check_out)


@pytest.mark.parametrize(
    ("check_in", "check_out", "expected_type"),
    [
        ("2026-01-05", date(2026, 1, 6), "str"),
        (None, date(2026, 1, 6), "NoneType"),
        (20260105, date(2026, 1, 6), "int"),
        (date(2026, 1, 5), "2026-01-06", "str"),
        (date(2026, 1, 5), None, "NoneType"),
        (date(2026, 1, 5), 20260106, "int"),
    ],
)
def test_nights_rechaza_fechas_de_tipo_incorrecto(check_in, check_out, expected_type):
    with pytest.raises(TypeError, match=f"must be a datetime.date, got {expected_type}"):
        nights(check_in, check_out)


def test_nights_valida_el_tipo_antes_del_rango():
    # Una fecha invertida con ``datetime`` debe fallar por tipo, no por rango.
    with pytest.raises(TypeError, match="not datetime.datetime"):
        nights(datetime(2026, 1, 10, 8, 0), date(2026, 1, 5))


@pytest.mark.parametrize(
    ("check_in", "check_out", "expected"),
    [
        (date(2026, 1, 31), date(2026, 2, 1), 1),
        (date(2026, 2, 27), date(2026, 3, 2), 3),
        (date(2025, 12, 31), date(2026, 1, 2), 2),
        (date(2024, 2, 28), date(2024, 3, 1), 2),
        (date(2024, 2, 29), date(2024, 3, 1), 1),
        (date(2026, 1, 5), date(2026, 1, 6), 1),
    ],
)
def test_nights_es_la_diferencia_en_dias_calendario(check_in, check_out, expected):
    # La resta de dos ``date`` produce días calendario completos, sin resto.
    assert nights(check_in, check_out) == expected
    assert nights(check_in, check_out) == (check_out - check_in).days
    assert nights(check_in, check_out) == check_out.toordinal() - check_in.toordinal()


def test_nights_no_consulta_el_reloj_ni_el_huso_horario():
    # El módulo no lee el reloj ni convierte a marcas de tiempo: el conteo de
    # noches depende únicamente del par de fechas.
    fuente = inspect.getsource(booking)

    assert "now(" not in fuente
    assert "utcnow" not in fuente
    assert "timestamp" not in fuente
    assert "timezone" not in fuente
    assert "time.time" not in fuente


def test_nights_es_estable_para_el_mismo_par_de_fechas():
    check_in = date(2026, 1, 2)
    check_out = date(2026, 1, 4)

    assert {nights(check_in, check_out) for _ in range(3)} == {2}


# ---------------------------------------------------------------------------
# Contrato de días calendario entre ambas fechas (R3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("check_in", "check_out"),
    [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2024, 2, 1), date(2024, 3, 1)),
        (date(2026, 3, 15), date(2026, 4, 14)),
        (date(2026, 6, 30), date(2026, 7, 30)),
        (date(2025, 12, 31), date(2026, 1, 1)),
    ],
)
def test_nights_es_la_diferencia_entre_las_dos_fechas(check_in, check_out):
    # El conteo es la diferencia de días calendario entre ambas fechas, sin
    # horas ni minutos residuales: coincide con la resta de las fechas y con la
    # diferencia de sus números ordinales.
    assert nights(check_in, check_out) == (check_out - check_in).days
    assert nights(check_in, check_out) == check_out.toordinal() - check_in.toordinal()
    assert nights(check_in, check_out) == booking._calendar_days_between(
        check_in, check_out
    )


def test_nights_devuelve_un_numero_de_dias_y_no_un_intervalo():
    resultado = nights(date(2026, 1, 5), date(2026, 1, 12))

    assert isinstance(resultado, int)
    assert not isinstance(resultado, timedelta)
    assert not isinstance(resultado, bool)


@pytest.mark.parametrize(
    ("anio", "mes", "dias_del_mes"),
    [
        (2026, 1, 31),
        (2026, 2, 28),
        (2024, 2, 29),
        (2026, 4, 30),
        (2026, 12, 31),
    ],
)
def test_nights_cubre_cada_mes_del_calendario(anio, mes, dias_del_mes):
    # El conteo no descuadra los meses: desde el día 2 de un mes hasta el día
    # 1 del mes siguiente hay exactamente los días que dura el mes, menos el
    # primer día.
    check_in = date(anio, mes, 2)
    check_out = date(anio + (mes // 12), (mes % 12) + 1, 1)

    assert nights(check_in, check_out) == dias_del_mes - 1


# ---------------------------------------------------------------------------
# Contrato de fechas planas (E1-E3, E6)
# ---------------------------------------------------------------------------


class _Instante(datetime):
    """Subclase de ``datetime.datetime`` para verificar la detección."""


@pytest.mark.parametrize(
    "fecha",
    [
        datetime(2026, 1, 5, 12, 0),
        datetime(2026, 1, 5),
        _Instante(2026, 1, 5, 12, 0),
    ],
)
def test_nights_rechaza_datetime_en_cualquier_parametro(fecha):
    with pytest.raises(TypeError, match="not datetime.datetime"):
        nights(fecha, date(2026, 1, 6))

    with pytest.raises(TypeError, match="not datetime.datetime"):
        nights(date(2026, 1, 5), fecha)


@pytest.mark.parametrize(
    ("valor", "expected_type"),
    [
        (True, "bool"),
        (1.5, "float"),
        (Decimal("20260105"), "Decimal"),
        (["2026-01-05"], "list"),
        ({"2026-01-05": 1}, "dict"),
    ],
)
def test_nights_rechaza_cualquier_valor_que_no_sea_una_fecha(valor, expected_type):
    with pytest.raises(TypeError, match=f"must be a datetime.date, got {expected_type}"):
        nights(valor, date(2026, 1, 6))

    with pytest.raises(TypeError, match=f"must be a datetime.date, got {expected_type}"):
        nights(date(2026, 1, 5), valor)


def test_nights_rechaza_datetime_aunque_herede_de_date():
    # ``datetime`` es subclase de ``date``: comprobar solo ``isinstance(x, date)``
    # aceptaría una fecha con hora, por lo que el orden de las comprobaciones
    # es parte del contrato.
    assert issubclass(datetime, date)

    with pytest.raises(TypeError, match="not datetime.datetime"):
        nights(datetime(2026, 1, 5), date(2026, 1, 6))


def test_nights_valida_check_in_antes_que_check_out():
    with pytest.raises(TypeError) as excinfo:
        nights(datetime(2026, 1, 5), datetime(2026, 1, 6))

    assert str(excinfo.value) == "check_in must be a datetime.date, not datetime.datetime"


def test_nights_el_tipo_de_check_out_precede_al_rango():
    with pytest.raises(TypeError) as excinfo:
        nights(date(2026, 1, 5), datetime(2026, 1, 4))

    assert str(excinfo.value) == "check_out must be a datetime.date, not datetime.datetime"


def test_nights_el_validador_comprueba_datetime_antes_que_date():
    # Orden interno del validador: la comprobación de ``datetime`` debe
    # ejecutarse antes que la de ``date``.
    fuente = inspect.getsource(booking._require_plain_date)

    assert fuente.index("isinstance(value, datetime)") < fuente.index(
        "isinstance(value, date)"
    )


def test_nights_aplica_el_validador_de_fechas_a_ambos_parametros():
    # R6: la validación de tipo se aplica a ``check_in`` y a ``check_out``.
    fuente = inspect.getsource(booking.nights)

    assert '_require_plain_date(check_in, "check_in")' in fuente
    assert '_require_plain_date(check_out, "check_out")' in fuente


@pytest.mark.parametrize("nombre", ["check_in", "check_out", "day"])
def test_el_validador_devuelve_la_misma_fecha_recibida(nombre):
    fecha = date(2026, 1, 5)

    assert booking._require_plain_date(fecha, nombre) is fecha


@pytest.mark.parametrize(
    ("valor", "expected_type"),
    [
        ("2026-01-05", "str"),
        (None, "NoneType"),
        (20260105, "int"),
        (1.5, "float"),
        (True, "bool"),
        (Decimal("20260105"), "Decimal"),
        (["2026-01-05"], "list"),
        ({"2026-01-05": 1}, "dict"),
    ],
)
def test_el_validador_rechaza_cualquier_valor_que_no_sea_una_fecha(valor, expected_type):
    with pytest.raises(TypeError, match=f"must be a datetime.date, got {expected_type}"):
        booking._require_plain_date(valor, "check_in")


@pytest.mark.parametrize(
    "fecha",
    [
        datetime(2026, 1, 5, 12, 0),
        datetime(2026, 1, 5),
        _Instante(2026, 1, 5, 12, 0),
    ],
)
def test_el_validador_rechaza_datetime_antes_de_considerar_date(fecha):
    with pytest.raises(TypeError, match="not datetime.datetime"):
        booking._require_plain_date(fecha, "check_in")


def test_el_validador_incluye_el_nombre_del_parametro_en_el_mensaje():
    with pytest.raises(TypeError) as excinfo:
        booking._require_plain_date("2026-01-05", "check_out")

    assert str(excinfo.value) == "check_out must be a datetime.date, got str"


def test_el_validador_no_forma_parte_de_la_superficie_publica():
    assert "_require_plain_date" not in booking.__all__


def test_nightly_rate_rechaza_datetime_antes_de_validar_la_habitacion():
    with pytest.raises(TypeError) as excinfo:
        nightly_rate(datetime(2026, 1, 5, 8, 0), "deluxe")

    assert str(excinfo.value) == "day must be a datetime.date, not datetime.datetime"


def test_stay_total_rechaza_fechas_con_hora_en_cualquier_parametro():
    with pytest.raises(TypeError, match="not datetime.datetime"):
        stay_total(datetime(2026, 1, 5, 10, 0), date(2026, 1, 6), "double", 2)

    with pytest.raises(TypeError, match="not datetime.datetime"):
        stay_total(date(2026, 1, 5), datetime(2026, 1, 6, 10, 0), "double", 2)


def test_stay_total_el_tipo_de_fecha_precede_al_rango_y_a_la_habitacion():
    with pytest.raises(TypeError, match="not datetime.datetime"):
        stay_total(date(2026, 1, 6), datetime(2026, 1, 5), "deluxe", 99)


# ---------------------------------------------------------------------------
# nightly_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("room", "expected"),
    [
        ("single", Decimal("50.00")),
        ("double", Decimal("80.00")),
        ("suite", Decimal("150.00")),
    ],
)
def test_nightly_rate_tarifa_base_en_dia_habil(room, expected):
    assert nightly_rate(MONDAY, room) == expected


@pytest.mark.parametrize(
    ("room", "expected"),
    [
        ("single", Decimal("62.50")),
        ("double", Decimal("100.00")),
        ("suite", Decimal("187.50")),
    ],
)
def test_nightly_rate_recargo_de_fin_de_semana(room, expected):
    assert nightly_rate(FRIDAY, room) == expected
    assert nightly_rate(SATURDAY, room) == expected


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
        date(2026, 1, 8),
        date(2026, 1, 4),
    ],
)
def test_nightly_rate_sin_recargo_de_lunes_a_jueves_ni_domingo(day):
    assert day.weekday() not in WEEKEND_DAYS
    assert nightly_rate(day, "double") == BASE_RATES["double"]


@pytest.mark.parametrize("room", ["single", "double", "suite"])
def test_nightly_rate_aplica_el_recargo_sobre_la_tarifa_base(room):
    assert WEEKEND_SURCHARGE_RATE == Decimal("0.25")
    esperado = (BASE_RATES[room] * (Decimal(1) + WEEKEND_SURCHARGE_RATE)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )

    assert nightly_rate(FRIDAY, room) == esperado


def test_nightly_rate_depende_del_dia_que_empieza_la_noche():
    # La noche que empieza el viernes se cobra con recargo aunque termine el sábado.
    assert nightly_rate(FRIDAY, "double") == Decimal("100.00")
    # La noche que empieza el sábado también se cobra con recargo.
    assert nightly_rate(SATURDAY, "double") == Decimal("100.00")
    # La noche que empieza el domingo se cobra a tarifa base.
    assert nightly_rate(date(2026, 1, 4), "double") == Decimal("80.00")


@pytest.mark.parametrize("day", [MONDAY, FRIDAY, SATURDAY])
def test_nightly_rate_devuelve_decimal_con_dos_decimales(day):
    resultado = nightly_rate(day, "suite")

    assert isinstance(resultado, Decimal)
    assert resultado.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("day", "expected_type"),
    [
        ("2026-01-05", "str"),
        (None, "NoneType"),
        (20260105, "int"),
    ],
)
def test_nightly_rate_rechaza_fecha_de_tipo_incorrecto(day, expected_type):
    with pytest.raises(TypeError, match=f"day must be a datetime.date, got {expected_type}"):
        nightly_rate(day, "double")


def test_nightly_rate_rechaza_datetime():
    with pytest.raises(TypeError, match="day must be a datetime.date, not datetime.datetime"):
        nightly_rate(datetime(2026, 1, 2, 22, 30), "double")


@pytest.mark.parametrize(
    ("room", "expected_type"),
    [
        (None, "NoneType"),
        (80, "int"),
        (["double"], "list"),
    ],
)
def test_nightly_rate_rechaza_habitacion_no_texto(room, expected_type):
    with pytest.raises(TypeError, match=f"room must be a str, got {expected_type}"):
        nightly_rate(MONDAY, room)


@pytest.mark.parametrize("room", ["Double", "deluxe", "", "SINGLE"])
def test_nightly_rate_rechaza_habitacion_desconocida(room):
    with pytest.raises(ValueError, match=f"unknown room: {room!r}"):
        nightly_rate(MONDAY, room)


def test_nightly_rate_valida_el_tipo_de_fecha_antes_que_el_de_habitacion():
    with pytest.raises(TypeError, match="day must be a datetime.date"):
        nightly_rate(datetime(2026, 1, 2, 10, 0), 80)


def test_nightly_rate_es_determinista():
    assert nightly_rate(FRIDAY, "double") == nightly_rate(FRIDAY, "double")


def test_nightly_rate_no_altera_las_tablas_de_tarifas():
    antes = dict(BASE_RATES)

    nightly_rate(FRIDAY, "suite")
    nightly_rate(MONDAY, "single")

    assert BASE_RATES == antes


# ---------------------------------------------------------------------------
# Contrato de tarifas y constantes (integración)
# ---------------------------------------------------------------------------


def test_base_rates_declara_las_tarifas_de_las_tres_habitaciones():
    assert BASE_RATES["single"] == Decimal("50.00")
    assert BASE_RATES["double"] == Decimal("80.00")
    assert BASE_RATES["suite"] == Decimal("150.00")


def test_base_rates_contiene_solo_las_habitaciones_documentadas():
    assert set(BASE_RATES) == {"single", "double", "suite"}


@pytest.mark.parametrize("room", ["single", "double", "suite"])
def test_las_tarifas_base_son_decimales_de_dos_decimales(room):
    tarifa = BASE_RATES[room]

    assert isinstance(tarifa, Decimal)
    assert tarifa.as_tuple().exponent == -2


def test_las_tarifas_no_se_construyen_desde_literales_binarios():
    # Los importes se construyen desde cadenas: un literal binario
    # introduciría error de representación en las sumas posteriores.
    arbol = ast.parse(inspect.getsource(booking))
    literales_flot = [
        nodo.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, float)
    ]

    assert literales_flot == []


def test_weekend_days_corresponden_a_viernes_y_sabado():
    assert WEEKEND_DAYS == frozenset({4, 5})
    assert FRIDAY.weekday() in WEEKEND_DAYS
    assert SATURDAY.weekday() in WEEKEND_DAYS
    assert MONDAY.weekday() not in WEEKEND_DAYS


def test_weekend_surcharge_rate_es_el_25_por_ciento():
    assert WEEKEND_SURCHARGE_RATE == Decimal("0.25")
    assert BASE_RATES["double"] * (Decimal(1) + WEEKEND_SURCHARGE_RATE) == Decimal("100.00")


def test_cents_es_el_exponente_de_cuantizacion():
    assert CENTS == Decimal("0.01")
    assert CENTS.as_tuple().exponent == -2


@pytest.mark.parametrize("room", ["single", "double", "suite"])
@pytest.mark.parametrize(
    "day",
    [
        date(2026, 1, 4),
        MONDAY,
        date(2026, 1, 6),
        date(2026, 1, 7),
        FRIDAY,
        SATURDAY,
    ],
)
def test_nightly_rate_siempre_devuelve_un_decimal_de_dos_decimales(day, room):
    resultado = nightly_rate(day, room)

    assert isinstance(resultado, Decimal)
    assert not isinstance(resultado, float)
    assert resultado.as_tuple().exponent == -2


def test_nightly_rate_deriva_el_recargo_del_dia_que_empieza_la_noche():
    # La noche del viernes se cobra con recargo aunque termine el sábado.
    assert nightly_rate(FRIDAY, "double") > BASE_RATES["double"]
    # La noche del sábado también, aunque termine el domingo.
    assert nightly_rate(SATURDAY, "double") > BASE_RATES["double"]
    # La noche del domingo se cobra a tarifa base aunque termine el lunes.
    assert nightly_rate(date(2026, 1, 4), "double") == BASE_RATES["double"]
    # La noche del lunes se cobra a tarifa base aunque termine el martes.
    assert nightly_rate(MONDAY, "double") == BASE_RATES["double"]


def test_nightly_rate_acepta_exclusivamente_las_tres_habitaciones_del_contrato():
    for room in ("single", "double", "suite"):
        assert nightly_rate(MONDAY, room) == BASE_RATES[room]

    with pytest.raises(ValueError, match="unknown room"):
        nightly_rate(MONDAY, "deluxe")


# ---------------------------------------------------------------------------
# stay_total
# ---------------------------------------------------------------------------


def test_stay_total_ejemplo_canonico():
    # 2026-01-02 (viernes) → 2026-01-04, double, 2 huéspedes:
    # 100.00 + 100.00 + 10.00 = 210.00
    total = stay_total(date(2026, 1, 2), date(2026, 1, 4), "double", 2)

    assert total == Decimal("210.00")


def test_stay_total_descompone_el_ejemplo_canonico():
    check_in = date(2026, 1, 2)
    check_out = date(2026, 1, 4)
    guests = 2
    noches = nights(check_in, check_out)

    subtotal_habitacion = sum(
        (nightly_rate(check_in + timedelta(days=offset), "double") for offset in range(noches)),
        Decimal("0.00"),
    )
    tasa = TOURIST_TAX_PER_GUEST_NIGHT * guests * noches

    assert subtotal_habitacion == Decimal("200.00")
    assert tasa == Decimal("10.00")
    assert stay_total(check_in, check_out, "double", guests) == subtotal_habitacion + tasa


@pytest.mark.parametrize(
    ("room", "guests", "expected_total"),
    [
        ("single", 1, Decimal("52.50")),
        ("double", 2, Decimal("85.00")),
        ("suite", 4, Decimal("160.00")),
    ],
)
def test_stay_total_de_una_noche_incluye_la_tasa_turistica(room, guests, expected_total):
    check_in = MONDAY
    check_out = date(2026, 1, 6)

    total = stay_total(check_in, check_out, room, guests)
    tarifa = BASE_RATES[room]
    tasa = TOURIST_TAX_PER_GUEST_NIGHT * guests

    assert total == tarifa + tasa
    assert total == expected_total


@pytest.mark.parametrize(
    ("room", "guests", "expected_total"),
    [
        ("single", 1, Decimal("340.00")),
        ("double", 2, Decimal("550.00")),
        ("suite", 4, Decimal("1035.00")),
    ],
)
def test_stay_total_sin_descuento_para_estadias_cortas(room, guests, expected_total):
    # Seis noches (2026-01-05 → 2026-01-11): por debajo del umbral de descuento.
    check_in = date(2026, 1, 5)
    check_out = date(2026, 1, 11)
    noches = nights(check_in, check_out)

    subtotal_habitacion = sum(
        (nightly_rate(check_in + timedelta(days=offset), room) for offset in range(noches)),
        Decimal("0.00"),
    )

    total = stay_total(check_in, check_out, room, guests)

    assert noches == LONG_STAY_NIGHTS - 1
    assert total == subtotal_habitacion + TOURIST_TAX_PER_GUEST_NIGHT * guests * noches
    assert total == expected_total


@pytest.mark.parametrize(
    ("room", "guests", "expected_room_subtotal", "expected_total"),
    [
        ("single", 1, Decimal("375.00"), Decimal("355.00")),
        ("double", 2, Decimal("600.00"), Decimal("575.00")),
        ("suite", 4, Decimal("1125.00"), Decimal("1082.50")),
    ],
)
def test_stay_total_descuento_de_estadia_larga(
    room, guests, expected_room_subtotal, expected_total
):
    # Siete noches (2026-01-05 → 2026-01-12): incluye dos noches de fin de semana.
    check_in = date(2026, 1, 5)
    check_out = date(2026, 1, 12)
    noches = nights(check_in, check_out)

    subtotal_habitacion = sum(
        (nightly_rate(check_in + timedelta(days=offset), room) for offset in range(noches)),
        Decimal("0.00"),
    )
    subtotal_con_descuento = (subtotal_habitacion * (Decimal(1) - LONG_STAY_DISCOUNT_RATE)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )
    tasa = TOURIST_TAX_PER_GUEST_NIGHT * guests * noches

    total = stay_total(check_in, check_out, room, guests)

    assert noches == LONG_STAY_NIGHTS
    assert subtotal_habitacion == expected_room_subtotal
    assert total == subtotal_con_descuento + tasa
    assert total == expected_total


def test_stay_total_el_descuento_no_alcanza_a_la_tasa_turistica():
    check_in = date(2026, 1, 5)
    check_out = date(2026, 1, 12)
    noches = nights(check_in, check_out)
    guests = 1

    subtotal_habitacion = sum(
        (nightly_rate(check_in + timedelta(days=offset), "single") for offset in range(noches)),
        Decimal("0.00"),
    )
    total = stay_total(check_in, check_out, "single", guests)
    descuento = (subtotal_habitacion * LONG_STAY_DISCOUNT_RATE).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )
    tasa = TOURIST_TAX_PER_GUEST_NIGHT * guests * noches

    # El descuento equivale exactamente al 10 % del subtotal de habitación.
    assert total == subtotal_habitacion + tasa - descuento
    # La tasa turística se cobra completa, sin descuento.
    assert total - (subtotal_habitacion - descuento) == tasa
    assert tasa == Decimal("17.50")


def test_stay_total_devuelve_decimal_con_dos_decimales():
    total = stay_total(date(2026, 1, 5), date(2026, 1, 12), "double", 2)

    assert isinstance(total, Decimal)
    assert total.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("guests", "expected_type"),
    [
        (True, "bool"),
        (False, "bool"),
        (2.0, "float"),
        ("2", "str"),
        (None, "NoneType"),
    ],
)
def test_stay_total_rechaza_guests_de_tipo_incorrecto(guests, expected_type):
    with pytest.raises(TypeError, match=f"guests must be an int, got {expected_type}"):
        stay_total(date(2026, 1, 5), date(2026, 1, 6), "double", guests)


@pytest.mark.parametrize(
    ("room", "guests"),
    [
        ("single", 0),
        ("single", 2),
        ("double", 0),
        ("double", 3),
        ("suite", 0),
        ("suite", 5),
    ],
)
def test_stay_total_rechaza_guests_fuera_de_rango(room, guests):
    capacidad = ROOM_CAPACITY[room]

    with pytest.raises(
        ValueError, match=f"guests must be between 1 and {capacidad} for room {room!r}"
    ):
        stay_total(date(2026, 1, 5), date(2026, 1, 6), room, guests)


@pytest.mark.parametrize(
    ("room", "guests"),
    [
        ("single", 1),
        ("double", 1),
        ("double", 2),
        ("suite", 1),
        ("suite", 4),
    ],
)
def test_stay_total_admite_huespedes_dentro_de_la_capacidad(room, guests):
    assert stay_total(date(2026, 1, 5), date(2026, 1, 6), room, guests) > Decimal("0.00")


def test_stay_total_propaga_los_errores_de_fecha():
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        stay_total(date(2026, 1, 6), date(2026, 1, 5), "double", 2)

    with pytest.raises(ValueError, match="stay cannot exceed 30 nights"):
        stay_total(date(2026, 1, 1), date(2026, 2, 1), "double", 2)

    with pytest.raises(TypeError, match="not datetime.datetime"):
        stay_total(datetime(2026, 1, 5, 10, 0), date(2026, 1, 6), "double", 2)


def test_stay_total_rechaza_fechas_iguales():
    with pytest.raises(ValueError) as excinfo:
        stay_total(date(2026, 1, 5), date(2026, 1, 5), "double", 2)

    assert str(excinfo.value) == "check_out must be after check_in"


def test_stay_total_propaga_los_errores_de_habitacion():
    with pytest.raises(TypeError, match="room must be a str, got int"):
        stay_total(date(2026, 1, 5), date(2026, 1, 6), 80, 1)

    with pytest.raises(ValueError, match="unknown room: 'deluxe'"):
        stay_total(date(2026, 1, 5), date(2026, 1, 6), "deluxe", 1)


def test_stay_total_valida_las_fechas_antes_que_la_habitacion():
    with pytest.raises(ValueError, match="check_out must be after check_in"):
        stay_total(date(2026, 1, 6), date(2026, 1, 5), "deluxe", 1)


def test_stay_total_valida_la_habitacion_antes_que_los_huespedes():
    with pytest.raises(ValueError, match="unknown room: 'deluxe'"):
        stay_total(date(2026, 1, 5), date(2026, 1, 6), "deluxe", 99)


def test_stay_total_es_determinista():
    argumentos = (date(2026, 1, 2), date(2026, 1, 12), "double", 2)

    assert stay_total(*argumentos) == stay_total(*argumentos)


# ---------------------------------------------------------------------------
# Integración: las siete reglas de `nightly_rate` y sus constantes
# ---------------------------------------------------------------------------


def test_la_tarifa_corresponde_a_la_noche_que_empieza_en_day():
    # Regla 1: el estado de fin de semana se deriva de ``day.weekday()``, no
    # del día en que la noche termina.
    fuente = inspect.getsource(booking.nightly_rate)

    assert "day.weekday()" in fuente
    assert "WEEKEND_DAYS" in fuente


@pytest.mark.parametrize(
    ("dia_inicio", "esperado"),
    [
        (date(2026, 1, 1), Decimal("80.00")),  # jueves
        (date(2026, 1, 2), Decimal("100.00")),  # viernes
        (date(2026, 1, 3), Decimal("100.00")),  # sábado
        (date(2026, 1, 4), Decimal("80.00")),  # domingo
        (date(2026, 1, 5), Decimal("80.00")),  # lunes
    ],
)
def test_la_noche_se_cobra_segun_el_dia_en_el_que_empieza(dia_inicio, esperado):
    assert nightly_rate(dia_inicio, "double") == esperado


def test_base_rates_declara_las_tarifas_de_las_tres_habitaciones_como_constantes():
    # Reglas 2, 3 y 4: la tabla de tarifas base se declara con los tres
    # importes del contrato, construidos desde cadenas.
    fuente = inspect.getsource(booking)

    assert 'BASE_RATES["single"] = Decimal("50.00")' in fuente
    assert 'BASE_RATES["double"] = Decimal("80.00")' in fuente
    assert 'BASE_RATES["suite"] = Decimal("150.00")' in fuente


def test_el_recargo_de_fin_de_semana_usa_las_constantes_del_contrato():
    # Regla 5: el mecanismo del recargo es ``base * (1 + WEEKEND_SURCHARGE_RATE)``
    # y solo se aplica en los días de ``WEEKEND_DAYS``.
    fuente = inspect.getsource(booking.nightly_rate)

    assert "WEEKEND_SURCHARGE_RATE" in fuente
    assert "Decimal(1) + WEEKEND_SURCHARGE_RATE" in fuente
    assert WEEKEND_DAYS == frozenset({4, 5})
    assert WEEKEND_SURCHARGE_RATE == Decimal("0.25")


@pytest.mark.parametrize("room", ["single", "double", "suite"])
def test_el_recargo_se_aplica_solo_a_las_noches_de_viernes_y_sabado(room):
    base = BASE_RATES[room]
    recargado = (base * (Decimal(1) + WEEKEND_SURCHARGE_RATE)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )

    for dia in range(1, 8):  # 2026-01-01 (jueves) … 2026-01-07 (miércoles)
        fecha = date(2026, 1, dia)
        esperado = recargado if fecha.weekday() in WEEKEND_DAYS else base

        assert nightly_rate(fecha, room) == esperado


def test_el_resultado_monetario_es_un_decimal_de_dos_decimales():
    # Regla 6: el resultado es un ``Decimal`` (nunca un ``float``) con
    # exactamente dos decimales, cuantizado con ``ROUND_HALF_UP``.
    fuente = inspect.getsource(booking.nightly_rate)

    assert "CENTS" in fuente
    assert "ROUND_HALF_UP" in fuente
    assert "quantize" in fuente

    for dia in range(1, 8):
        for room in ("single", "double", "suite"):
            resultado = nightly_rate(date(2026, 1, dia), room)

            assert isinstance(resultado, Decimal)
            assert not isinstance(resultado, float)
            assert resultado.as_tuple().exponent == -2


def test_la_identificacion_de_habitacion_se_valida_por_tipo_y_por_valor():
    # Regla 7: el identificador de habitación debe ser un ``str`` (E7) y
    # una de las tres habitaciones documentadas (E8).
    fuente = inspect.getsource(booking)

    assert "isinstance(room, str)" in fuente
    assert "room not in BASE_RATES" in fuente

    with pytest.raises(TypeError, match="room must be a str, got int"):
        nightly_rate(MONDAY, 80)

    with pytest.raises(ValueError, match="unknown room: 'deluxe'"):
        nightly_rate(MONDAY, "deluxe")


def test_las_tres_habitaciones_documentadas_son_las_aceptadas():
    assert set(BASE_RATES) == {"single", "double", "suite"}
    assert set(ROOM_CAPACITY) == {"single", "double", "suite"}

    for room in ("single", "double", "suite"):
        assert nightly_rate(MONDAY, room) == BASE_RATES[room]
