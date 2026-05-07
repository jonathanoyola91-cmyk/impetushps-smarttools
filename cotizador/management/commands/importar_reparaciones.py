import pandas as pd

from django.core.management.base import BaseCommand, CommandError

from cotizador.models import ReparacionCamaraTarifa


class Command(BaseCommand):
    help = "Importa tarifas de reparación de cámaras desde Excel"

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str)

    def handle(self, *args, **options):
        archivo = options["archivo"]

        try:
            df = pd.read_excel(
                archivo,
                sheet_name="tarifas_reparacion"
            )
        except Exception as e:
            raise CommandError(f"No se pudo leer el archivo: {e}")

        creados = 0
        actualizados = 0

        for _, row in df.iterrows():

            marca = str(row.get("marca", "")).strip()
            modelo = str(row.get("modelo", "")).strip()
            tipo = str(row.get("tipo_reparacion", "")).strip().upper()

            if not marca or not modelo or not tipo:
                continue

            valor = row.get("valor_estimado", 0)
            tiempo = str(row.get("tiempo_estimado_semanas", "")).strip()
            activo_excel = str(row.get("activo", "SI")).strip().upper()
            observacion = str(row.get("observacion", "")).strip()

            if pd.isna(valor):
                valor = 0

            activo = True if activo_excel in ["SI", "TRUE", "1"] else False

            obj, creado = ReparacionCamaraTarifa.objects.update_or_create(
                marca=marca,
                modelo=modelo,
                tipo_reparacion=tipo,
                defaults={
                    "valor_estimado": valor,
                    "tiempo_estimado_texto": tiempo,
                    "activo": activo,
                    "observacion": observacion,
                }
            )

            if creado:
                creados += 1
            else:
                actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Importación completada.\n"
            f"Creados: {creados}\n"
            f"Actualizados: {actualizados}"
        ))