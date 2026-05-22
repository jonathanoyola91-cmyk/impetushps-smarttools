from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class OperationalLimit(models.Model):
    campo = models.ForeignKey(
        "runlife.FieldLocation",
        on_delete=models.CASCADE,
        related_name="limites_operativos"
    )

    sistema = models.ForeignKey(
        "runlife.InjectionSystem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="limites_operativos"
    )

    nombre = models.CharField(max_length=120, default="Límites estándar")

    vib_alerta = models.FloatField(default=4.5)
    vib_critico = models.FloatField(default=7.0)

    temp_alerta = models.FloatField(default=75.0)
    temp_critico = models.FloatField(default=90.0)

    dp_alerta = models.FloatField(default=300.0)
    dp_critico = models.FloatField(default=0.0)

    presion_succion_min = models.FloatField(null=True, blank=True)
    presion_succion_max = models.FloatField(null=True, blank=True)

    presion_descarga_min = models.FloatField(null=True, blank=True)
    presion_descarga_max = models.FloatField(null=True, blank=True)

    caudal_min = models.FloatField(null=True, blank=True)
    caudal_max = models.FloatField(null=True, blank=True)

    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.campo} - {self.nombre}"

class OperationalMonitoring(models.Model):

    sistema = models.ForeignKey(
        "runlife.InjectionSystem",
        on_delete=models.CASCADE,
        related_name="monitoreos"
    )

    fecha = models.DateField(default=timezone.localdate)
    hora = models.TimeField(default=timezone.now)

    frecuencia = models.FloatField(blank=True, null=True)
    corriente_motor = models.FloatField(blank=True, null=True)
    voltaje_motor = models.FloatField(blank=True, null=True)
    kw = models.FloatField(blank=True, null=True)

    presion_succion = models.FloatField(blank=True, null=True)
    presion_descarga = models.FloatField(blank=True, null=True)

    caudal = models.FloatField(blank=True, null=True)
    temperatura_camara = models.FloatField(blank=True, null=True)
    vibracion_camara = models.FloatField(blank=True, null=True)

    vibracion_bomba1 = models.FloatField(blank=True, null=True)
    vibracion_bomba2 = models.FloatField(blank=True, null=True)
    vibracion_bomba3 = models.FloatField(blank=True, null=True)
    vibracion_bomba4 = models.FloatField(blank=True, null=True)

    bomba3_aplica = models.BooleanField(default=True)
    bomba4_aplica = models.BooleanField(default=True)

    observaciones = models.TextField(blank=True, null=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-hora"]

    def __str__(self):
        return f"{self.sistema} - {self.fecha} {self.hora}"

    @property
    def diferencial_presion(self):
        if self.presion_succion is not None and self.presion_descarga is not None:
            return self.presion_descarga - self.presion_succion
        return None

    @property
    def observacion_auto_promedio(self):
        anteriores = (
            OperationalMonitoring.objects
            .filter(sistema=self.sistema)
            .exclude(pk=self.pk)
            .order_by("-fecha", "-hora")[:5]
        )

        anteriores = list(anteriores)

        if not anteriores:
            return "Primer registro. Sin histórico."

        def promedio(campo):
            vals = [
                getattr(m, campo)
                for m in anteriores
                if getattr(m, campo) is not None
            ]
            return sum(vals) / len(vals) if vals else None

        mensajes = []

        prom_caudal = promedio("caudal")
        prom_temp = promedio("temperatura_camara")
        prom_vib = promedio("vibracion_camara")

        if prom_caudal and self.caudal:
            if self.caudal > prom_caudal * 1.1:
                mensajes.append("Caudal superior al promedio.")
            elif self.caudal < prom_caudal * 0.9:
                mensajes.append("Caudal inferior al promedio.")

        if prom_temp and self.temperatura_camara:
            if self.temperatura_camara > prom_temp + 5:
                mensajes.append("Temperatura elevada frente al promedio.")

        if prom_vib and self.vibracion_camara:
            if self.vibracion_camara > prom_vib + 1:
                mensajes.append("Vibración aumentada frente al promedio.")

        if self.estado_thrust == "UP_THRUST":
            mensajes.append("UP THRUST detectado.")
        elif self.estado_thrust == "DOWN_THRUST":
            mensajes.append("DOWN THRUST detectado.")

        return " ".join(mensajes) if mensajes else "Operación normal."

    @property
    def diagnostico_avanzado(self):
        diagnosticos = []

        limite = self.limite_operativo
        dp = self.diferencial_presion

        # 1. Posible cavitación / baja succión
        if self.presion_succion is not None:
            if self.presion_succion <= 20:
                diagnosticos.append(
                    "Posible restricción en succión o condición cercana a cavitación. Revisar línea de succión, filtros, válvulas y nivel de fluido."
                )

        # 2. Alta descarga
        if limite and self.presion_descarga is not None and limite.presion_descarga_max is not None:
            if self.presion_descarga > limite.presion_descarga_max:
                diagnosticos.append(
                    "Presión de descarga por encima del límite operativo. Revisar restricción aguas abajo, válvulas parcialmente cerradas o aumento de contrapresión."
                )

        # 3. Bajo diferencial de presión
        if limite and dp is not None:
            if dp < limite.dp_alerta:
                diagnosticos.append(
                    "Diferencial de presión bajo frente al límite operativo. Posible pérdida de eficiencia hidráulica, recirculación o desgaste interno."
                )

        # 4. UP / DOWN thrust
        if self.estado_thrust == "UP_THRUST":
            diagnosticos.append(
                "Condición UP THRUST: caudal superior al rango operativo. Revisar punto de operación, frecuencia y curva de la bomba."
            )

        elif self.estado_thrust == "DOWN_THRUST":
            diagnosticos.append(
                "Condición DOWN THRUST: caudal inferior al rango operativo. Revisar baja demanda, restricción en succión o operación fuera del rango recomendado."
            )

        # 5. Vibración
        if self.alerta_vibracion == "ALERTA":
            diagnosticos.append(
                "Vibración en alerta. Revisar alineación, anclaje, rodamientos, acople y condición hidráulica."
            )

        elif self.alerta_vibracion == "CRITICO":
            diagnosticos.append(
                "Vibración crítica. Se recomienda inspección inmediata para evitar daño en bomba, motor o cámara de empuje."
            )

        # 6. Temperatura
        if self.alerta_temperatura_camara == "ALERTA":
            diagnosticos.append(
                "Temperatura de cámara elevada. Revisar lubricación, carga axial, enfriamiento y condiciones de operación."
            )

        elif self.alerta_temperatura_camara == "CRITICO":
            diagnosticos.append(
                "Temperatura crítica en cámara de empuje. Se recomienda detener o evaluar operación inmediatamente."
            )

        # 7. Tendencia por promedio
        if self.observacion_auto_promedio and self.observacion_auto_promedio != "Operación normal.":
            diagnosticos.append(self.observacion_auto_promedio)

        if not diagnosticos:
            return "Diagnóstico avanzado: operación estable, sin indicios relevantes de falla operacional."

        return " ".join(diagnosticos)
 
    # -------------------------
    # KPIs
    # -------------------------

    @property
    def diferencial_presion(self):
        if self.presion_succion is not None and self.presion_descarga is not None:
            return self.presion_descarga - self.presion_succion
        return None

    # -------------------------
    # LÍMITES
    # -------------------------

    @property
    def limite_operativo(self):
        from .models import OperationalLimit

        limite = OperationalLimit.objects.filter(
            sistema=self.sistema,
            activo=True
        ).first()

        if limite:
            return limite

        return OperationalLimit.objects.filter(
            campo=self.sistema.campo,
            activo=True
        ).first()

    # -------------------------
    # THRUST
    # -------------------------

    @property
    def estado_thrust(self):
        limite = self.limite_operativo

        if not limite:
            return "SIN_LIMITES"

        if self.presion_descarga is None or self.caudal is None:
            return "SIN_DATOS"

        if limite.caudal_min is not None and self.caudal < limite.caudal_min:
            return "DOWN_THRUST"

        if limite.caudal_max is not None and self.caudal > limite.caudal_max:
            return "UP_THRUST"

        if limite.presion_descarga_max is not None and self.presion_descarga > limite.presion_descarga_max:
            return "ALTA_DESCARGA"

        if limite.presion_descarga_min is not None and self.presion_descarga < limite.presion_descarga_min:
            return "BAJA_DESCARGA"

        return "NORMAL"

    # -------------------------
    # ALERTAS
    # -------------------------

    @property
    def alerta_vibracion(self):
        limite = self.limite_operativo

        if not limite:
            return "OK"

        valores = [
            self.vibracion_camara,
            self.vibracion_bomba1,
            self.vibracion_bomba2,
            self.vibracion_bomba3 if self.bomba3_aplica else None,
            self.vibracion_bomba4 if self.bomba4_aplica else None,
        ]

        valores = [v for v in valores if v is not None]

        if not valores:
            return "SIN_DATOS"

        max_vib = max(valores)

        if max_vib >= limite.vib_critico:
            return "CRITICO"

        if max_vib >= limite.vib_alerta:
            return "ALERTA"

        return "OK"

    @property
    def alerta_temperatura_camara(self):
        limite = self.limite_operativo

        if not limite or self.temperatura_camara is None:
            return "SIN_DATOS"

        if self.temperatura_camara >= limite.temp_critico:
            return "CRITICO"

        if self.temperatura_camara >= limite.temp_alerta:
            return "ALERTA"

        return "OK"

    @property
    def alerta_presion(self):
        limite = self.limite_operativo
        dp = self.diferencial_presion

        if not limite or dp is None:
            return "SIN_DATOS"

        if dp <= limite.dp_critico:
            return "CRITICO"

        if dp < limite.dp_alerta:
            return "ALERTA"

        return "OK"

class MaintenanceRule(models.Model):
    TIPO_COMPONENTE = [
        ("MOTOR", "Motor"),
        ("CAMARA", "Cámara de Empuje"),
        ("BOMBA", "Bomba"),
        ("COOLER", "Cooler"),
        ("VSD", "Variador / VSD"),
        ("OTRO", "Otro"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_COMPONENTE)

    cliente = models.ForeignKey(
        "ClientAccount",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="reglas_mantenimiento"
    )

    campo = models.ForeignKey(
        "FieldLocation",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="reglas_mantenimiento"
    )
     

    horas_mantenimiento = models.PositiveIntegerField(
        help_text="Cada cuántas horas se debe realizar mantenimiento"
    )

    dias_mantenimiento = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Alternativa por días. Si se deja vacío, se calcula con horas / 24."
    )

    alerta_porcentaje = models.PositiveIntegerField(
        default=80,
        help_text="Porcentaje para marcar próximo mantenimiento. Ej: 80"
    )

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["tipo", "horas_mantenimiento"]
        verbose_name = "Regla de Mantenimiento"
        verbose_name_plural = "Reglas de Mantenimiento"

    def __str__(self):
        return f"{self.get_tipo_display()} - cada {self.horas_mantenimiento} h"


class ClientAccount(models.Model):
    nombre = models.CharField(max_length=150, unique=True)

    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="clientes_runlife"
    )

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Cliente RunLife"
        verbose_name_plural = "Clientes RunLife"

    def __str__(self):
        return self.nombre


