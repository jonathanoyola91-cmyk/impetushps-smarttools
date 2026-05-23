from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
import pandas as pd

from .models import (
    ClientAccount,
    FieldLocation,
    InjectionSystem,
    BodegaCampoItem,
    SystemComponent,
    ComponentChangeLog,
    MaintenanceRule,
)
from .forms import InjectionSystemForm, SystemComponentForm
from .forms_change import ChangeComponentForm
from .forms import MaintenanceRuleForm
from .forms import OperationalMonitoringForm
from .models import OperationalLimit
from .forms import OperationalLimitForm
from django.http import HttpResponse, HttpResponseForbidden
from django.template.loader import get_template
from xhtml2pdf import pisa

from .models import InjectionSystem

import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from django.http import HttpResponse
from django.shortcuts import get_object_or_404


def _puede_gestionar_bodega(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=[
            "RUNLIFE_ADMIN",
            "RUNLIFE_BODEGA",
            "Gerencia",
            "gerencia",
            "Ingeniería",
            "INGENIERIA",
        ]).exists()
    )

def _generar_observacion_monitoreo(monitoreo, sistema, cantidad=5):
    anteriores = list(
        sistema.monitoreos
        .exclude(pk=monitoreo.pk)
        .order_by("-fecha", "-hora")[:cantidad]
    )

    if not anteriores:
        return "Primer registro de monitoreo. Sin histórico suficiente para comparar tendencia."

    def promedio(campo):
        valores = [getattr(m, campo) for m in anteriores if getattr(m, campo) is not None]
        return sum(valores) / len(valores) if valores else None

    mensajes = []

    prom_caudal = promedio("caudal")
    prom_temp = promedio("temperatura_camara")
    prom_vib = promedio("vibracion_camara")

    dp_valores = [m.diferencial_presion for m in anteriores if m.diferencial_presion is not None]
    prom_dp = sum(dp_valores) / len(dp_valores) if dp_valores else None

    if prom_caudal and monitoreo.caudal:
        variacion = ((monitoreo.caudal - prom_caudal) / prom_caudal) * 100
        if variacion > 10:
            mensajes.append(f"Caudal superior al promedio reciente en {variacion:.1f}%.")
        elif variacion < -10:
            mensajes.append(f"Caudal inferior al promedio reciente en {abs(variacion):.1f}%.")

    if prom_temp and monitoreo.temperatura_camara:
        diferencia = monitoreo.temperatura_camara - prom_temp
        if diferencia >= 5:
            mensajes.append(f"Temperatura de cámara aumentó {diferencia:.1f} °C frente al promedio reciente.")

    if prom_vib and monitoreo.vibracion_camara:
        diferencia = monitoreo.vibracion_camara - prom_vib
        if diferencia >= 1:
            mensajes.append(f"Vibración de cámara aumentó {diferencia:.1f} mm/s frente al promedio reciente.")

    if prom_dp and monitoreo.diferencial_presion:
        variacion = ((monitoreo.diferencial_presion - prom_dp) / prom_dp) * 100
        if variacion > 10:
            mensajes.append(f"ΔP superior al promedio reciente en {variacion:.1f}%.")
        elif variacion < -10:
            mensajes.append(f"ΔP inferior al promedio reciente en {abs(variacion):.1f}%.")

    if monitoreo.estado_thrust == "UP_THRUST":
        mensajes.append("Condición UP THRUST por caudal superior al límite operativo.")
    elif monitoreo.estado_thrust == "DOWN_THRUST":
        mensajes.append("Condición DOWN THRUST por caudal inferior al límite operativo.")

    if monitoreo.alerta_temperatura_camara == "ALERTA":
        mensajes.append("Temperatura en alerta.")
    elif monitoreo.alerta_temperatura_camara == "CRITICO":
        mensajes.append("Temperatura crítica.")

    if monitoreo.alerta_vibracion == "ALERTA":
        mensajes.append("Vibración en alerta.")
    elif monitoreo.alerta_vibracion == "CRITICO":
        mensajes.append("Vibración crítica.")

    if monitoreo.alerta_presion == "ALERTA":
        mensajes.append("Presión diferencial en alerta.")
    elif monitoreo.alerta_presion == "CRITICO":
        mensajes.append("Presión diferencial crítica.")

    return " ".join(mensajes) if mensajes else "Operación estable. Variables dentro del comportamiento promedio reciente."

def monitoreo_pdf(request, sistema_id):
    sistema = get_object_or_404(InjectionSystem, id=sistema_id)

    monitoreos = sistema.monitoreos.all()[:30]
    ultimo = monitoreos.first()

    data = list(reversed(monitoreos))

    labels = [
        f"{m.fecha.strftime('%d/%m')} {m.hora.strftime('%H:%M')}"
        for m in data
    ]

    caudal = [m.caudal or 0 for m in data]
    descarga = [m.presion_descarga or 0 for m in data]
    succion = [m.presion_succion or 0 for m in data]
    temp = [m.temperatura_camara or 0 for m in data]

    grafica_base64 = None

    if data:
        fig, ax1 = plt.subplots(figsize=(11.5, 4.2))

        ax1.plot(
            labels,
            caudal,
            marker="o",
            linewidth=2.4,
            color="#2563eb",
            label="Caudal (BPD)"
        )

        ax1.set_ylabel("Caudal (BPD)")
        ax1.tick_params(axis="y", labelsize=8)
        ax1.tick_params(axis="x", rotation=0, labelsize=7)
        ax1.grid(True, linestyle="-", linewidth=0.4, alpha=0.35)

        ax2 = ax1.twinx()

        ax2.plot(
            labels,
            descarga,
            marker="o",
            linewidth=2.2,
            color="#ef4444",
            label="P. Descarga"
        )

        ax2.plot(
            labels,
            succion,
            marker="o",
            linewidth=2.2,
            color="#06b6d4",
            label="P. Succión"
        )

        ax2.set_ylabel("Presión (PSI)")
        ax2.tick_params(axis="y", labelsize=8)

        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("axes", 1.06))

        ax3.plot(
            labels,
            temp,
            marker="o",
            linewidth=2.2,
            color="#9333ea",
            label="Temp"
        )

        ax3.set_ylabel("Temp. °C")
        ax3.tick_params(axis="y", labelsize=8)

        ax1.set_title("Tendencia Operacional", fontsize=14, fontweight="bold", pad=12)
        ax1.set_xlabel("Fecha / Hora", fontsize=9)

        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_2, labels_2 = ax2.get_legend_handles_labels()
        lines_3, labels_3 = ax3.get_legend_handles_labels()

        ax1.legend(
            lines_1 + lines_2 + lines_3,
            labels_1 + labels_2 + labels_3,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.08),
            ncol=4,
            fontsize=8,
            frameon=False
        )

        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
        plt.close(fig)

        grafica_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    template = get_template("runlife/monitoreo_pdf.html")

    html = template.render({
        "sistema": sistema,
        "monitoreos": monitoreos,
        "ultimo": ultimo,
        "grafica_base64": grafica_base64,
    })

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="monitoreo_{sistema.nombre}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generando PDF", status=500)

    return response

