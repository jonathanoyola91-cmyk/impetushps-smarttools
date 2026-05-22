import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date

from runlife.models import InjectionSystem, SystemComponent


class Command(BaseCommand):
    help = "Importa componentes RunLife desde Excel"

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str)

    def handle(self, *args, **options):
        archivo = options["archivo"]

        try:
            df = pd.read_excel(archivo)
        except Exception as e:
            raise CommandError(f"No se pudo leer el archivo Excel: {e}")

        columnas_requeridas = [
            "sistema_id",
            "tipo",
            "descripcion",
            "serial",
            "parte_numero",
        ]

        for columna in columnas_requeridas:
            if columna not in df.columns:
                raise CommandError(f"Falta la columna obligatoria: {columna}")

        creados = 0
        errores = []

        tipos_unicos = ["MOTOR", "CAMARA", "COOLER", "VSD"]

        mapa_tipos = {
            "MOTOR": "MOTOR",
            "Motor": "MOTOR",
            "CAMARA": "CAMARA",
            "Cámara": "CAMARA",
            "Cámara de Empuje": "CAMARA",
            "Camara de Empuje": "CAMARA",
            "BOMBA": "BOMBA",
            "Bomba": "BOMBA",
            "COOLER": "COOLER",
            "Cooler": "COOLER",
            "VSD": "VSD",
            "Variador / VSD": "VSD",
            "Variador": "VSD",
            "OTRO": "OTRO",
            "Otro": "OTRO",
        }

        with transaction.atomic():
            for index, row in df.iterrows():
                fila = index + 2

                try:
                    sistema_id = int(row["sistema_id"])
                    sistema = InjectionSystem.objects.get(id=sistema_id)

                    tipo_excel = str(row["tipo"]).strip()
                    tipo = mapa_tipos.get(tipo_excel, tipo_excel.upper())

                    descripcion = str(row["descripcion"]).strip()
                    serial = str(row["serial"]).strip()
                    parte_numero = str(row["parte_numero"]).strip()

                    marca = (
                        str(row.get("marca", "IMPETUS")).strip()
                        if not pd.isna(row.get("marca", ""))
                        else "IMPETUS"
                    )

                    modelo = (
                        str(row.get("modelo", "")).strip()
                        if not pd.isna(row.get("modelo", ""))
                        else ""
                    )

                    origen = (
                        str(row.get("origen", "CLIENTE")).strip()
                        if "origen" in df.columns and not pd.isna(row.get("origen"))
                        else "CLIENTE"
                    )

                    fecha_instalacion = None
                    if "fecha_instalacion" in df.columns and not pd.isna(row.get("fecha_instalacion")):
                        valor_fecha = row.get("fecha_instalacion")

                        if hasattr(valor_fecha, "date"):
                            fecha_instalacion = valor_fecha.date()
                        else:
                            fecha_instalacion = parse_date(str(valor_fecha))

                    if tipo in tipos_unicos:
                        existe_activo = SystemComponent.objects.filter(
                            sistema=sistema,
                            tipo=tipo,
                            activo=True,
                        ).exists()

                        if existe_activo:
                            errores.append(
                                f"Fila {fila}: ya existe un {tipo} activo para el sistema {sistema_id}. Use reemplazo."
                            )
                            continue

                    SystemComponent.objects.create(
                        sistema=sistema,
                        tipo=tipo,
                        origen=origen,
                        descripcion=descripcion,
                        marca=marca,
                        modelo=modelo,
                        serial=serial,
                        parte_numero=parte_numero,
                        fecha_instalacion=fecha_instalacion,
                        fecha_entrega_cliente=fecha_instalacion,
                        activo=True,
                    )

                    creados += 1

                except InjectionSystem.DoesNotExist:
                    errores.append(f"Fila {fila}: no existe sistema_id {row['sistema_id']}")
                except Exception as e:
                    errores.append(f"Fila {fila}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Componentes creados: {creados}"))

        if errores:
            self.stdout.write(self.style.WARNING("Errores encontrados:"))
            for error in errores:
                self.stdout.write(self.style.WARNING(error))