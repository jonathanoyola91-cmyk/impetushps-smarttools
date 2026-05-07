from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class EquipoBase(models.Model):
    id_equipo = models.CharField(max_length=20, unique=True)
    nombre_equipo = models.CharField(max_length=150)
    bomba = models.CharField(max_length=150)

    camara_empuje = models.CharField(max_length=100, blank=True, default="")
    carga_camara_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        null=True,
        blank=True,
    )

    curva_imagen = models.ImageField(
        upload_to="curvas_equipos/",
        null=True,
        blank=True,
    )

    longitud_total_mm = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    potencia_hp_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    potencia_hp_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    caudal_min_bpd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    caudal_max_bpd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    ps_min_psi = models.DecimalField(max_digits=10, decimal_places=2)
    ps_max_psi = models.DecimalField(max_digits=10, decimal_places=2)
    pd_min_psi = models.DecimalField(max_digits=10, decimal_places=2)
    pd_max_psi = models.DecimalField(max_digits=10, decimal_places=2)

    precio_base = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_base_dias = models.PositiveIntegerField(default=0)

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Equipo base"
        verbose_name_plural = "Equipos base"
        ordering = ["id_equipo"]

    def __str__(self):
        return f"{self.id_equipo} - {self.nombre_equipo}"


class CurvaOperacion(models.Model):
    TIPO_PUNTO_NOMINAL = "NOMINAL"
    TIPO_PUNTO_BAJA_EFICIENCIA = "BAJA_EFICIENCIA"
    TIPO_PUNTO_ALTO_CAUDAL = "ALTO_CAUDAL"

    TIPO_PUNTO_CHOICES = [
        (TIPO_PUNTO_NOMINAL, "Nominal"),
        (TIPO_PUNTO_BAJA_EFICIENCIA, "Baja eficiencia"),
        (TIPO_PUNTO_ALTO_CAUDAL, "Alto caudal"),
    ]

    id_punto = models.CharField(max_length=20, unique=True)
    equipo = models.ForeignKey(
        EquipoBase,
        on_delete=models.CASCADE,
        related_name="curvas",
    )

    caudal = models.DecimalField(max_digits=12, decimal_places=2)
    dp_requerida = models.DecimalField(max_digits=12, decimal_places=2)
    potencia_hp = models.DecimalField(max_digits=10, decimal_places=2)
    carga_camara = models.DecimalField(max_digits=12, decimal_places=2)
    eficiencia_pct = models.DecimalField(max_digits=5, decimal_places=2)

    tipo_punto = models.CharField(
        max_length=30,
        choices=TIPO_PUNTO_CHOICES,
        default=TIPO_PUNTO_NOMINAL,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Curva de operación"
        verbose_name_plural = "Curvas de operación"
        ordering = ["equipo__id_equipo", "caudal"]

    def __str__(self):
        return f"{self.id_punto} - {self.equipo.id_equipo}"


class MarcaMotor(models.Model):
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Marca de motor"
        verbose_name_plural = "Marcas de motor"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class OpcionMotor(models.Model):
    equipo = models.ForeignKey(
        EquipoBase,
        on_delete=models.CASCADE,
        related_name="opciones_motor",
    )
    marca = models.ForeignKey(
        MarcaMotor,
        on_delete=models.CASCADE,
        related_name="opciones",
    )
    potencia_hp = models.DecimalField(max_digits=10, decimal_places=2)
    voltaje = models.CharField(max_length=50, blank=True, default="")
    precio_adicional = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_adicional_dias = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Opción de motor"
        verbose_name_plural = "Opciones de motor"
        ordering = ["equipo__id_equipo", "marca__nombre", "potencia_hp"]

    def __str__(self):
        return f"{self.equipo.id_equipo} - {self.marca.nombre} - {self.potencia_hp} HP"


class Acople(models.Model):
    nombre = models.CharField(max_length=100)
    precio_adicional = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_adicional_dias = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Acople"
        verbose_name_plural = "Acoples"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Variador(models.Model):
    nombre = models.CharField(max_length=100)
    potencia_hp_min = models.DecimalField(max_digits=10, decimal_places=2)
    potencia_hp_max = models.DecimalField(max_digits=10, decimal_places=2)
    precio_adicional = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_adicional_dias = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Variador"
        verbose_name_plural = "Variadores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Conexion(models.Model):
    TIPO_SUCCION = "SUCCION"
    TIPO_DESCARGA = "DESCARGA"

    TIPO_CHOICES = [
        (TIPO_SUCCION, "Succión"),
        (TIPO_DESCARGA, "Descarga"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    diametro = models.CharField(max_length=20)
    ansi = models.CharField(max_length=20)
    precio_adicional = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_adicional_dias = models.PositiveIntegerField(default=0)
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Conexión"
        verbose_name_plural = "Conexiones"
        ordering = ["tipo", "diametro", "ansi"]

    def __str__(self):
        return f"{self.tipo} {self.diametro} ANSI {self.ansi}"


class SolicitudCotizacion(models.Model):
    empresa = models.CharField(max_length=150)
    contacto = models.CharField(max_length=150)
    correo = models.EmailField()
    telefono = models.CharField(max_length=30, blank=True, default="")
    nombre_proyecto = models.CharField(max_length=150, blank=True, default="")
    observaciones_cliente = models.TextField(blank=True, default="")

    presion_succion = models.DecimalField(max_digits=10, decimal_places=2)
    presion_descarga = models.DecimalField(max_digits=10, decimal_places=2)
    caudal = models.DecimalField(max_digits=12, decimal_places=2)
    dp_calculada = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    equipo_recomendado = models.ForeignKey(
        EquipoBase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes",
    )
    punto_recomendado = models.ForeignKey(
        CurvaOperacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes",
    )

    motor = models.ForeignKey(
        OpcionMotor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    acople = models.ForeignKey(
        Acople,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    variador = models.ForeignKey(
        Variador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    conexion_succion = models.ForeignKey(
        Conexion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_succion",
    )
    conexion_descarga = models.ForeignKey(
        Conexion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_descarga",
    )

    valor_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_entrega_estimado_dias = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solicitud de cotización"
        verbose_name_plural = "Solicitudes de cotización"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Solicitud #{self.pk} - {self.empresa}"


class ReparacionCamaraTarifa(models.Model):
    TIPO_MENOR = "MENOR"
    TIPO_MAYOR = "MAYOR"
    TIPO_UPGRADE = "UPGRADE"

    TIPO_CHOICES = [
        (TIPO_MENOR, "Menor"),
        (TIPO_MAYOR, "Mayor"),
        (TIPO_UPGRADE, "Upgrade"),
    ]

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    tipo_reparacion = models.CharField(max_length=20, choices=TIPO_CHOICES)

    valor_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tiempo_estimado_texto = models.CharField(max_length=100, blank=True, default="")
    observacion = models.TextField(blank=True, default="")

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tarifa reparación cámara"
        verbose_name_plural = "Tarifas reparación cámara"
        ordering = ["marca", "modelo", "tipo_reparacion"]
        unique_together = ("marca", "modelo", "tipo_reparacion")

    def __str__(self):
        return f"{self.marca} - {self.modelo} - {self.tipo_reparacion}"


class SolicitudReparacionCamara(models.Model):
    empresa = models.CharField(max_length=150)
    contacto = models.CharField(max_length=150)
    correo = models.EmailField()
    telefono = models.CharField(max_length=30, blank=True, default="")
    nombre_proyecto = models.CharField(max_length=150, blank=True, default="")

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    serial = models.CharField(max_length=100, blank=True, default="")
    tipo_reparacion = models.CharField(
        max_length=20,
        choices=ReparacionCamaraTarifa.TIPO_CHOICES,
    )

    observaciones_cliente = models.TextField(blank=True, default="")
    observacion_tecnica = models.TextField(blank=True, default="")
    tiempo_estimado_texto = models.CharField(max_length=100, blank=True, default="")
    valor_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    solicito_precio = models.BooleanField(default=False)
    fecha_solicitud_precio = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solicitud reparación cámara"
        verbose_name_plural = "Solicitudes reparación cámara"
        ordering = ["-created_at"]

    def __str__(self):
        return f"RC-{self.id:04d} - {self.empresa}"

class DiagnosticoVariador(models.Model):
    marca = models.CharField(max_length=100)
    codigo = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    nombre_falla = models.CharField(max_length=200)
    causa_probable = models.TextField(blank=True, default="")
    accion_recomendada = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=100, blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Diagnóstico Variador"
        verbose_name_plural = "Diagnósticos Variadores"
        ordering = ["marca", "codigo"]
        unique_together = ("marca", "codigo")

    def __str__(self):
        return f"{self.marca} - {self.codigo}"