def monitoreo_dashboard(request, sistema_id):
    sistema = get_object_or_404(InjectionSystem, id=sistema_id)

    monitoreos = sistema.monitoreos.all()[:20]  # últimos registros
    ultimo = monitoreos.first()

    context = {
        "sistema": sistema,
        "monitoreos": monitoreos,
        "ultimo": ultimo,
    }
    return render(request, "runlife/monitoreo_dashboard.html", context)

@login_required
def limites_operativos(request):
    campos = _campos_permitidos(request.user)

    limites = OperationalLimit.objects.select_related(
        "campo", "campo__cliente"
    ).filter(
        campo__in=campos
    ).order_by("campo__cliente__nombre", "campo__nombre")

    return render(request, "runlife/limites_operativos.html", _runlife_context(
        request,
        sidebar_subtitle="Límites operativos",
        limites=limites,
    ))


@login_required
def crear_limite_operativo(request):
    campos = _campos_permitidos(request.user)

    if request.method == "POST":
        form = OperationalLimitForm(request.POST)
        form.fields["campo"].queryset = campos

        if form.is_valid():
            limite = form.save(commit=False)

            if not campos.filter(id=limite.campo_id).exists():
                messages.error(request, "No tiene permisos para este campo.")
                return redirect("runlife:limites_operativos")

            limite.save()
            messages.success(request, "Límite operativo creado correctamente.")
            return redirect("runlife:limites_operativos")
    else:
        form = OperationalLimitForm()
        form.fields["campo"].queryset = campos

    return render(request, "runlife/limite_operativo_form.html", _runlife_context(
        request,
        sidebar_subtitle="Nuevo límite",
        form=form,
    ))


@login_required
def editar_limite_operativo(request, limite_id):
    campos = _campos_permitidos(request.user)
    limite = get_object_or_404(OperationalLimit, id=limite_id, campo__in=campos)

    if request.method == "POST":
        form = OperationalLimitForm(request.POST, instance=limite)
        form.fields["campo"].queryset = campos

        if form.is_valid():
            form.save()
            messages.success(request, "Límite operativo actualizado correctamente.")
            return redirect("runlife:limites_operativos")
    else:
        form = OperationalLimitForm(instance=limite)
        form.fields["campo"].queryset = campos

    return render(request, "runlife/limite_operativo_form.html", _runlife_context(
        request,
        sidebar_subtitle="Editar límite",
        form=form,
        limite=limite,
    ))
@login_required
def monitoreo_sistema(request, sistema_id):
    sistema = get_object_or_404(InjectionSystem, id=sistema_id)

    if request.method == "POST":
        form = OperationalMonitoringForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.sistema = sistema

            if not obj.observaciones:
                obj.save()
                obj.observaciones = _generar_observacion_monitoreo(obj, sistema)
                obj.save(update_fields=["observaciones"])
            else:
                obj.save()

            messages.success(request, "Monitoreo registrado correctamente.")
            return redirect("runlife:monitoreo", sistema_id=sistema.id)
    else:
        form = OperationalMonitoringForm()

    monitoreos = sistema.monitoreos.all()[:20]

    return render(request, "runlife/monitoreo.html", {
        "sistema": sistema,
        "form": form,
        "monitoreos": monitoreos,
    })

def _es_admin_runlife(user):
    return user.is_staff or user.is_superuser


def _campos_permitidos(user):
    if _es_admin_runlife(user):
        return FieldLocation.objects.filter(activo=True)
    return FieldLocation.objects.filter(activo=True, usuarios=user)


def _clientes_permitidos(user):
    if _es_admin_runlife(user):
        return ClientAccount.objects.all().order_by("nombre")

    cliente_ids = _campos_permitidos(user).values_list("cliente_id", flat=True)
    return ClientAccount.objects.filter(id__in=cliente_ids).distinct().order_by("nombre")


def _usuario_puede_ver_campo(user, campo):
    if _es_admin_runlife(user):
        return True
    return campo.usuarios.filter(id=user.id).exists()


def _tiene_grupo(user, nombres_grupo):
    if not user.is_authenticated:
        return False
    return user.groups.filter(name__in=nombres_grupo).exists()


def _puede_gestionar_reglas(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name="RUNLIFE_REGLAS").exists()
        or user.groups.filter(name="RUNLIFE_ADMIN").exists()
    )


def _puede_ver_garantias(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=[
            "RUNLIFE_ADMIN",
            "RUNLIFE_GARANTIAS",
            "RUNLIFE_REGLAS",
            "gerencia",
            "Gerencia",
            "Ingeniería",
            "INGENIERIA",
        ]).exists()
    )


def _runlife_context(request, sidebar_subtitle="RunLife", **extra):
    """Contexto base para que base_runlife.html siempre conozca permisos del usuario."""
    puede = _puede_gestionar_reglas(request.user)
    context = {
        "puede_reglas": puede,
        "puede_gestionar_reglas": puede,
        "puede_ver_garantias": _puede_ver_garantias(request.user),
        "sidebar_subtitle": sidebar_subtitle,
        "puede_gestionar_bodega": _puede_gestionar_bodega(request.user),
    }
    context.update(extra)
    return context


def _puede_importar_componentes(user):
    return (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=[
            "RUNLIFE_ADMIN",
            "RUNLIFE_IMPORTADOR",
            "Gerencia",
            "gerencia",
        ]).exists()
    )


def _normalizar_tipo_componente(valor):
    valor = str(valor or "").strip()

    mapa_tipos = {
        "MOTOR": "MOTOR",
        "Motor": "MOTOR",
        "motor": "MOTOR",

        "CAMARA": "CAMARA",
        "Cámara": "CAMARA",
        "Camara": "CAMARA",
        "Cámara de Empuje": "CAMARA",
        "Camara de Empuje": "CAMARA",
        "cámara de empuje": "CAMARA",
        "camara de empuje": "CAMARA",

        "BOMBA": "BOMBA",
        "Bomba": "BOMBA",
        "bomba": "BOMBA",

        "COOLER": "COOLER",
        "Cooler": "COOLER",
        "cooler": "COOLER",

        "VSD": "VSD",
        "Variador": "VSD",
        "variador": "VSD",
        "Variador / VSD": "VSD",
        "variador / vsd": "VSD",

        "OTRO": "OTRO",
        "Otro": "OTRO",
        "otro": "OTRO",
    }

    return mapa_tipos.get(valor, valor.upper())


def _valor_excel(row, columna, defecto=""):
    if columna not in row.index:
        return defecto

    valor = row.get(columna)

    if pd.isna(valor):
        return defecto

    return str(valor).strip()


def _fecha_excel(row, columna):
    if columna not in row.index or pd.isna(row.get(columna)):
        return None

    valor = row.get(columna)

    if hasattr(valor, "date"):
        return valor.date()

    return parse_date(str(valor))


@login_required
def importar_componentes_excel(request):
    if not _puede_importar_componentes(request.user):
        return HttpResponseForbidden("No tienes permiso para importar componentes.")

    sistemas = InjectionSystem.objects.select_related(
        "campo",
        "campo__cliente",
    ).filter(
        activo=True,
    ).order_by(
        "campo__cliente__nombre",
        "campo__nombre",
        "nombre",
    )

    if request.method == "POST":
        archivo = request.FILES.get("archivo")

        if not archivo:
            messages.error(request, "Debes seleccionar un archivo Excel.")
            return redirect("runlife:importar_componentes_excel")

        try:
            df = pd.read_excel(archivo)
        except Exception as e:
            messages.error(request, f"No se pudo leer el archivo Excel: {e}")
            return redirect("runlife:importar_componentes_excel")

        columnas_requeridas = [
            "sistema_id",
            "tipo",
            "descripcion",
            "serial",
            "parte_numero",
        ]

        for columna in columnas_requeridas:
            if columna not in df.columns:
                messages.error(request, f"Falta la columna obligatoria: {columna}")
                return redirect("runlife:importar_componentes_excel")

        tipos_unicos = ["MOTOR", "CAMARA", "COOLER", "VSD"]

        creados = 0
        errores = []

        with transaction.atomic():
            for index, row in df.iterrows():
                fila = index + 2

                try:
                    sistema_id_raw = row.get("sistema_id")

                    if pd.isna(sistema_id_raw):
                        errores.append(f"Fila {fila}: sistema_id es obligatorio.")
                        continue

                    sistema_id = int(sistema_id_raw)
                    sistema = InjectionSystem.objects.get(id=sistema_id)

                    tipo = _normalizar_tipo_componente(row.get("tipo"))
                    tipos_validos = [codigo for codigo, _label in SystemComponent.TIPO_COMPONENTE]

                    if tipo not in tipos_validos:
                        errores.append(
                            f"Fila {fila}: tipo '{row.get('tipo')}' no es válido. "
                            "Use MOTOR, CAMARA, BOMBA, COOLER, VSD u OTRO."
                        )
                        continue

                    descripcion = _valor_excel(row, "descripcion")
                    serial = _valor_excel(row, "serial")
                    parte_numero = _valor_excel(row, "parte_numero")

                    if not serial:
                        errores.append(f"Fila {fila}: serial es obligatorio.")
                        continue

                    marca = _valor_excel(row, "marca", "IMPETUS") or "IMPETUS"
                    modelo = _valor_excel(row, "modelo", "")
                    origen = _valor_excel(row, "origen", "CLIENTE") or "CLIENTE"

                    origenes_validos = [codigo for codigo, _label in SystemComponent.ORIGEN_COMPONENTE]
                    if origen not in origenes_validos:
                        errores.append(
                            f"Fila {fila}: origen '{origen}' no es válido. "
                            "Use IMPETUS_FAB, IMPETUS_REP o CLIENTE."
                        )
                        continue

                    fecha_instalacion = _fecha_excel(row, "fecha_instalacion")
                    fecha_entrega_cliente = _fecha_excel(row, "fecha_entrega_cliente") or fecha_instalacion
                    fecha_reparacion = _fecha_excel(row, "fecha_reparacion")
                    fecha_ultimo_mantenimiento = _fecha_excel(row, "fecha_ultimo_mantenimiento")

                    dias_garantia = 365
                    if "dias_garantia" in row.index and not pd.isna(row.get("dias_garantia")):
                        dias_garantia = int(row.get("dias_garantia"))

                    if tipo in tipos_unicos:
                        existe_activo = SystemComponent.objects.filter(
                            sistema=sistema,
                            tipo=tipo,
                            activo=True,
                            fecha_desinstalacion__isnull=True,
                        ).exists()

                        if existe_activo:
                            errores.append(
                                f"Fila {fila}: ya existe un {tipo} activo para el sistema {sistema_id}. Use reemplazo."
                            )
                            continue

                    SystemComponent.objects.create(
                        sistema=sistema,
                        tipo=tipo,
                        origen=origen,
                        descripcion=descripcion,
                        marca=marca,
                        modelo=modelo,
                        serial=serial,
                        parte_numero=parte_numero,
                        fecha_instalacion=fecha_instalacion,
                        fecha_entrega_cliente=fecha_entrega_cliente,
                        fecha_reparacion=fecha_reparacion,
                        fecha_ultimo_mantenimiento=fecha_ultimo_mantenimiento,
                        dias_garantia=dias_garantia,
                        activo=True,
                    )

                    creados += 1

                except InjectionSystem.DoesNotExist:
                    errores.append(f"Fila {fila}: no existe sistema_id {row.get('sistema_id')}")
                except Exception as e:
                    errores.append(f"Fila {fila}: {e}")

        if creados:
            messages.success(request, f"Componentes creados: {creados}")
        else:
            messages.warning(request, "No se creó ningún componente.")

        for error in errores[:30]:
            messages.warning(request, error)

        if len(errores) > 30:
            messages.warning(request, f"Hay {len(errores) - 30} errores adicionales no mostrados.")

        return redirect("runlife:importar_componentes_excel")

    return render(request, "runlife/importar_componentes_excel.html", _runlife_context(
        request,
        sidebar_subtitle="Importar Excel",
        sistemas=sistemas,
    ))


def _configurar_form_regla_por_usuario(form, user):
    """Limita Cliente/Campo del formulario según acceso del usuario."""
    if _es_admin_runlife(user):
        return form

    campos = _campos_permitidos(user).select_related("cliente").order_by("cliente__nombre", "nombre")
    clientes = _clientes_permitidos(user)

    if "campo" in form.fields:
        form.fields["campo"].queryset = campos
        form.fields["campo"].empty_label = "Seleccione campo permitido"

    if "cliente" in form.fields:
        form.fields["cliente"].queryset = clientes
        form.fields["cliente"].empty_label = "Seleccione cliente permitido"

    if clientes.count() == 1 and "cliente" in form.fields and not form.initial.get("cliente"):
        form.initial["cliente"] = clientes.first()

    if campos.count() == 1 and "campo" in form.fields and not form.initial.get("campo"):
        form.initial["campo"] = campos.first()

    return form


def _usuario_puede_gestionar_regla(user, regla):
    if _es_admin_runlife(user):
        return True

    if not _puede_gestionar_reglas(user):
        return False

    campos_ids = set(_campos_permitidos(user).values_list("id", flat=True))
    clientes_ids = set(_clientes_permitidos(user).values_list("id", flat=True))

    if regla.campo_id:
        return regla.campo_id in campos_ids

    if regla.cliente_id:
        return regla.cliente_id in clientes_ids

    # Regla totalmente general: solo admin puede editarla, porque afecta a todos.
    return False


