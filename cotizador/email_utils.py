from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage

from .pdf_utils import generar_pdf_cotizacion


def enviar_cotizacion_por_correo(solicitud, correo_copia=None):
    ruta_pdf = Path(settings.BASE_DIR) / f"cotizacion_{solicitud.id}.pdf"
    generar_pdf_cotizacion(str(ruta_pdf), solicitud)

    numero_cotizacion = f"CP-{solicitud.id:04d}"
    asunto = f"Cotización presupuestal {numero_cotizacion}"

    mensaje = f"""
Cordial saludo,

Adjuntamos la cotización presupuestal correspondiente a su requerimiento.

Número: {numero_cotizacion}
Equipo recomendado: {solicitud.equipo_recomendado}
Valor estimado: $ {solicitud.valor_estimado}
Tiempo estimado de entrega: {solicitud.tiempo_entrega_estimado_dias} días

Este documento corresponde a una cotización presupuestal y las condiciones definitivas serán establecidas en la etapa de validación y negociación final.

Atentamente,
Impetus HPS
""".strip()

    destinatarios = [solicitud.correo]
    cc = [correo_copia] if correo_copia else []

    email = EmailMessage(
        subject=asunto,
        body=mensaje,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
        cc=cc,
    )

    email.attach_file(str(ruta_pdf))
    email.send(fail_silently=False)