from django import forms
from .models import SystemComponent


class ChangeComponentForm(forms.Form):
    MOTIVO_CHOICES = [
        ("FALLA", "Falla"),
        ("PREVENTIVO", "Mantenimiento preventivo"),
        ("UPGRADE", "Mejora / Upgrade"),
        ("ROTACION", "Rotación"),
        ("GARANTIA", "Garantía"),
        ("OTRO", "Otro"),
    ]

    POSICION_BOMBA_CHOICES = [
        ("", "No aplica"),
        ("LOWER", "Lower"),
        ("MIDDLE", "Middle"),
        ("UPPER", "Upper"),
        ("GENERAL", "General"),
    ]

    componente_actual = forms.ModelChoiceField(
        queryset=SystemComponent.objects.filter(activo=True),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    nuevo_serial = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    nuevo_modelo = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    nuevo_parte = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    fecha_cambio = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )

    motivo_tipo = forms.ChoiceField(
        choices=MOTIVO_CHOICES,
        initial="OTRO",
        label="Motivo del cambio",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    es_falla = forms.BooleanField(
        required=False,
        label="Este reemplazo fue por falla",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    posicion_bomba = forms.ChoiceField(
        required=False,
        choices=POSICION_BOMBA_CHOICES,
        label="Posición bomba",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    causa_falla = forms.CharField(
        required=False,
        label="Causa / modo de falla",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )

    motivo = forms.CharField(
        required=False,
        label="Observación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3})
    )