def _guardar_regla_segura(form, user):
    regla = form.save(commit=False)

    if not _es_admin_runlife(user):
        campos = _campos_permitidos(user)
        clientes = _clientes_permitidos(user)

        if not regla.campo_id:
            raise ValueError("Debe seleccionar un campo operativo permitido para la regla.")

        campo_permitido = campos.filter(id=regla.campo_id).select_related("cliente").first()
        if not campo_permitido:
            raise ValueError("No tiene permisos para crear o modificar reglas en ese campo.")

        if regla.cliente_id and not clientes.filter(id=regla.cliente_id).exists():
            raise ValueError("No tiene permisos para ese cliente.")

        # Evita que el usuario relacione la regla con un cliente distinto al campo.
        regla.cliente = campo_permitido.cliente

    regla.save()
    form.save_m2m()
    return regla


@login_required
def crear_regla_mantenimiento(request):
    if not _puede_gestionar_reglas(request.user):
        messages.error(request, "No tiene permisos para crear reglas de mantenimiento. Solicite acceso RUNLIFE_REGLAS al administrador.")
        return redirect("runlife:reglas")

    if request.method == "POST":
        form = MaintenanceRuleForm(request.POST)
        _configurar_form_regla_por_usuario(form, request.user)

        if form.is_valid():
            try:
                _guardar_regla_segura(form, request.user)
                messages.success(request, "Regla de mantenimiento creada correctamente.")
                return redirect("runlife:reglas")
            except ValueError as exc:
                form.add_error(None, str(exc))

        messages.error(request, "Revise los datos del formulario.")
    else:
        form = MaintenanceRuleForm()
        _configurar_form_regla_por_usuario(form, request.user)

    return render(request, "runlife/regla_form.html", _runlife_context(
        request,
        sidebar_subtitle="Nueva regla",
        form=form,
    ))


@login_required
def reglas_mantenimiento(request):
    campos = _campos_permitidos(request.user)
    clientes = _clientes_permitidos(request.user)

    reglas = MaintenanceRule.objects.select_related(
        "cliente",
        "campo",
    )

    if not _es_admin_runlife(request.user):
        reglas = reglas.filter(
            activo=True,
        ).filter(
            campo__in=campos
        ) | MaintenanceRule.objects.select_related(
            "cliente",
            "campo",
        ).filter(
            activo=True,
            campo__isnull=True,
            cliente__in=clientes,
        ) | MaintenanceRule.objects.select_related(
            "cliente",
            "campo",
        ).filter(
            activo=True,
            campo__isnull=True,
            cliente__isnull=True,
        )

    reglas = reglas.distinct().order_by("tipo", "cliente__nombre", "campo__nombre", "horas_mantenimiento")

    return render(request, "runlife/reglas.html", _runlife_context(
        request,
        sidebar_subtitle="Mantenimientos",
        reglas=reglas,
    ))


@login_required
def editar_regla_mantenimiento(request, regla_id):
    regla = get_object_or_404(MaintenanceRule, id=regla_id)

    if not _usuario_puede_gestionar_regla(request.user, regla):
        messages.error(request, "No tiene permisos para modificar esta regla de mantenimiento.")
        return redirect("runlife:reglas")

    if request.method == "POST":
        form = MaintenanceRuleForm(request.POST, instance=regla)
        _configurar_form_regla_por_usuario(form, request.user)

        if form.is_valid():
            try:
                _guardar_regla_segura(form, request.user)
                messages.success(request, "Regla de mantenimiento actualizada correctamente.")
                return redirect("runlife:reglas")
            except ValueError as exc:
                form.add_error(None, str(exc))

        messages.error(request, "Revise los datos del formulario.")
    else:
        form = MaintenanceRuleForm(instance=regla)
        _configurar_form_regla_por_usuario(form, request.user)

    return render(request, "runlife/regla_form.html", _runlife_context(
        request,
        sidebar_subtitle="Editar regla",
        form=form,
        regla=regla,
        modo="editar",
    ))



