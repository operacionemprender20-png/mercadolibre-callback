from mercado_libre import obtener_subcategorias


def construir_indice_subcategorias(category_id, access_token):
    subcategorias = obtener_subcategorias(
        category_id,
        access_token
    )

    subcategorias_ordenadas = sorted(
        subcategorias,
        key=lambda subcategoria: subcategoria["publicaciones"],
        reverse=True
    )

    return subcategorias_ordenadas
