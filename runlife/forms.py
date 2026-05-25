from django import forms

from .models import InjectionSystem, SystemComponent, MaintenanceRule, OperationalMonitoring
from .models import MaintenanceRule
from .models import OperationalLimit

class OperationalLimitForm(forms.ModelForm):
    class Meta:
        model = OperationalLimit
        fields = [
            "campo",
            "nombre",
            "vib_alerta",
            "vib_critico",
            "temp_alerta",
            "temp_critico",
            "dp_alerta",
            "dp_critico",
            "activo",
            "sistemas",
            "presion_succion_min",
            "presion_succion_max",
            "presion_descarga_min",
            "presion_descarga_max",
            "caudal_min",
            "caudal_max",
        ]
        widgets = {
            "campo": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),

            "vib_alerta": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "vib_critico": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),

            "temp_alerta": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "temp_critico": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),

            "dp_alerta": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "dp_critico": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),

            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "sistemas": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),

            "presion_succion_min": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "presion_succion_max": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "presion_descarga_min": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "presion_descarga_max": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "caudal_min": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "caudal_max": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["sistemas"].required = False
        self.fields["sistemas"].label = "Sistemas a los que aplica"
        self.fields["sistemas"].help_text = "Seleccione uno o varios sistemas. Si no selecciona ninguno, el límite aplica a todo el campo."
        self.fields["sistemas"].queryset = InjectionSystem.objects.none()

        campo_id = None

        if self.data.get("campo"):
            campo_id = self.data.get("campo")
        elif self.instance and self.instance.pk and self.instance.campo_id:
            campo_id = self.instance.campo_id

        if campo_id:
            self.fields["sistemas"].queryset = InjectionSystem.objects.filter(
                campo_id=campo_id,
                activo=True,
            ).order_by("nombre")


class OperationalMonitoringForm(forms.ModelForm):
    class Meta:
        model = OperationalMonitoring
        exclude = ["sistema", "creado_en"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        labels = {
    "frecuencia": "Frecuencia (Hz)",
    "corriente_motor": "Corriente (Amp)",
    "voltaje_motor": "Voltaje (V)",
    "kw": "Potencia (kW)",

    "presion_succion": "Presión succión (PSI)",
    "presion_descarga": "Presión descarga (PSI)",
    "caudal": "Caudal (BPD)",

    "vibracion_camara": "Vibración cámara (mm/s)",
    "temperatura_camara": "Temperatura cámara (°C)",

    "vibracion_bomba1": "Vibración bomba 1 (mm/s)",
    "vibracion_bomba2": "Vibración bomba 2 (mm/s)",
    "vibracion_bomba3": "Vibración bomba 3 (mm/s)",
    "vibracion_bomba4": "Vibración bomba 4 (mm/s)",

    "bomba3_aplica": "Bomba 3 aplica",
    "bomba4_aplica": "Bomba 4 aplica",
}

        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)

            if name in ["bomba3_aplica", "bomba4_aplica"]:
                field.widget.attrs.update({"class": "form-check-input"})
            elif name == "observaciones":
                field.widget.attrs.update({"class": "form-control", "rows": 4})
            else:
                field.widget.attrs.update({"class": "form-control"})

        self.fields["fecha"].widget.input_type = "date"
        self.fields["hora"].widget.input_type = "time"


class MaintenanceRuleForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRule
        fields = [
            "cliente",
            "campo",
            "sistemas",
            "tipo",
            "horas_mantenimiento",
            "dias_mantenimiento",
            "alerta_porcentaje",
            "activo",
        ]
        widgets = {
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "campo": forms.Select(attrs={"class": "form-select"}),
            "sistemas": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "horas_mantenimiento": forms.NumberInput(attrs={"class": "form-control"}),
            "dias_mantenimiento": forms.NumberInput(attrs={"class": "form-control"}),
            "alerta_porcentaje": forms.NumberInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["sistemas"].required = False
        self.fields["sistemas"].label = "Sistemas a los que aplica"
        self.fields["sistemas"].help_text = "Seleccione los sistemas específicos. Si no selecciona ninguno, la regla aplica según cliente/campo."
        self.fields["sistemas"].queryset = InjectionSystem.objects.none()

        campo_id = None

        if self.data.get("campo"):
            campo_id = self.data.get("campo")
        elif self.instance and self.instance.pk and self.instance.campo_id:
            campo_id = self.instance.campo_id

        if campo_id:
            self.fields["sistemas"].queryset = InjectionSystem.objects.filter(
                campo_id=campo_id,
                activo=True,
            ).order_by("nombre")


class InjectionSystemForm(forms.ModelForm):
    class Meta:
        model = InjectionSystem
        fields = ["nombre", "campo", "pozo", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Cohembi 1"}),
            "campo": forms.Select(attrs={"class": "form-select"}),
            "pozo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: CB-101"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SystemComponentForm(forms.ModelForm):
    class Meta:
        model = SystemComponent
        fields = [
            "sistema",
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
            "observaciones",
        ]
        widgets = {
            "sistema": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Bomba Lower / Bomba Upper / Cámara HTC"}),
            "marca": forms.TextInput(attrs={"class": "form-control"}),
            "modelo": forms.TextInput(attrs={"class": "form-control"}),
            "serial": forms.TextInput(attrs={"class": "form-control"}),
            "parte_numero": forms.TextInput(attrs={"class": "form-control"}),
            "fecha_reparacion": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "fecha_instalacion": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "fecha_desinstalacion": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }