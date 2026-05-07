from pathlib import Path
import os

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)


def generar_pdf_cotizacion(ruta, solicitud):
    doc = SimpleDocTemplate(ruta, pagesize=letter)
    styles = getSampleStyleSheet()
    contenido = []

    # -------------------------
    # LOGO
    # -------------------------
    logo_path = Path(settings.BASE_DIR) / "cotizador" / "static" / "cotizador" / "logo.png"

    if logo_path.exists():
        logo = Image(str(logo_path), width=180, height=70)
        contenido.append(logo)
        contenido.append(Spacer(1, 12))

    # -------------------------
    # TITULO Y NUMERO
    # -------------------------
    numero_cotizacion = f"CP-{solicitud.id:04d}"

    contenido.append(Paragraph("COTIZACIÓN PRESUPUESTAL", styles["Title"]))
    contenido.append(Spacer(1, 6))
    contenido.append(Paragraph(f"<b>Número:</b> {numero_cotizacion}", styles["Normal"]))
    contenido.append(Spacer(1, 18))

    # -------------------------
    # DATOS CLIENTE
    # -------------------------
    contenido.append(Paragraph("<b>Datos del cliente</b>", styles["Heading2"]))
    contenido.append(Spacer(1, 8))

    tabla_cliente = Table([
        ["Empresa", solicitud.empresa or ""],
        ["Contacto", solicitud.contacto or ""],
        ["Correo", solicitud.correo or ""],
        ["Teléfono", solicitud.telefono or ""],
        ["Proyecto / Pozo", solicitud.nombre_proyecto or ""],
        ["Observaciones cliente", solicitud.observaciones_cliente or ""],
    ], colWidths=[120, 300])

    tabla_cliente.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    contenido.append(tabla_cliente)
    contenido.append(Spacer(1, 15))

    # -------------------------
    # DATOS DE OPERACION
    # -------------------------
    contenido.append(Paragraph("<b>Datos de operación</b>", styles["Heading2"]))
    contenido.append(Spacer(1, 8))

    tabla_operacion = Table([
        ["Caudal", str(solicitud.caudal)],
        ["Presión Succión", str(solicitud.presion_succion)],
        ["Presión Descarga", str(solicitud.presion_descarga)],
        ["DP", str(solicitud.dp_calculada)],
    ], colWidths=[180, 240])

    tabla_operacion.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    contenido.append(tabla_operacion)
    contenido.append(Spacer(1, 15))

    # -------------------------
    # EQUIPO RECOMENDADO
    # -------------------------
    contenido.append(Paragraph("<b>Equipo recomendado</b>", styles["Heading2"]))
    contenido.append(Spacer(1, 8))

    equipo = solicitud.equipo_recomendado
    punto = solicitud.punto_recomendado

    tabla_equipo = Table([
        ["Equipo", f"{equipo.id_equipo} - {equipo.nombre_equipo}"],
        ["Bomba", equipo.bomba or ""],
        ["Potencia HP", str(punto.potencia_hp)],
        ["Carga Cámara", str(punto.carga_camara)],
        ["Eficiencia", f"{punto.eficiencia_pct}%"],
        ["Tipo operación", punto.tipo_punto],
        ["Longitud total", f"{equipo.longitud_total_mm} mm" if equipo.longitud_total_mm else ""],
    ], colWidths=[180, 240])

    tabla_equipo.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    contenido.append(tabla_equipo)
    contenido.append(Spacer(1, 15))

    # -------------------------
    # RESUMEN ECONOMICO
    # -------------------------
    contenido.append(Paragraph("<b>Resumen económico</b>", styles["Heading2"]))
    contenido.append(Spacer(1, 8))

    tabla_valores = Table([
        ["Valor estimado", f"$ {solicitud.valor_estimado}"],
        ["Tiempo entrega (días)", str(solicitud.tiempo_entrega_estimado_dias)],
    ], colWidths=[200, 220])

    tabla_valores.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    contenido.append(tabla_valores)
    contenido.append(Spacer(1, 20))

    # -------------------------
    # CURVA DEL EQUIPO
    # -------------------------
    if equipo.curva_imagen:
        ruta_imagen = equipo.curva_imagen.path

        if os.path.exists(ruta_imagen):
            contenido.append(Paragraph("<b>Curva del equipo</b>", styles["Heading2"]))
            contenido.append(Spacer(1, 10))

            img = Image(ruta_imagen, width=420, height=260)
            contenido.append(img)
            contenido.append(Spacer(1, 20))

    # -------------------------
    # OBSERVACIONES
    # -------------------------
    contenido.append(Paragraph("<b>Observaciones</b>", styles["Heading2"]))
    contenido.append(Spacer(1, 8))

    nota = """
    Esta cotización corresponde a un valor presupuestal estimado, elaborado con base en la información suministrada por el cliente y en la selección técnica realizada por el sistema.
    Las condiciones comerciales, técnicas y contractuales definitivas serán establecidas durante la etapa de validación y negociación final.
    """

    contenido.append(Paragraph(nota, styles["Normal"]))

    doc.build(contenido)