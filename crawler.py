from mercado_libre import obtener_subcategorias


def construir_indice_subcategorias(category_id, access_token):
    subcategorias = obtener_subcategorias(
        category_id,
        access_token
    )

    if not subcategorias:
        return []

    total_publicaciones = sum(
        subcategoria["publicaciones"]
        for subcategoria in subcategorias
    )

    subcategorias_ordenadas = sorted(
        subcategorias,
        key=lambda subcategoria: subcategoria["publicaciones"],
        reverse=True
    )

    resultado = []

    for posicion, subcategoria in enumerate(
        subcategorias_ordenadas,
        start=1
    ):
        publicaciones = subcategoria["publicaciones"]

        if total_publicaciones > 0:
            participacion = (
                publicaciones / total_publicaciones
            ) * 100
        else:
            participacion = 0

        if publicaciones >= 50000:
            competencia = "Alta"
        elif publicaciones >= 10000:
            competencia = "Media"
        else:
            competencia = "Baja"

        resultado.append({
            "ranking": posicion,
            "id": subcategoria["id"],
            "nombre": subcategoria["nombre"],
            "publicaciones": publicaciones,
            "participacion": round(participacion, 2),
            "competencia": competencia
        })

    return resultado
