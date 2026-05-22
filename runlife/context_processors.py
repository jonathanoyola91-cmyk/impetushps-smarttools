def permisos_runlife(request):
    user = request.user

    puede_reglas = False

    if user.is_authenticated:
        puede_reglas = (
            user.is_staff
            or user.is_superuser
            or user.groups.filter(name="RUNLIFE_REGLAS").exists()
            or user.groups.filter(name="RUNLIFE_ADMIN").exists()
        )

    return {
        "puede_reglas": puede_reglas,
    }