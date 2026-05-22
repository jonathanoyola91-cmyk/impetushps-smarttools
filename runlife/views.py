from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import (
    ClientAccount,
    FieldLocation,
    InjectionSystem,
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
from django.http import HttpResponse
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


def _runlife_context(request, sidebar_subtitle="RunLife", **extra):
    """Contexto base para que base_runlife.html siempre conozca permisos del usuario."""
    puede = _puede_gestionar_reglas(request.user)
    context = {
        "puede_reglas": puede,
        "puede_gestionar_reglas": puede,
        "sidebar_subtitle": sidebar_subtitle,
    }
    context.update(extra)
    return context


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

    return render(request, "runlife/campo_detail.html", _runlife_context(
        request,
        sidebar_subtitle=campo.cliente.nombre,
        campo=campo,
        sistemas=sistemas,
        sistemas_base=sistemas_base,
        sistema_id=sistema_id,
        componentes=componentes,
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



        if accion == "agregar_componente":
            SystemComponent.objects.create(
                sistema=sistema,
                tipo=request.POST.get("tipo"),
                descripcion=request.POST.get("descripcion"),
                marca=request.POST.get("marca"),
                modelo=request.POST.get("modelo"),
                serial=request.POST.get("serial"),
                parte_numero=request.POST.get("parte_numero"),
                fecha_instalacion=request.POST.get("fecha_instalacion") or None,
                fecha_ultimo_mantenimiento=request.POST.get("fecha_ultimo_mantenimiento") or None,
                activo=True,
            )

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
            nuevo_serial = request.POST.get("nuevo_serial", "").strip()
            nuevo_modelo = request.POST.get("nuevo_modelo", "").strip()
            nuevo_parte = request.POST.get("nuevo_parte", "").strip()
            motivo_cambio = request.POST.get("motivo_cambio", "").strip()

            if not nuevo_serial:
                messages.error(request, "Debe ingresar el serial del nuevo componente.")
                return redirect("runlife:sistema_detail", sistema_id=sistema.id)

            runlife_anterior = comp.runlife_dias

            comp.fecha_desinstalacion = fecha_cambio
            comp.activo = False
            comp.save()

            nuevo = SystemComponent.objects.create(
                sistema=comp.sistema,
                tipo=comp.tipo,
                descripcion=comp.descripcion,
                marca=comp.marca,
                modelo=nuevo_modelo or comp.modelo,
                serial=nuevo_serial,
                parte_numero=nuevo_parte or comp.parte_numero,
                fecha_instalacion=fecha_cambio,
                activo=True,
            )

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
