from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage, send_mail

from .pdf_utils import generar_pdf_cotizacion


CORREO_COMERCIAL_DEFAULT = "director.comercial@impetushps.co"


def _correo_comercial():
    return getattr(settings, "COTIZADOR_EMAIL_COPIA", None) or getattr(
        settings, "IMPETUS_NOTIFICACIONES_EMAIL", CORREO_COMERCIAL_DEFAULT
    )


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
    cc = [correo_copia or _correo_comercial()]

    email = EmailMessage(
        subject=asunto,
        body=mensaje,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
        cc=cc,
    )
    email.attach_file(str(ruta_pdf))
    email.send(fail_silently=False)


def enviar_notificacion_comercial(asunto, mensaje):
    destino = _correo_comercial()
    if not destino:
        return 0
    return send_mail(
        subject=asunto,
        message=mensaje,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[destino],
        fail_silently=False,
    )


def notificar_nueva_cotizacion_bomba(solicitud):
    numero = f"CP-{solicitud.id:04d}"
    mensaje = f"""
Nueva cotización presupuestal de bomba registrada.

Número: {numero}
Empresa: {solicitud.empresa}
Contacto: {solicitud.contacto}
Correo: {solicitud.correo}
Teléfono: {solicitud.telefono}
Proyecto/pozo: {solicitud.nombre_proyecto}
Caudal: {solicitud.caudal}
Presión succión: {solicitud.presion_succion}
Presión descarga: {solicitud.presion_descarga}
Equipo recomendado: {solicitud.equipo_recomendado}
Valor estimado: {solicitud.valor_estimado}
Observaciones: {solicitud.observaciones_cliente}
""".strip()
    return enviar_notificacion_comercial(f"Nueva cotización bomba {numero}", mensaje)


def notificar_nueva_reparacion_camara(solicitud):
    numero = f"RC-{solicitud.id:04d}"
    mensaje = f"""
Nueva solicitud de reparación de cámara registrada.

Número: {numero}
Empresa: {solicitud.empresa}
Contacto: {solicitud.contacto}
Correo: {solicitud.correo}
Teléfono: {solicitud.telefono}
Proyecto/pozo: {solicitud.nombre_proyecto}
Marca: {solicitud.marca}
Modelo: {solicitud.modelo}
Serial: {solicitud.serial}
Tipo reparación: {solicitud.tipo_reparacion}
Tiempo estimado: {solicitud.tiempo_estimado_texto}
Valor estimado: {solicitud.valor_estimado}
Observaciones cliente: {solicitud.observaciones_cliente}
""".strip()
    return enviar_notificacion_comercial(f"Nueva solicitud reparación cámara {numero}", mensaje)


def notificar_precio_reparacion_camara(solicitud):
    numero = f"RC-{solicitud.id:04d}"
    mensaje = f"""
El cliente solicitó precio formal para una reparación de cámara.

Número: {numero}
Empresa: {solicitud.empresa}
Contacto: {solicitud.contacto}
Correo: {solicitud.correo}
Teléfono: {solicitud.telefono}
Marca/Modelo: {solicitud.marca} {solicitud.modelo}
Tipo reparación: {solicitud.tipo_reparacion}
Fecha solicitud precio: {solicitud.fecha_solicitud_precio}
""".strip()
    return enviar_notificacion_comercial(f"Cliente solicitó precio {numero}", mensaje)


def notificar_uso_sospechoso_vsd(log, total_ip, total_sesion, ventana_minutos):
    mensaje = f"""
Alerta de monitoreo VSD: posible uso intensivo del diagnóstico público.

IP: {log.ip_address}
Sesión: {log.session_key or 'sin sesión'}
User-Agent: {log.user_agent}
Última consulta: {log.marca} {log.codigo}
Encontrado: {'Sí' if log.encontrado else 'No'}
Consultas desde IP en {ventana_minutos} min: {total_ip}
Consultas desde sesión en {ventana_minutos} min: {total_sesion}
Referer: {log.referer}
Ruta: {log.path}
Fecha: {log.created_at}

Recomendación: revise si corresponde a un cliente real, bot, scraping o posible competencia jalando información.
""".strip()
    return enviar_notificacion_comercial("Alerta: uso intensivo del diagnóstico VSD", mensaje)
