from django import forms

class ImportadorDiagnosticoVariadorForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel",
        help_text="Cargue un archivo .xlsx con la hoja de diagnósticos."
    )