@login_required
def dashboard_garantias(request):
    if not _puede_ver_garantias(request.user):
        messages.error(request, "No tiene permisos para ver el dashboard de garantías.")
        return redirect("runlife:dashboard")

    campos = _campos_permitidos(request.user)

    componentes = SystemComponent.objects.select_related(
        "sistema",
        "sistema__campo",
        "sistema__campo__cliente",
        "bodega_item",
        "bodega_item__campo",
        "bodega_item__campo__cliente",
    ).filter(
        Q(sistema__campo__in=campos) | Q(bodega_item__campo__in=campos),
    ).filter(
        tipo__in=["BOMBA", "CAMARA", "COOLER"]
    ).filter(
        Q(origen__in=["IMPETUS_FAB", "IMPETUS_REP"]) |
        Q(marca__icontains="IMPETUS") |
        Q(modelo__icontains="IMPETUS")
    ).distinct()

    cliente_id = request.GET.get("cliente")
    campo_id = request.GET.get("campo")
    tipo = request.GET.get("tipo")
    estado = request.GET.get("estado")
    q = request.GET.get("q", "").strip()

    if cliente_id:
        componentes = componentes.filter(
            Q(sistema__campo__cliente_id=cliente_id) | Q(bodega_item__campo__cliente_id=cliente_id)
        )

    if campo_id:
        componentes = componentes.filter(
            Q(sistema__campo_id=campo_id) | Q(bodega_item__campo_id=campo_id)
        )

    if tipo:
        componentes = componentes.filter(tipo=tipo)

    if q:
        componentes = componentes.filter(
            Q(serial__icontains=q) |
            Q(modelo__icontains=q) |
            Q(marca__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(sistema__nombre__icontains=q) |
            Q(sistema__campo__nombre__icontains=q) |
            Q(sistema__campo__cliente__nombre__icontains=q) |
            Q(bodega_item__campo__nombre__icontains=q) |
            Q(bodega_item__campo__cliente__nombre__icontains=q)
        )

    componentes = componentes.order_by(
        "sistema__campo__cliente__nombre",
        "sistema__campo__nombre",
        "sistema__nombre",
        "tipo",
        "serial",
    )

    componentes_lista = list(componentes)

    en_garantia = []
    fuera_garantia = []
    sin_fecha = []

    for componente in componentes_lista:
        # Compatibilidad con el modelo nuevo:
        # ahora la garantía se controla por origen + fecha_entrega_cliente.
        estado_calc = getattr(componente, "estado_garantia_interna", None)

        if not estado_calc:
            estado_calc = getattr(componente, "estado_garantia", None)

        if not estado_calc:
            if not getattr(componente, "fecha_entrega_cliente", None):
                estado_calc = "SIN_FECHA"
            elif getattr(componente, "en_garantia", False) or getattr(componente, "en_garantia_real", False):
                estado_calc = "EN_GARANTIA"
            else:
                estado_calc = "FUERA_GARANTIA"

        # Atributo auxiliar para el template si se requiere.
        componente.estado_garantia_dashboard = estado_calc

        if estado_calc == "EN_GARANTIA":
            en_garantia.append(componente)
        elif estado_calc == "FUERA_GARANTIA":
            fuera_garantia.append(componente)
        elif estado_calc in ["SIN_FECHA", "SIN_ENTREGA"]:
            sin_fecha.append(componente)

    if estado == "EN_GARANTIA":
        componentes_lista = en_garantia
    elif estado == "FUERA_GARANTIA":
        componentes_lista = fuera_garantia
    elif estado == "SIN_FECHA":
        componentes_lista = sin_fecha

    clientes = _clientes_permitidos(request.user)
    campos_filtro = campos.select_related("cliente").order_by("cliente__nombre", "nombre")

    total_componentes = len(componentes_lista)
    total_en_garantia = len([c for c in componentes_lista if getattr(c, "estado_garantia_dashboard", "") == "EN_GARANTIA"])
    total_fuera_garantia = len([c for c in componentes_lista if getattr(c, "estado_garantia_dashboard", "") == "FUERA_GARANTIA"])
    total_sin_fecha = len([c for c in componentes_lista if getattr(c, "estado_garantia_dashboard", "") in ["SIN_FECHA", "SIN_ENTREGA"]])

    return render(request, "runlife/dashboard_garantias.html", _runlife_context(
        request,
        sidebar_subtitle="Garantías",
        componentes=componentes_lista,
        clientes=clientes,
        campos_filtro=campos_filtro,
        tipos_componentes=SystemComponent.TIPO_COMPONENTE,
        filtros={
            "cliente_id": cliente_id or "",
            "campo_id": campo_id or "",
            "tipo": tipo or "",
            "estado": estado or "",
            "q": q,
        },
        total_componentes=total_componentes,
        total_en_garantia=total_en_garantia,
        total_fuera_garantia=total_fuera_garantia,
        total_sin_fecha=total_sin_fecha,
    ))


@login_required
def dashboard_runlife(request):
    campos = _campos_permitidos(request.user).select_related("cliente")

    data = []

    for campo in campos:
        sistemas = InjectionSystem.objects.filter(
            campo=campo,
            activo=True
        )

        componentes = SystemComponent.objects.filter(
            sistema__campo=campo,
            activo=True,
            fecha_desinstalacion__isnull=True
        )

        total_componentes = componentes.count()

        runlife_promedio = 0
        if total_componentes:
            runlife_promedio = round(
                sum([c.runlife_dias for c in componentes]) / total_componentes
            )

        data.append({
            "campo": campo,
            "total_sistemas": sistemas.count(),
            "total_componentes": total_componentes,
            "runlife_promedio": runlife_promedio,
        })

    total_sistemas_global = sum(item["total_sistemas"] for item in data)
    total_componentes_global = sum(item["total_componentes"] for item in data)

    return render(request, "runlife/dashboard.html", _runlife_context(
        request,
        sidebar_subtitle="Dashboard",
        campos_data=data,
        total_sistemas_global=total_sistemas_global,
        total_componentes_global=total_componentes_global,
    ))


@login_required
def campo_detail(request, campo_id):
    user = request.user

    campo = get_object_or_404(FieldLocation.objects.select_related("cliente"), id=campo_id, activo=True)

    if not _usuario_puede_ver_campo(user, campo):
        messages.error(request, "No tiene acceso a este campo operativo.")
        return redirect("runlife:dashboard")

    # Campos permitidos para que el usuario pueda cambiar de Campo/Locación
    # desde esta misma pantalla sin regresar al dashboard.
    campos_usuario = _campos_permitidos(user).select_related("cliente").order_by(
        "cliente__nombre",
        "nombre"
    )

    sistema_id = request.GET.get("sistema")

    sistemas_base = InjectionSystem.objects.filter(
        campo=campo,
        activo=True
    ).order_by("nombre")

    if sistema_id:
        sistemas = sistemas_base.filter(id=sistema_id)
    else:
        sistemas = sistemas_base

    sistemas = sistemas.prefetch_related(
        Prefetch(
            "componentes",
            queryset=SystemComponent.objects.filter(
                activo=True,
                fecha_desinstalacion__isnull=True
            ).order_by("tipo", "descripcion", "serial")
        )
    )

    componentes = SystemComponent.objects.filter(
        sistema__in=sistemas,
        activo=True,
        fecha_desinstalacion__isnull=True
    )

    vencidos = []
    proximos = []
    en_garantia = []
    fuera_garantia = []

    for c in componentes:
        if c.estado_mantenimiento == "VENCIDO":
            vencidos.append(c)
        elif c.estado_mantenimiento == "PROXIMO":
            proximos.append(c)

        if c.runlife_dias > 365:
            fuera_garantia.append(c)
        else:
            en_garantia.append(c)

    total_componentes = componentes.count()

    runlife_promedio = 0
    if total_componentes:
        runlife_promedio = round(
            sum([c.runlife_dias for c in componentes]) / total_componentes
        )

    cambios = ComponentChangeLog.objects.filter(
        sistema__campo=campo
    )

    if sistema_id:
        cambios = cambios.filter(sistema_id=sistema_id)

    cambios = cambios.select_related(
        "sistema",
        "componente_anterior",
        "componente_nuevo"
    ).order_by("-fecha_cambio")[:10]

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "crear_bodega_item":
            if not _puede_gestionar_bodega(request.user):
                messages.error(request, "No tiene permisos para agregar equipos a bodega.")
                return redirect("runlife:campo_detail", campo_id=campo.id)

            componente = SystemComponent.objects.create(
                sistema=None,
                tipo=request.POST.get("tipo"),
                origen=request.POST.get("origen") or "IMPETUS_REP",
                descripcion=request.POST.get("descripcion"),
                marca=request.POST.get("marca") or "IMPETUS",
                modelo=request.POST.get("modelo"),
                serial=request.POST.get("serial"),
                parte_numero=request.POST.get("parte_numero"),
                fecha_reparacion=request.POST.get("fecha_reparacion") or None,
                fecha_entrega_cliente=request.POST.get("fecha_entrega_cliente") or timezone.localdate(),
                dias_garantia=request.POST.get("dias_garantia") or 365,
                activo=True,
            )

            BodegaCampoItem.objects.create(
                campo=campo,
                componente=componente,
                fecha_ingreso_bodega=timezone.localdate(),
                disponible=True,
            )

            messages.success(request, "Equipo agregado a la bodega del campo.")
            return redirect("runlife:campo_detail", campo_id=campo.id)

        if accion == "cambiar_componente":
            form = ChangeComponentForm(request.POST)

            if form.is_valid():
                comp = form.cleaned_data["componente_actual"]
                fecha = form.cleaned_data["fecha_cambio"]

                comp.fecha_desinstalacion = fecha
                comp.activo = False
                comp.save()

                nuevo = SystemComponent.objects.create(
                    sistema=comp.sistema,
                    tipo=comp.tipo,
                    descripcion=comp.descripcion,
                    marca=comp.marca,
                    modelo=form.cleaned_data["nuevo_modelo"],
                    serial=form.cleaned_data["nuevo_serial"],
                    parte_numero=form.cleaned_data["nuevo_parte"],
                    fecha_instalacion=fecha,
                    activo=True
                )

                ComponentChangeLog.objects.create(
                    sistema=comp.sistema,
                    componente_anterior=comp,
                    componente_nuevo=nuevo,
                    tipo=comp.tipo,
                    fecha_cambio=fecha,
                    runlife_anterior_dias=comp.runlife_dias,
                    creado_por=request.user
                )

                messages.success(request, "Cambio realizado")
                return redirect("runlife:campo_detail", campo_id=campo.id)
                
    bodega_items = BodegaCampoItem.objects.select_related(
        "componente",
        "componente__sistema"
    ).filter(
        campo=campo,
        disponible=True
    )  

    return render(request, "runlife/campo_detail.html", _runlife_context(
        request,
        sidebar_subtitle=campo.cliente.nombre,
        campo=campo,
        campos_usuario=campos_usuario,
        sistemas=sistemas,
        sistemas_base=sistemas_base,
        sistema_id=sistema_id,
        componentes=componentes,
        bodega_items=bodega_items,
        vencidos=vencidos,
        proximos=proximos,
        en_garantia=en_garantia,
        fuera_garantia=fuera_garantia,
        total_componentes=total_componentes,
        runlife_promedio=runlife_promedio,
        cambios=cambios,
    ))


@login_required
def crear_sistema_runlife(request):
    campos_permitidos = _campos_permitidos(request.user).select_related("cliente").order_by("cliente__nombre", "nombre")

    if not campos_permitidos.exists():
        messages.error(request, "No tiene campos operativos asignados para crear sistemas.")
        return redirect("runlife:dashboard")

    campo_id = request.GET.get("campo") or request.POST.get("campo")
    campo_inicial = None

    if campo_id:
        campo_inicial = campos_permitidos.filter(id=campo_id).first()
        if not campo_inicial:
            messages.error(request, "No tiene permisos para crear sistemas en este campo operativo.")
            return redirect("runlife:dashboard")

    if request.method == "POST":
        form = InjectionSystemForm(request.POST)

        if "campo" in form.fields:
            form.fields["campo"].queryset = campos_permitidos

        if form.is_valid():
            sistema = form.save(commit=False)

            if "campo" in form.fields:
                campo = form.cleaned_data.get("campo")
            else:
                campo = campo_inicial

            if not campo or not campos_permitidos.filter(id=campo.id).exists():
                messages.error(request, "Debe seleccionar un campo operativo permitido.")
                return redirect("runlife:crear_sistema")

            sistema.campo = campo
            sistema.activo = True
            sistema.save()
            form.save_m2m()

            messages.success(request, "Sistema creado correctamente.")
            return redirect("runlife:sistema_detail", sistema_id=sistema.id)

        messages.error(request, "Revise los datos del formulario.")
    else:
        initial = {}
        if campo_inicial:
            initial["campo"] = campo_inicial

        form = InjectionSystemForm(initial=initial)

        if "campo" in form.fields:
            form.fields["campo"].queryset = campos_permitidos

    return render(request, "runlife/sistema_form.html", _runlife_context(
        request,
        sidebar_subtitle="Nuevo sistema",
        form=form,
        campo_inicial=campo_inicial,
        campos_permitidos=campos_permitidos,
    ))


def _model_has_field(model, field_name):
    return any(field.name == field_name for field in model._meta.get_fields())


def _date_from_post(value):
    if not value:
        return None

    value = value.strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return timezone.datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def _tipo_requiere_unico_activo(tipo):
    """
    En un sistema solo debe existir un componente activo de estos tipos.
    Bomba queda excluida porque un sistema puede tener 2, 3 o más bombas.
    """
    return tipo in ["MOTOR", "CAMARA", "COOLER", "VSD"]


def _existe_tipo_unico_activo(sistema, tipo, excluir_id=None):
    if not _tipo_requiere_unico_activo(tipo):
        return False

    qs = SystemComponent.objects.filter(
        sistema=sistema,
        tipo=tipo,
        activo=True,
        fecha_desinstalacion__isnull=True,
    )

    if excluir_id:
        qs = qs.exclude(id=excluir_id)

    return qs.exists()


@login_required
def sistema_detail_runlife(request, sistema_id):
    user = request.user

    if user.is_staff or user.is_superuser:
        sistema = get_object_or_404(
            InjectionSystem.objects.select_related("campo", "campo__cliente"),
            id=sistema_id,
        )
    else:
        sistema = get_object_or_404(
            InjectionSystem.objects.select_related("campo", "campo__cliente"),
            id=sistema_id,
            campo__usuarios=user,
        )

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "actualizar_sistema":
            sistema.nombre = request.POST.get("nombre", sistema.nombre).strip() or sistema.nombre
            sistema.pozo = request.POST.get("pozo", sistema.pozo).strip() or sistema.pozo

            fecha_instalacion = _date_from_post(request.POST.get("fecha_instalacion"))
            if fecha_instalacion and _model_has_field(InjectionSystem, "fecha_instalacion"):
                sistema.fecha_instalacion = fecha_instalacion

            sistema.save()
            messages.success(request, "Sistema actualizado correctamente.")
            return redirect("runlife:sistema_detail", sistema_id=sistema.id)

        if accion == "instalar_desde_bodega":
            # Acción de compatibilidad: ya no se muestra como botón principal al usuario.
            # Si llega por POST, agrega un componente adicional desde bodega respetando la regla
            # de un solo MOTOR/CAMARA/COOLER/VSD activo por sistema.
            item_id = request.POST.get("bodega_item_id")
            fecha_instalacion = _date_from_post(request.POST.get("fecha_instalacion")) or timezone.localdate()

            item = get_object_or_404(
                BodegaCampoItem.objects.select_related("componente"),
                id=item_id,
                campo=sistema.campo,
                disponible=True,
            )

            if _existe_tipo_unico_activo(sistema, item.componente.tipo):
                messages.error(
                    request,
                    f"Ya existe un {item.componente.get_tipo_display()} activo en este sistema. "
                    "Use Reemplazar componente para consumir bodega sin duplicar."
                )
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            with transaction.atomic():
                item.instalar_en_sistema(sistema, fecha_instalacion=fecha_instalacion)

            messages.success(request, "Equipo agregado al sistema desde bodega correctamente.")
            return redirect("runlife:sistema_detail", sistema_id=sistema.id)

        if accion == "agregar_componente":
            bodega_item_id = request.POST.get("bodega_item_id")
            fecha_instalacion = _date_from_post(request.POST.get("fecha_instalacion")) or timezone.localdate()

            if bodega_item_id:
                item = get_object_or_404(
                    BodegaCampoItem.objects.select_related("componente"),
                    id=bodega_item_id,
                    campo=sistema.campo,
                    disponible=True,
                )

                if _existe_tipo_unico_activo(sistema, item.componente.tipo):
                    messages.error(
                        request,
                        f"Ya existe un {item.componente.get_tipo_display()} activo en este sistema. "
                        "Para este tipo debe usar Reemplazar componente, no Agregar componente."
                    )
                    return redirect("runlife:sistema_detail", sistema_id=sistema.id)

                with transaction.atomic():
                    item.instalar_en_sistema(sistema, fecha_instalacion=fecha_instalacion)

                    nuevo = item.componente
                    if _model_has_field(SystemComponent, "fecha_ultimo_mantenimiento"):
                        nuevo.fecha_ultimo_mantenimiento = None
                        nuevo.save(update_fields=["fecha_ultimo_mantenimiento", "actualizado_en"])

                messages.success(request, "Componente agregado desde bodega correctamente.")
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            tipo = request.POST.get("tipo")

            if _existe_tipo_unico_activo(sistema, tipo):
                tipo_label = dict(SystemComponent.TIPO_COMPONENTE).get(tipo, tipo)
                messages.error(
                    request,
                    f"Ya existe un {tipo_label} activo en este sistema. "
                    "Para Motor, Cámara, Cooler y VSD debe usar Reemplazar componente. "
                    "Solo Bomba permite varios componentes activos."
                )
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            nuevo_data = {
                "sistema": sistema,
                "tipo": tipo,
                "descripcion": request.POST.get("descripcion"),
                "marca": request.POST.get("marca"),
                "modelo": request.POST.get("modelo"),
                "serial": request.POST.get("serial"),
                "parte_numero": request.POST.get("parte_numero"),
                "fecha_instalacion": fecha_instalacion,
                "fecha_ultimo_mantenimiento": request.POST.get("fecha_ultimo_mantenimiento") or None,
                "activo": True,
            }

            if _model_has_field(SystemComponent, "origen"):
                nuevo_data["origen"] = request.POST.get("origen") or "CLIENTE"
            if _model_has_field(SystemComponent, "fecha_entrega_cliente"):
                nuevo_data["fecha_entrega_cliente"] = request.POST.get("fecha_entrega_cliente") or None
            if _model_has_field(SystemComponent, "fabricado_por_nosotros"):
                nuevo_data["fabricado_por_nosotros"] = request.POST.get("fabricado_por_nosotros") == "on"
            if _model_has_field(SystemComponent, "reparado_por_nosotros"):
                nuevo_data["reparado_por_nosotros"] = request.POST.get("reparado_por_nosotros") == "on"
            if _model_has_field(SystemComponent, "fecha_garantia_inicio"):
                nuevo_data["fecha_garantia_inicio"] = request.POST.get("fecha_garantia_inicio") or nuevo_data["fecha_instalacion"]
            if _model_has_field(SystemComponent, "dias_garantia"):
                nuevo_data["dias_garantia"] = request.POST.get("dias_garantia") or 365

            SystemComponent.objects.create(**nuevo_data)

            messages.success(request, "Componente agregado correctamente.")
            return redirect("runlife:sistema_detail", sistema_id=sistema.id)

        if accion == "actualizar_mantenimiento":
            componente_id = request.POST.get("componente_id")
            componente = get_object_or_404(
                SystemComponent,
                id=componente_id,
                sistema=sistema,
                activo=True,
                fecha_desinstalacion__isnull=True,
            )

            fecha_realizada = _date_from_post(request.POST.get("fecha_mantenimiento_realizado"))

            if not componente.regla_mantenimiento:
                messages.error(
                    request,
                    "No se puede calcular el próximo mantenimiento porque este componente no tiene regla configurada."
                )
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            if not fecha_realizada:
                messages.error(request, "Debe ingresar la fecha del mantenimiento realizado.")
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            if hasattr(componente, "registrar_mantenimiento"):
                componente.registrar_mantenimiento(fecha_realizada=fecha_realizada)
            elif _model_has_field(SystemComponent, "fecha_ultimo_mantenimiento"):
                componente.fecha_ultimo_mantenimiento = fecha_realizada
                componente.save(update_fields=["fecha_ultimo_mantenimiento", "actualizado_en"])
            else:
                messages.error(
                    request,
                    "Falta agregar el campo fecha_ultimo_mantenimiento en el modelo SystemComponent."
                )
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            messages.success(
                request,
                f"Mantenimiento actualizado. Próximo mantenimiento calculado: {componente.fecha_proximo_mantenimiento}."
            )
            return redirect("runlife:sistema_detail", sistema_id=sistema.id)

        if accion == "reemplazar_componente":
            componente_id = request.POST.get("componente_actual")
            comp = get_object_or_404(
                SystemComponent,
                id=componente_id,
                sistema=sistema,
                activo=True,
                fecha_desinstalacion__isnull=True,
            )

            fecha_cambio = _date_from_post(request.POST.get("fecha_cambio")) or timezone.localdate()
            bodega_item_id = request.POST.get("bodega_item_id")
            nuevo_serial = request.POST.get("nuevo_serial", "").strip()
            nuevo_modelo = request.POST.get("nuevo_modelo", "").strip()
            nuevo_parte = request.POST.get("nuevo_parte", "").strip()
            motivo_cambio = request.POST.get("motivo_cambio", "").strip()

            runlife_anterior = comp.runlife_dias

            with transaction.atomic():
                if bodega_item_id:
                    item = get_object_or_404(
                        BodegaCampoItem.objects.select_related("componente"),
                        id=bodega_item_id,
                        campo=sistema.campo,
                        disponible=True,
                    )

                    nuevo = item.componente

                    if nuevo.tipo != comp.tipo:
                        messages.error(
                            request,
                            "El equipo seleccionado en bodega no coincide con el tipo del componente actual. "
                            "Para evitar duplicados, seleccione un equipo del mismo tipo."
                        )
                        return redirect("runlife:sistema_detail", sistema_id=sistema.id)

                    comp.fecha_desinstalacion = fecha_cambio
                    comp.activo = False
                    comp.save(update_fields=["fecha_desinstalacion", "activo", "actualizado_en"])

                    item.instalar_en_sistema(sistema, fecha_instalacion=fecha_cambio)

                    # El componente que viene de bodega inicia ciclo de mantenimiento desde cero
                    # salvo que luego el usuario registre un mantenimiento.
                    if _model_has_field(SystemComponent, "fecha_ultimo_mantenimiento"):
                        nuevo.fecha_ultimo_mantenimiento = None
                        nuevo.save(update_fields=["fecha_ultimo_mantenimiento", "actualizado_en"])

                else:
                    if not nuevo_serial:
                        messages.error(
                            request,
                            "Debe seleccionar un equipo de bodega o ingresar el serial del nuevo componente."
                        )
                        return redirect("runlife:sistema_detail", sistema_id=sistema.id)

                    comp.fecha_desinstalacion = fecha_cambio
                    comp.activo = False
                    comp.save(update_fields=["fecha_desinstalacion", "activo", "actualizado_en"])

                    nuevo_data = {
                        "sistema": comp.sistema,
                        "tipo": comp.tipo,
                        "descripcion": comp.descripcion,
                        "marca": comp.marca,
                        "modelo": nuevo_modelo or comp.modelo,
                        "serial": nuevo_serial,
                        "parte_numero": nuevo_parte or comp.parte_numero,
                        "fecha_instalacion": fecha_cambio,
                        "activo": True,
                    }

                    if _model_has_field(SystemComponent, "origen"):
                        nuevo_data["origen"] = request.POST.get("origen") or comp.origen
                    if _model_has_field(SystemComponent, "fecha_entrega_cliente"):
                        nuevo_data["fecha_entrega_cliente"] = request.POST.get("fecha_entrega_cliente") or None
                    if _model_has_field(SystemComponent, "fabricado_por_nosotros"):
                        nuevo_data["fabricado_por_nosotros"] = request.POST.get("fabricado_por_nosotros") == "on"
                    if _model_has_field(SystemComponent, "reparado_por_nosotros"):
                        nuevo_data["reparado_por_nosotros"] = request.POST.get("reparado_por_nosotros") == "on"
                    if _model_has_field(SystemComponent, "fecha_garantia_inicio"):
                        nuevo_data["fecha_garantia_inicio"] = request.POST.get("fecha_garantia_inicio") or fecha_cambio
                    if _model_has_field(SystemComponent, "dias_garantia"):
                        nuevo_data["dias_garantia"] = request.POST.get("dias_garantia") or 365

                    nuevo = SystemComponent.objects.create(**nuevo_data)

                log_data = {
                    "sistema": comp.sistema,
                    "componente_anterior": comp,
                    "componente_nuevo": nuevo,
                    "tipo": comp.tipo,
                    "fecha_cambio": fecha_cambio,
                    "runlife_anterior_dias": runlife_anterior,
                    "creado_por": request.user,
                }

                if _model_has_field(ComponentChangeLog, "motivo_cambio"):
                    log_data["motivo_cambio"] = motivo_cambio

                ComponentChangeLog.objects.create(**log_data)

            messages.success(request, "Componente reemplazado correctamente.")
            return redirect("runlife:sistema_detail", sistema_id=sistema.id)

    componentes_activos = SystemComponent.objects.filter(
        sistema=sistema,
        activo=True,
        fecha_desinstalacion__isnull=True,
    ).order_by("tipo", "descripcion", "serial")

    componentes_historicos = SystemComponent.objects.filter(
        sistema=sistema,
    ).exclude(
        fecha_desinstalacion__isnull=True,
        activo=True,
    ).order_by("-fecha_desinstalacion", "tipo", "serial")

    historial_cambios = ComponentChangeLog.objects.filter(
        sistema=sistema,
    ).select_related(
        "componente_anterior",
        "componente_nuevo",
        "creado_por",
    ).order_by("-fecha_cambio", "-creado_en")

    vencidos = []
    proximos = []
    en_garantia = []
    fuera_garantia = []

    for c in componentes_activos:
        if c.estado_mantenimiento == "VENCIDO":
            vencidos.append(c)
        elif c.estado_mantenimiento == "PROXIMO":
            proximos.append(c)

        if c.runlife_dias > 365:
            fuera_garantia.append(c)
        else:
            en_garantia.append(c)

    bodega_items = BodegaCampoItem.objects.select_related(
        "componente"
    ).filter(
        campo=sistema.campo,
        disponible=True
    ).order_by("componente__tipo", "componente__serial")
 
    context = {
        "sistema": sistema,
        "campo": sistema.campo,
        "componentes_activos": componentes_activos,
        "componentes_historicos": componentes_historicos,
        "historial_cambios": historial_cambios,
        "vencidos": vencidos,
        "proximos": proximos,
        "en_garantia": en_garantia,
        "fuera_garantia": fuera_garantia,
        "total_componentes": componentes_activos.count(),
        "total_alertas": len(proximos) + len(vencidos),
        "sidebar_subtitle": sistema.campo.cliente.nombre,
        "bodega_items": bodega_items,
         
    }

    context.update(_runlife_context(request, sidebar_subtitle=sistema.campo.cliente.nombre))
    return render(request, "runlife/sistema_detail.html", context)



@login_required
def clientes_runlife(request):
    clientes = _clientes_permitidos(request.user).prefetch_related("campos")
    campos = _campos_permitidos(request.user).select_related("cliente").order_by("cliente__nombre", "nombre")

    resumen = []
    for cliente in clientes:
        campos_cliente = [campo for campo in campos if campo.cliente_id == cliente.id]
        sistemas_count = InjectionSystem.objects.filter(
            campo__in=campos_cliente,
            activo=True,
        ).count()
        componentes_count = SystemComponent.objects.filter(
            sistema__campo__in=campos_cliente,
            activo=True,
            fecha_desinstalacion__isnull=True,
        ).count()
        resumen.append({
            "cliente": cliente,
            "campos": campos_cliente,
            "total_campos": len(campos_cliente),
            "total_sistemas": sistemas_count,
            "total_componentes": componentes_count,
        })

    return render(request, "runlife/clientes.html", _runlife_context(
        request,
        sidebar_subtitle="Clientes",
        clientes_data=resumen,
    ))


@login_required
def componentes_runlife(request):
    campos = _campos_permitidos(request.user)
    componentes = SystemComponent.objects.select_related(
        "sistema", "sistema__campo", "sistema__campo__cliente"
    ).filter(
        sistema__campo__in=campos,
        activo=True,
        fecha_desinstalacion__isnull=True,
    ).order_by("sistema__campo__nombre", "sistema__nombre", "tipo", "serial")

    return render(request, "runlife/componentes.html", _runlife_context(
        request,
        sidebar_subtitle="Componentes",
        componentes=componentes,
    ))


@login_required
def historial_runlife(request):
    campos = _campos_permitidos(request.user)
    cambios = ComponentChangeLog.objects.select_related(
        "sistema", "sistema__campo", "sistema__campo__cliente", "componente_anterior", "componente_nuevo", "creado_por"
    ).filter(
        sistema__campo__in=campos,
    ).order_by("-fecha_cambio", "-creado_en")[:200]

    return render(request, "runlife/historial.html", _runlife_context(
        request,
        sidebar_subtitle="Historial",
        cambios=cambios,
    ))


@login_required
def reportes_runlife(request):
    campos = _campos_permitidos(request.user)
    componentes = SystemComponent.objects.select_related(
        "sistema", "sistema__campo", "sistema__campo__cliente"
    ).filter(
        sistema__campo__in=campos,
        activo=True,
        fecha_desinstalacion__isnull=True,
    )

    total_componentes = componentes.count()
    vencidos = []
    proximos = []
    en_garantia = []
    fuera_garantia = []

    for c in componentes:
        if c.estado_mantenimiento == "VENCIDO":
            vencidos.append(c)
        elif c.estado_mantenimiento == "PROXIMO":
            proximos.append(c)

        if c.runlife_dias > 365:
            fuera_garantia.append(c)
        else:
            en_garantia.append(c)

    return render(request, "runlife/reportes.html", _runlife_context(
        request,
        sidebar_subtitle="Reportes",
        total_campos=campos.count(),
        total_componentes=total_componentes,
        vencidos=vencidos,
        proximos=proximos,
        en_garantia=en_garantia,
        fuera_garantia=fuera_garantia,
    ))
