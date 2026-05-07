from decimal import Decimal
from typing import Optional

from .models import CurvaOperacion, EquipoBase


TIPO_PUNTO_PESO = {
    "NOMINAL": Decimal("1.00"),
    "ALTO_CAUDAL": Decimal("0.80"),
    "BAJA_EFICIENCIA": Decimal("0.30"),
}


def calcular_dp(presion_succion: Decimal, presion_descarga: Decimal) -> Decimal:
    return presion_descarga - presion_succion


def seleccionar_mejor_punto(
    caudal: Decimal,
    presion_succion: Decimal,
    presion_descarga: Decimal,
) -> Optional[dict]:
    dp_objetivo = calcular_dp(presion_succion, presion_descarga)

    if dp_objetivo <= 0:
        return None

    equipos_candidatos = EquipoBase.objects.filter(
        activo=True,
        caudal_min_bpd__lte=caudal,
        caudal_max_bpd__gte=caudal,
        ps_min_psi__lte=presion_succion,
        ps_max_psi__gte=presion_succion,
        pd_min_psi__lte=presion_descarga,
        pd_max_psi__gte=presion_descarga,
    )

    if not equipos_candidatos.exists():
        return None

    puntos = CurvaOperacion.objects.filter(
        equipo__in=equipos_candidatos
    ).select_related("equipo")

    if not puntos.exists():
        return None

    mejor_resultado = None
    mejor_score = None

    for punto in puntos:
        diff_caudal = abs(Decimal(punto.caudal) - caudal)
        diff_dp = abs(Decimal(punto.dp_requerida) - dp_objetivo)

        score_distancia = Decimal("1000000") - (diff_caudal * Decimal("10")) - (diff_dp * Decimal("20"))
        score_eficiencia = Decimal(punto.eficiencia_pct) * Decimal("100")
        score_tipo = TIPO_PUNTO_PESO.get(punto.tipo_punto, Decimal("0.50")) * Decimal("1000")

        score_total = score_distancia + score_eficiencia + score_tipo

        if mejor_score is None or score_total > mejor_score:
            mejor_score = score_total
            mejor_resultado = {
                "equipo": punto.equipo,
                "punto": punto,
                "dp_objetivo": dp_objetivo,
                "score": score_total,
                "detalle": {
                    "caudal_solicitado": caudal,
                    "presion_succion": presion_succion,
                    "presion_descarga": presion_descarga,
                    "dp_objetivo": dp_objetivo,
                    "caudal_punto": punto.caudal,
                    "dp_punto": punto.dp_requerida,
                    "potencia_hp": punto.potencia_hp,
                    "carga_camara": punto.carga_camara,
                    "eficiencia_pct": punto.eficiencia_pct,
                    "tipo_punto": punto.tipo_punto,
                },
            }

    return mejor_resultado