class FieldLocation(models.Model):
    cliente = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name="campos"
    )

    nombre = models.CharField(max_length=150)
    ubicacion = models.CharField(max_length=150, blank=True, null=True)

    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="campos_runlife"
    )

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["cliente__nombre", "nombre"]
        unique_together = ("cliente", "nombre")
        verbose_name = "Campo / Locación"
        verbose_name_plural = "Campos / Locaciones"

    def __str__(self):
        return f"{self.nombre} - {self.cliente.nombre}"


class InjectionSystem(models.Model):
    nombre = models.CharField(max_length=150)

    campo = models.ForeignKey(
        FieldLocation,
        on_delete=models.CASCADE,
        related_name="sistemas"
    )

    pozo = models.CharField(max_length=100, blank=True, null=True)
    fecha_instalacion = models.DateField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["campo__cliente__nombre", "campo__nombre", "nombre"]
        verbose_name = "Sistema de Inyección"
        verbose_name_plural = "Sistemas de Inyección"

    def __str__(self):
        return f"{self.nombre} - {self.campo.nombre} - {self.campo.cliente.nombre}"


class SystemComponent(models.Model):
    TIPO_COMPONENTE = [
        ("MOTOR", "Motor"),
        ("CAMARA", "Cámara de Empuje"),
        ("BOMBA", "Bomba"),
        ("COOLER", "Cooler"),
        ("VSD", "Variador / VSD"),
        ("OTRO", "Otro"),
    ]

    ORIGEN_COMPONENTE = [
        ("IMPETUS_FAB", "Fabricado por IMPETUS"),
        ("IMPETUS_REP", "Reparado por IMPETUS"),
        ("CLIENTE", "Equipo del cliente"),
    ]

    sistema = models.ForeignKey(
        InjectionSystem,
        on_delete=models.CASCADE,
        related_name="componentes",
        null=True,
        blank=True,
        help_text="Sistema donde está instalado. Puede quedar vacío cuando el componente está en bodega del campo."
    )

    tipo = models.CharField(max_length=20, choices=TIPO_COMPONENTE)
    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_COMPONENTE,
        default="CLIENTE",
        help_text="Indica si el componente fue fabricado o reparado por IMPETUS, o si pertenece al cliente."
    )
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    serial = models.CharField(max_length=100)
    parte_numero = models.CharField(max_length=100, blank=True, null=True)

    fecha_reparacion = models.DateField(blank=True, null=True)
    fecha_instalacion = models.DateField(blank=True, null=True)
    fecha_desinstalacion = models.DateField(blank=True, null=True)

    # Garantía IMPETUS.
    # Para equipos fabricados/reparados por IMPETUS, la garantía inicia desde la entrega al cliente,
    # aunque el cliente todavía no lo haya instalado en un sistema.
    fecha_entrega_cliente = models.DateField(
        blank=True,
        null=True,
        help_text="Fecha de entrega al cliente. Desde esta fecha inicia la garantía IMPETUS."
    )
    dias_garantia = models.PositiveIntegerField(
        default=365,
        help_text="Días de garantía aplicables al componente."
    )

    # Último mantenimiento realmente ejecutado.
    # Desde esta fecha se calcula automáticamente el próximo mantenimiento según la regla.
    fecha_ultimo_mantenimiento = models.DateField(blank=True, null=True)

    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True, null=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sistema", "tipo", "-activo", "serial"]
        verbose_name = "Componente del Sistema"
        verbose_name_plural = "Componentes del Sistema"

    def __str__(self):
        estado = "Activo" if self.activo else "Histórico"
        return f"{self.get_tipo_display()} - {self.serial} - {estado}"

    def save(self, *args, **kwargs):
        if self.fecha_desinstalacion:
            self.activo = False
        super().save(*args, **kwargs)

    @property
    def runlife_dias(self):
        if not self.fecha_instalacion:
            return 0

        fecha_final = self.fecha_desinstalacion or timezone.localdate()
        return max((fecha_final - self.fecha_instalacion).days, 0)

    @property
    def horas_desde_instalacion(self):
        return self.runlife_dias * 24

    @property
    def regla_mantenimiento(self):
        qs = MaintenanceRule.objects.filter(
            tipo=self.tipo,
            activo=True
        )

        campo = getattr(self.sistema, "campo", None)
        cliente = getattr(campo, "cliente", None) if campo else None

        # 1) Regla específica por cliente + campo
        if cliente and campo:
            regla = qs.filter(cliente=cliente, campo=campo).first()
            if regla:
                return regla

        # 2) Regla por cliente
        if cliente:
            regla = qs.filter(cliente=cliente, campo__isnull=True).first()
            if regla:
                return regla

        # 3) Regla global por tipo
        return qs.filter(cliente__isnull=True, campo__isnull=True).first()

    @property
    def horas_para_mantenimiento(self):
        regla = self.regla_mantenimiento

        if not regla:
            return None

        return regla.horas_mantenimiento

    @property
    def fecha_base_mantenimiento(self):
        # Primero usa la fecha del último mantenimiento realizado.
        # Si nunca se ha registrado mantenimiento, usa la instalación.
        return self.fecha_ultimo_mantenimiento or self.fecha_instalacion

    @property
    def dias_regla_mantenimiento(self):
        regla = self.regla_mantenimiento

        if not regla:
            return None

        if regla.dias_mantenimiento:
            return regla.dias_mantenimiento

        return round(regla.horas_mantenimiento / 24)

    @property
    def horas_desde_ultimo_mantenimiento(self):
        if not self.fecha_base_mantenimiento:
            return 0

        return max((timezone.localdate() - self.fecha_base_mantenimiento).days, 0) * 24

    @property
    def horas_restantes_mantenimiento(self):
        regla = self.regla_mantenimiento

        if not regla:
            return None

        return regla.horas_mantenimiento - self.horas_desde_ultimo_mantenimiento

    @property
    def fecha_proximo_mantenimiento(self):
        regla = self.regla_mantenimiento

        # Sin regla NO se calcula fecha automática.
        # La interfaz debe indicar que se debe crear una regla para este componente.
        if not regla:
            return None

        if not self.fecha_base_mantenimiento:
            return None

        dias = self.dias_regla_mantenimiento
        if dias is None:
            return None

        return self.fecha_base_mantenimiento + timedelta(days=dias)

    @property
    def dias_para_mantenimiento(self):
        proximo = self.fecha_proximo_mantenimiento

        if not proximo:
            return None

        return (proximo - timezone.localdate()).days

    @property
    def estado_mantenimiento(self):
        regla = self.regla_mantenimiento

        if not regla:
            return "SIN_REGLA"

        if not self.fecha_base_mantenimiento:
            return "SIN_FECHA"

        proximo = self.fecha_proximo_mantenimiento

        if not proximo:
            return "SIN_FECHA"

        hoy = timezone.localdate()

        if proximo < hoy:
            return "VENCIDO"

        dias_restantes = (proximo - hoy).days
        dias_regla = self.dias_regla_mantenimiento or 0

        porcentaje_alerta = regla.alerta_porcentaje or 80
        dias_alerta = round(dias_regla * ((100 - porcentaje_alerta) / 100))
        dias_alerta = max(dias_alerta, 1)

        if dias_restantes <= dias_alerta:
            return "PROXIMO"

        return "OK"

    @property
    def en_garantia(self):
        if not self.fecha_instalacion:
            return False

        return self.runlife_dias <= 365


    @property
    def es_impetus(self):
        return self.origen in ["IMPETUS_FAB", "IMPETUS_REP"]

    @property
    def tipo_garantia_interno(self):
        if self.origen == "IMPETUS_FAB":
            return "Fabricado por IMPETUS"
        if self.origen == "IMPETUS_REP":
            return "Reparado por IMPETUS"
        return "Equipo del cliente"

    @property
    def fecha_inicio_garantia_calc(self):
        # La garantía comercial inicia desde entrega al cliente.
        # Se deja respaldo con fecha_instalacion/fecha_reparacion para registros antiguos.
        return self.fecha_entrega_cliente or self.fecha_instalacion or self.fecha_reparacion

    @property
    def runlife_garantia_dias(self):
        if not self.fecha_inicio_garantia_calc:
            return None

        fecha_final = self.fecha_desinstalacion or timezone.localdate()
        return max((fecha_final - self.fecha_inicio_garantia_calc).days, 0)

    @property
    def dias_garantia_transcurridos(self):
        if not self.fecha_entrega_cliente:
            return None
        return max((timezone.localdate() - self.fecha_entrega_cliente).days, 0)

    @property
    def en_garantia_interna(self):
        if not self.es_impetus:
            return False

        dias = self.runlife_garantia_dias
        if dias is None:
            return False

        return dias <= (self.dias_garantia or 365)

    @property
    def en_garantia_real(self):
        return self.en_garantia_interna

    @property
    def dias_restantes_garantia(self):
        dias = self.runlife_garantia_dias
        if dias is None:
            return None
        return (self.dias_garantia or 365) - dias

    @property
    def dias_vencidos_garantia(self):
        restantes = self.dias_restantes_garantia
        if restantes is None or restantes >= 0:
            return 0
        return abs(restantes)

    @property
    def es_marca_impetus(self):
        return bool(self.marca and "IMPETUS" in self.marca.upper())

    @property
    def estado_garantia_interna(self):
        if not self.es_impetus and not self.es_marca_impetus:
            return "NO_APLICA"
        if not self.fecha_inicio_garantia_calc:
            return "SIN_FECHA"
        if self.en_garantia_interna:
            return "EN_GARANTIA"
        return "FUERA_GARANTIA"

    def registrar_mantenimiento(self, fecha_realizada=None):
        self.fecha_ultimo_mantenimiento = fecha_realizada or timezone.localdate()
        self.save(update_fields=["fecha_ultimo_mantenimiento", "actualizado_en"])


