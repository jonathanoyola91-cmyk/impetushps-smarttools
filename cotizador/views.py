from decimal import Decimal
import json
import openpyxl

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .email_utils import enviar_cotizacion_por_correo
from .forms import ImportadorDiagnosticoVariadorForm
from .models import SolicitudCotizacion
from .pdf_utils import generar_pdf_cotizacion
from .services import seleccionar_mejor_punto, calcular_dp
from .models import ReparacionCamaraTarifa, SolicitudReparacionCamara
from .models import DiagnosticoVariador

def home_view(request):
    return render(request, "cotizador/home.html")
import json

def reparacion_camara_view(request):
    resultado = None
    error = None
    solicitud_id = None

    tarifas = ReparacionCamaraTarifa.objects.filter(
        activo=True
    ).order_by("marca", "modelo")

    marcas = list(
        tarifas.values_list("marca", flat=True).distinct()
    )

    modelos_por_marca = {}

    for marca in marcas:
        modelos_por_marca[marca] = list(
            tarifas.filter(marca=marca)
            .values_list("modelo", flat=True)
            .distinct()
        )

    if request.method == "POST":
        try:
            empresa = request.POST.get("empresa", "").strip()
            contacto = request.POST.get("contacto", "").strip()
            correo = request.POST.get("correo", "").strip()
            telefono = request.POST.get("telefono", "").strip()
            nombre_proyecto = request.POST.get("nombre_proyecto", "").strip()

            marca = request.POST.get("marca", "").strip()
            modelo = request.POST.get("modelo", "").strip()
            serial = request.POST.get("serial", "").strip()
            tipo_reparacion = request.POST.get("tipo_reparacion", "").strip()
            observaciones_cliente = request.POST.get("observaciones_cliente", "").strip()

            # Validación mínima
            if not empresa or not contacto or not correo:
                error = "Debe ingresar empresa, contacto y correo."
            else:
                tarifa = ReparacionCamaraTarifa.objects.filter(
                    activo=True,
                    marca=marca,
                    modelo=modelo,
                    tipo_reparacion=tipo_reparacion
                ).first()

                if not tarifa:
                    error = "No se encontró configuración para esa selección."
                else:
                    solicitud = SolicitudReparacionCamara.objects.create(
                        empresa=empresa,
                        contacto=contacto,
                        correo=correo,
                        telefono=telefono,
                        nombre_proyecto=nombre_proyecto,
                        marca=marca,
                        modelo=modelo,
                        serial=serial,
                        tipo_reparacion=tipo_reparacion,
                        observaciones_cliente=observaciones_cliente,
                        observacion_tecnica=tarifa.observacion,
                        tiempo_estimado_texto=tarifa.tiempo_estimado_texto,
                        valor_estimado=tarifa.valor_estimado,
                    )

                    resultado = solicitud
                    solicitud_id = solicitud.id

        except Exception as exc:
            error = f"Error: {exc}"

    return render(request, "cotizador/reparacion_camara.html", {
        "resultado": resultado,
        "error": error,
        "solicitud_id": solicitud_id,
        "marcas": marcas,
        "modelos_por_marca_json": json.dumps(modelos_por_marca),
    })
def solicitar_precio_reparacion(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudReparacionCamara, id=solicitud_id)

    solicitud.solicito_precio = True
    solicitud.fecha_solicitud_precio = timezone.now()
    solicitud.save()

    mensaje = (
        f"El cliente {solicitud.empresa} solicitó precio para la reparación "
        f"de cámara {solicitud.marca} {solicitud.modelo} - {solicitud.tipo_reparacion}."
    )

    return render(request, "cotizador/precio_solicitado.html", {
        "solicitud": solicitud,
        "mensaje": mensaje,
    })
def descargar_pdf(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCotizacion, id=solicitud_id)

    ruta = f"cotizacion_{solicitud.id}.pdf"
    generar_pdf_cotizacion(ruta, solicitud)

    return FileResponse(open(ruta, "rb"), as_attachment=True)


