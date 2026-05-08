from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import admin
from .models import ReparacionCamaraTarifa, SolicitudReparacionCamara

from .models import (
    Acople,
    Conexion,
    CurvaOperacion,
    EquipoBase,
    MarcaMotor,
    OpcionMotor,
    SolicitudCotizacion,
    Variador,
)


@admin.register(EquipoBase)
class EquipoBaseAdmin(admin.ModelAdmin):
    list_display = (
        "id_equipo",
        "nombre_equipo",
        "bomba",
        "potencia_hp_min",
        "potencia_hp_max",
        "caudal_min_bpd",
        "caudal_max_bpd",
        "activo",
    )
    search_fields = ("id_equipo", "nombre_equipo", "bomba")
    list_filter = ("activo",)
    ordering = ("id_equipo",)


@admin.register(CurvaOperacion)
class CurvaOperacionAdmin(admin.ModelAdmin):
    list_display = (
        "id_punto",
        "equipo",
        "caudal",
        "dp_requerida",
        "potencia_hp",
        "carga_camara",
        "eficiencia_pct",
        "tipo_punto",
    )
    search_fields = ("id_punto", "equipo__id_equipo", "equipo__nombre_equipo")
    list_filter = ("tipo_punto", "equipo")
    ordering = ("equipo__id_equipo", "caudal")


@admin.register(MarcaMotor)
class MarcaMotorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)


@admin.register(OpcionMotor)
class OpcionMotorAdmin(admin.ModelAdmin):
    list_display = (
        "equipo",
        "marca",
        "potencia_hp",
        "voltaje",
        "precio_adicional",
        "tiempo_adicional_dias",
        "disponible",
    )
    search_fields = ("equipo__id_equipo", "marca__nombre", "voltaje")
    list_filter = ("disponible", "marca")


@admin.register(Acople)
class AcopleAdmin(admin.ModelAdmin):
    list_display = ("nombre", "precio_adicional", "tiempo_adicional_dias", "disponible")
    search_fields = ("nombre",)
    list_filter = ("disponible",)


@admin.register(Variador)
class VariadorAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "potencia_hp_min",
        "potencia_hp_max",
        "precio_adicional",
        "tiempo_adicional_dias",
        "disponible",
    )
    search_fields = ("nombre",)
    list_filter = ("disponible",)


@admin.register(Conexion)
class ConexionAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "diametro",
        "ansi",
        "precio_adicional",
        "tiempo_adicional_dias",
        "disponible",
    )
    search_fields = ("diametro", "ansi")
    list_filter = ("tipo", "disponible")


@admin.register(SolicitudCotizacion)
class SolicitudCotizacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "empresa",
        "contacto",
        "correo",
        "caudal",
        "presion_succion",
        "presion_descarga",
        "dp_calculada",
        "equipo_recomendado",
        "valor_estimado",
        "tiempo_entrega_estimado_dias",
        "created_at",
    )
    search_fields = ("empresa", "contacto", "correo")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)

@admin.register(ReparacionCamaraTarifa)
class ReparacionCamaraTarifaAdmin(admin.ModelAdmin):
    list_display = (
        "marca",
        "modelo",
        "tipo_reparacion",
        "valor_estimado",
        "tiempo_estimado_texto",
        "activo",
    )
    search_fields = ("marca", "modelo")
    list_filter = ("tipo_reparacion", "activo")


@admin.register(SolicitudReparacionCamara)
class SolicitudReparacionCamaraAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "empresa",
        "contacto",
        "marca",
        "modelo",
        "tipo_reparacion",
        "valor_estimado",
        "tiempo_estimado_texto",
        "created_at",
    )
    search_fields = ("empresa", "contacto", "marca", "modelo", "serial")
    list_filter = ("tipo_reparacion", "created_at")

@admin.action(description="Activar usuarios seleccionados y notificar")
def activar_usuarios(modeladmin, request, queryset):

    for user in queryset:
        user.is_active = True
        user.save()

        if user.email:
            send_mail(
                "Cuenta aprobada - IMPETUS Smart Tools",
                f"""
Hola {user.first_name or user.username},

Su cuenta fue aprobada correctamente.

Ya puede ingresar a IMPETUS Smart Tools.

Usuario:
{user.username}

URL:
https://SU-DOMINIO/login/

IMPETUS HPS
""",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )


from django.contrib.auth.admin import UserAdmin

admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    actions = [activar_usuarios]