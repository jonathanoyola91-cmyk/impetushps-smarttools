from django import forms
from .models import SystemComponent


class ChangeComponentForm(forms.Form):
    componente_actual = forms.ModelChoiceField(
        queryset=SystemComponent.objects.filter(activo=True),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    nuevo_serial = forms.CharField(
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

    motivo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control"})
    )