def enviar_cotizacion_email(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudCotizacion, id=solicitud_id)

    enviar_cotizacion_por_correo(
        solicitud,
        correo_copia=getattr(settings, "COTIZADOR_EMAIL_COPIA", None),
    )

    numero_cotizacion = f"CP-{solicitud.id:04d}"
    es_modo_prueba = settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"

    if es_modo_prueba:
        mensaje = (
            f"La cotización presupuestal {numero_cotizacion} fue procesada en modo prueba. "
            f"El contenido del correo fue generado y mostrado en la consola para revisión."
        )
    else:
        mensaje = (
            f"La cotización presupuestal {numero_cotizacion} fue enviada correctamente "
            f"al correo {solicitud.correo}."
        )

    return render(request, "cotizador/email_enviado.html", {
        "solicitud": solicitud,
        "mensaje": mensaje,
        "numero_cotizacion": numero_cotizacion,
        "es_modo_prueba": es_modo_prueba,
    })


def cotizador_view(request):
    resultado = None
    error = None
    solicitud_id = None

    if request.method == "POST":
        try:
            empresa = request.POST.get("empresa", "").strip()
            contacto = request.POST.get("contacto", "").strip()
            correo = request.POST.get("correo", "").strip()
            telefono = request.POST.get("telefono", "").strip()
            nombre_proyecto = request.POST.get("nombre_proyecto", "").strip()
            observaciones_cliente = request.POST.get("observaciones_cliente", "").strip()

            caudal = Decimal(request.POST.get("caudal", "0"))
            ps = Decimal(request.POST.get("presion_succion", "0"))
            pd = Decimal(request.POST.get("presion_descarga", "0"))
            temperatura_fluido = request.POST.get("temperatura_fluido")
            gravedad_especifica = request.POST.get("gravedad_especifica")
            viscosidad = request.POST.get("viscosidad")

            resultado = seleccionar_mejor_punto(
                caudal=caudal,
                presion_succion=ps,
                presion_descarga=pd,
            )

            if not resultado:
                error = "No se encontró un equipo compatible."
            else:
                dp = calcular_dp(ps, pd)

                solicitud = SolicitudCotizacion.objects.create(
                    empresa=empresa,
                    contacto=contacto,
                    correo=correo,
                    telefono=telefono,
                    nombre_proyecto=nombre_proyecto,
                    observaciones_cliente=observaciones_cliente,
                    presion_succion=ps,
                    presion_descarga=pd,
                    caudal=caudal,
                    dp_calculada=dp,
                    equipo_recomendado=resultado["equipo"],
                    punto_recomendado=resultado["punto"],
                    valor_estimado=resultado["equipo"].precio_base or 0,
                    tiempo_entrega_estimado_dias=resultado["equipo"].tiempo_base_dias or 0,
                )

                solicitud_id = solicitud.id

        except Exception as exc:
            error = f"Error en los datos ingresados: {exc}"

    return render(request, "cotizador/formulario.html", {
        "resultado": resultado,
        "error": error,
        "solicitud_id": solicitud_id,
    })


def historial_cotizaciones(request):
    q = request.GET.get("q", "").strip()

    solicitudes = SolicitudCotizacion.objects.all().order_by("-created_at")

    if q:
        solicitudes = solicitudes.filter(
            Q(empresa__icontains=q) |
            Q(contacto__icontains=q) |
            Q(correo__icontains=q) |
            Q(nombre_proyecto__icontains=q)
        ).order_by("-created_at")

    return render(request, "cotizador/historial.html", {
        "solicitudes": solicitudes,
        "q": q,
    })

def diagnostico_variador_view(request):
    resultado = None
    error = None

    marcas = (
        DiagnosticoVariador.objects
        .filter(activo=True)
        .values_list("marca", flat=True)
        .distinct()
        .order_by("marca")
    )

    if request.method == "POST":
        marca = request.POST.get("marca", "").strip()
        codigo = request.POST.get("codigo", "").strip()

        resultado = DiagnosticoVariador.objects.filter(
            activo=True,
            marca__iexact=marca,
            codigo__iexact=codigo
        ).first()

        if not resultado:
            error = "No se encontró información para ese código."

    return render(request, "cotizador/diagnostico_variador.html", {
        "resultado": resultado,
        "error": error,
        "marcas": marcas,
    })

