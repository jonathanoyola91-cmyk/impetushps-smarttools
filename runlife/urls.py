from django.urls import path
from . import views

app_name = "runlife"

urlpatterns = [
    path("", views.dashboard_runlife, name="dashboard"),
    path("garantias/", views.dashboard_garantias, name="dashboard_garantias"),
    path("mtbf/", views.dashboard_mtbf, name="dashboard_mtbf"),
    path("campo/<int:campo_id>/", views.campo_detail, name="campo_detail"),

    path("sistema/nuevo/", views.crear_sistema_runlife, name="crear_sistema"),
    path("sistema/<int:sistema_id>/", views.sistema_detail_runlife, name="sistema_detail"),
    path("sistema/<int:sistema_id>/monitoreo/", views.monitoreo_sistema, name="monitoreo"),

    path("clientes/", views.clientes_runlife, name="clientes"),
    path("componentes/", views.componentes_runlife, name="componentes"),
    path("historial/", views.historial_runlife, name="historial"),
    path("reportes/", views.reportes_runlife, name="reportes"),

    path("reglas/", views.reglas_mantenimiento, name="reglas"),
    path("reglas/nueva/", views.crear_regla_mantenimiento, name="crear_regla"),
    path("reglas/<int:regla_id>/editar/", views.editar_regla_mantenimiento, name="editar_regla"),
    path("limites-operativos/", views.limites_operativos, name="limites_operativos"),
    path("limites-operativos/nuevo/", views.crear_limite_operativo, name="crear_limite_operativo"),
    path("limites-operativos/<int:limite_id>/editar/", views.editar_limite_operativo, name="editar_limite_operativo"),
    path("sistemas-por-campo/<int:campo_id>/", views.sistemas_por_campo, name="sistemas_por_campo"),
    path("sistema/<int:sistema_id>/monitoreo/pdf/",views.monitoreo_pdf,name="monitoreo_pdf"),
    path("componentes/importar-excel/", views.importar_componentes_excel, name="importar_componentes_excel"),
]