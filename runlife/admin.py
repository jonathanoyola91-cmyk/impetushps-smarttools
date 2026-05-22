from django.contrib import admin

from .models import (
    ClientAccount,
    FieldLocation,
    InjectionSystem,
    SystemComponent,
    ComponentChangeLog,
    MaintenanceRule,
)

@admin.register(MaintenanceRule)
class MaintenanceRuleAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "cliente",
        "campo",
        "horas_mantenimiento",
        "dias_mantenimiento",
        "alerta_porcentaje",
        "activo",
    )
    list_filter = ("tipo", "cliente", "campo", "activo")
    search_fields = ("cliente__nombre", "campo__nombre", "tipo")

@admin.register(ClientAccount)
class ClientAccountAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    filter_horizontal = ("usuarios",)


class InjectionSystemInline(admin.TabularInline):
    model = InjectionSystem
    extra = 0
    fields = ("nombre", "pozo", "activo")
    show_change_link = True


@admin.register(FieldLocation)
class FieldLocationAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cliente", "ubicacion", "activo")
    list_filter = ("cliente", "activo")
    search_fields = ("nombre", "cliente__nombre", "ubicacion")
    filter_horizontal = ("usuarios",)
    inlines = [InjectionSystemInline]


class SystemComponentInline(admin.TabularInline):
    model = SystemComponent
    extra = 0
    fields = (
        "tipo",
        "descripcion",
        "marca",
        "modelo",
        "serial",
        "parte_numero",
        "fecha_reparacion",
        "fecha_instalacion",
        "fecha_desinstalacion",
        "activo",
    )
    show_change_link = True


@admin.register(InjectionSystem)
class InjectionSystemAdmin(admin.ModelAdmin):
    list_display = ("nombre", "campo", "cliente_nombre", "pozo", "activo")
    list_filter = ("campo__cliente", "campo", "activo")
    search_fields = (
        "nombre",
        "pozo",
        "campo__nombre",
        "campo__cliente__nombre",
    )
    inlines = [SystemComponentInline]

    def cliente_nombre(self, obj):
        return obj.campo.cliente.nombre

    cliente_nombre.short_description = "Cliente"


@admin.register(SystemComponent)
class SystemComponentAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "serial",
        "sistema",
        "cliente_nombre",
        "fecha_instalacion",
        "fecha_desinstalacion",
        "runlife_dias",
        "fecha_proximo_mantenimiento",
        "estado_mantenimiento",
        "en_garantia",
        "activo",
    )
    list_filter = (
        "tipo",
        "activo",
        "sistema__campo__cliente",
        "sistema__campo",
    )
    search_fields = (
        "serial",
        "modelo",
        "marca",
        "parte_numero",
        "sistema__nombre",
        "sistema__campo__nombre",
        "sistema__campo__cliente__nombre",
    )
    readonly_fields = (
        "runlife_dias",
        "fecha_proximo_mantenimiento",
        "dias_para_mantenimiento",
        "estado_mantenimiento",
        "en_garantia",
        "creado_en",
        "actualizado_en",
    )

    fieldsets = (
        ("Ubicación del componente", {
            "fields": ("sistema", "tipo", "activo")
        }),
        ("Identificación", {
            "fields": (
                "descripcion",
                "marca",
                "modelo",
                "serial",
                "parte_numero",
            )
        }),
        ("Fechas", {
            "fields": (
                "fecha_reparacion",
                "fecha_instalacion",
                "fecha_desinstalacion",
            )
        }),
        ("Cálculos automáticos", {
            "fields": (
                "runlife_dias",
                "fecha_proximo_mantenimiento",
                "dias_para_mantenimiento",
                "estado_mantenimiento",
                "en_garantia",
            )
        }),
        ("Observaciones", {
            "fields": ("observaciones",)
        }),
        ("Auditoría", {
            "fields": ("creado_en", "actualizado_en"),
            "classes": ("collapse",),
        }),
    )

    def cliente_nombre(self, obj):
        return obj.sistema.campo.cliente.nombre

    cliente_nombre.short_description = "Cliente"


@admin.register(ComponentChangeLog)
class ComponentChangeLogAdmin(admin.ModelAdmin):
    list_display = (
        "sistema",
        "tipo",
        "fecha_cambio",
        "componente_anterior",
        "componente_nuevo",
        "runlife_anterior_dias",
        "creado_por",
    )
    list_filter = (
        "tipo",
        "sistema__campo__cliente",
        "fecha_cambio",
    )
    search_fields = (
        "sistema__nombre",
        "sistema__campo__nombre",
        "sistema__campo__cliente__nombre",
        "componente_anterior__serial",
        "componente_nuevo__serial",
    )
    readonly_fields = ("creado_en",)

    def save_model(self, request, obj, form, change):
        if not obj.creado_por:
            obj.creado_por = request.user

        if obj.componente_anterior and not obj.runlife_anterior_dias:
            obj.runlife_anterior_dias = obj.componente_anterior.runlife_dias

        super().save_model(request, obj, form, change)