def importar_diagnostico_variador_view(request):
    resumen = None
    error = None
    mensaje_ok = None

    if request.method == "POST":
        form = ImportadorDiagnosticoVariadorForm(request.POST, request.FILES)

        if form.is_valid():
            archivo = form.cleaned_data["archivo"]

            if not archivo.name.lower().endswith(".xlsx"):
                error = "Debe cargar un archivo Excel .xlsx"
                return render(
                    request,
                    "cotizador/importar_diagnostico_variador.html",
                    {
                        "form": form,
                        "resumen": resumen,
                        "error": error,
                    }
                )

            try:
                wb = openpyxl.load_workbook(archivo, data_only=True)
                ws = wb.active

                encabezados_requeridos = [
                    "Marca",
                    "Código",
                    "Tipo",
                    "Nombre de Falla",
                    "Causa Probable",
                    "Acción Recomendada",
                    "Categoría",
                    "Activo",
                ]

                encabezados_archivo = [
                    str(cell.value).strip() if cell.value is not None else ""
                    for cell in ws[1]
                ]

                faltantes = [
                    col for col in encabezados_requeridos
                    if col not in encabezados_archivo
                ]

                if faltantes:
                    error = f"Faltan columnas obligatorias: {', '.join(faltantes)}"
                    return render(
                        request,
                        "cotizador/importar_diagnostico_variador.html",
                        {
                            "form": form,
                            "resumen": resumen,
                            "error": error,
                        }
                    )

                indices = {
                    col: encabezados_archivo.index(col)
                    for col in encabezados_requeridos
                }

                creados = 0
                actualizados = 0
                filas_vacias = 0
                errores = []

                for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    marca = str(row[indices["Marca"]]).strip() if row[indices["Marca"]] is not None else ""
                    codigo = str(row[indices["Código"]]).strip() if row[indices["Código"]] is not None else ""
                    tipo = str(row[indices["Tipo"]]).strip() if row[indices["Tipo"]] is not None else ""
                    nombre_falla = str(row[indices["Nombre de Falla"]]).strip() if row[indices["Nombre de Falla"]] is not None else ""
                    causa_probable = str(row[indices["Causa Probable"]]).strip() if row[indices["Causa Probable"]] is not None else ""
                    accion_recomendada = str(row[indices["Acción Recomendada"]]).strip() if row[indices["Acción Recomendada"]] is not None else ""
                    categoria = str(row[indices["Categoría"]]).strip() if row[indices["Categoría"]] is not None else ""
                    activo_raw = str(row[indices["Activo"]]).strip().lower() if row[indices["Activo"]] is not None else "sí"

                    if not marca and not codigo and not tipo and not nombre_falla:
                        filas_vacias += 1
                        continue

                    if not marca or not codigo or not tipo or not nombre_falla:
                        errores.append(f"Fila {idx}: faltan campos obligatorios.")
                        continue

                    activo = activo_raw in ["si", "sí", "true", "1", "activo", "yes"]

                    _, creado = DiagnosticoVariador.objects.update_or_create(
                        marca=marca,
                        codigo=codigo,
                        defaults={
                            "tipo": tipo,
                            "nombre_falla": nombre_falla,
                            "causa_probable": causa_probable,
                            "accion_recomendada": accion_recomendada,
                            "categoria": categoria,
                            "activo": activo,
                        }
                    )

                    if creado:
                        creados += 1
                    else:
                        actualizados += 1

                resumen = {
                    "creados": creados,
                    "actualizados": actualizados,
                    "filas_vacias": filas_vacias,
                    "errores": errores,
                }

                mensaje_ok = (
                    f"Importación completada. "
                    f"Creados: {creados} | Actualizados: {actualizados} | "
                    f"Filas vacías: {filas_vacias}"
                )

            except Exception as exc:
                error = f"Error procesando archivo: {exc}"

        else:
            error = "Debe seleccionar un archivo válido."

    else:
        form = ImportadorDiagnosticoVariadorForm()

    return render(
        request,
        "cotizador/importar_diagnostico_variador.html",
        {
            "form": form,
            "resumen": resumen,
            "error": error,
            "mensaje_ok": mensaje_ok,
        }
    )