class BodegaCampoItem(models.Model):
    campo = models.ForeignKey(
        "runlife.FieldLocation",
        on_delete=models.CASCADE,
        related_name="bodega_items"
    )

    componente = models.OneToOneField(
        "runlife.SystemComponent",
        on_delete=models.CASCADE,
        related_name="bodega_item"
    )

    fecha_entrega_cliente = models.DateField(
        default=timezone.localdate,
        help_text="Fecha en que el componente reparado/fabricado fue entregado al cliente."
    )
    fecha_ingreso_bodega = models.DateField(default=timezone.localdate)

    disponible = models.BooleanField(default=True)

    sistema_instalado = models.ForeignKey(
        "runlife.InjectionSystem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="componentes_desde_bodega"
    )

    fecha_instalacion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["campo__cliente__nombre", "campo__nombre", "-disponible", "componente__serial"]
        verbose_name = "Bodega de Campo"
        verbose_name_plural = "Bodega de Campo"

    def __str__(self):
        estado = "Disponible" if self.disponible else "Instalado"
        return f"{self.componente.serial} - {self.campo.nombre} - {estado}"

    def save(self, *args, **kwargs):
        if self.fecha_entrega_cliente and self.componente_id:
            self.componente.fecha_entrega_cliente = self.fecha_entrega_cliente
            self.componente.save(update_fields=["fecha_entrega_cliente", "actualizado_en"])
        super().save(*args, **kwargs)

    def instalar_en_sistema(self, sistema, fecha_instalacion=None):
        """
        Consume el ítem de bodega y asigna su componente al sistema.

        Se usa tanto para:
        1) Agregar un componente adicional desde bodega.
        2) Reemplazar un componente activo con un componente de bodega.

        Importante: no crea otro SystemComponent, reutiliza el componente
        asociado a bodega para evitar duplicados.
        """
        fecha = fecha_instalacion or timezone.localdate()

        self.disponible = False
        self.sistema_instalado = sistema
        self.fecha_instalacion = fecha
        self.save(update_fields=["disponible", "sistema_instalado", "fecha_instalacion"])

        componente = self.componente
        componente.sistema = sistema
        componente.fecha_instalacion = fecha
        componente.fecha_desinstalacion = None
        componente.activo = True
        componente.save(update_fields=[
            "sistema",
            "fecha_instalacion",
            "fecha_desinstalacion",
            "activo",
            "actualizado_en",
        ])


class ComponentChangeLog(models.Model):
    sistema = models.ForeignKey(
        InjectionSystem,
        on_delete=models.CASCADE,
        related_name="historial_cambios"
    )

    componente_anterior = models.ForeignKey(
        SystemComponent,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="historial_como_anterior"
    )

    componente_nuevo = models.ForeignKey(
        SystemComponent,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="historial_como_nuevo"
    )

    tipo = models.CharField(max_length=20, choices=SystemComponent.TIPO_COMPONENTE)
    fecha_cambio = models.DateField(default=timezone.localdate)
    runlife_anterior_dias = models.PositiveIntegerField(default=0)

    motivo_cambio = models.TextField(blank=True, null=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_cambio", "-creado_en"]
        verbose_name = "Historial de Cambio"
        verbose_name_plural = "Historial de Cambios"

    def __str__(self):
        return f"Cambio {self.get_tipo_display()} - {self.sistema.nombre}"