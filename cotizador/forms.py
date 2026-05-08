from django import forms
from django.contrib.auth.models import User


from django import forms
from django.contrib.auth.models import User


class SolicitudCuentaForm(forms.ModelForm):
    nombre = forms.CharField(
        label="Nombre completo",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nombre Completo"
        })
    )

    empresa = forms.CharField(
        label="Empresa",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ej: IMPETUS HPS"
        })
    )

    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "correo@empresa.com"
        })
    )

    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Escriba una constraseña de 6 dígitos"
        })
    )

    class Meta:
        model = User
        fields = ["nombre", "empresa", "email", "username", "password"]

        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Escriba tu usuario, apodo o correo"
            }),
        }

        labels = {
            "username": "Usuario",
        }

    def clean_email(self):
        email = self.cleaned_data["email"]

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta registrada con este correo."
            )

        return email

    def clean_username(self):
        username = self.cleaned_data["username"]

        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(
                "Este usuario ya existe."
            )

        return username

class ImportadorCotizadorBombasForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel de bombas",
        help_text="Debe cargar un archivo .xlsx con equipos base y curvas de operación."
    )

    limpiar = forms.BooleanField(
        label="Borrar datos existentes antes de importar",
        required=False,
        initial=True
    )


class ImportadorDiagnosticoVariadorForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel",
        help_text="Cargue un archivo .xlsx con la hoja de diagnósticos.",
    )


class ImportadorReparacionCamaraForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel",
        help_text="Cargue un archivo .xlsx con las tarifas de reparación de cámara.",
    )
