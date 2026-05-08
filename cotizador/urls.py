from . import views
from django.urls import path
from .views import (
    home_view,
    cotizador_view,
    historial_cotizaciones,
    descargar_pdf,
    enviar_cotizacion_email,
    reparacion_camara_view,
    solicitar_precio_reparacion,
    diagnostico_variador_view,
    importar_diagnostico_variador_view,
    importar_reparacion_camara_view,
    CustomLoginView,
)

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", home_view, name="home"),
    path("cotizador-bombas/", cotizador_view, name="cotizador"),
    path("reparacion-camara/", reparacion_camara_view, name="reparacion_camara"),
    path("reparacion-camara/importar/", importar_reparacion_camara_view, name="importar_reparacion_camara"),
    path("historial/", historial_cotizaciones, name="historial_cotizaciones"),
    path("pdf/<int:solicitud_id>/", descargar_pdf, name="descargar_pdf"),
    path("enviar-email/<int:solicitud_id>/", enviar_cotizacion_email, name="enviar_cotizacion_email"),
    path("solicitar-precio-reparacion/<int:solicitud_id>/", solicitar_precio_reparacion, name="solicitar_precio_reparacion"),
    path("diagnostico-variador/", diagnostico_variador_view, name="diagnostico_variador"),
    path("diagnostico-variador/importar/", importar_diagnostico_variador_view, name="importar_diagnostico_variador"),
    path("crear-cuenta/", views.crear_cuenta, name="crear_cuenta"),
]
