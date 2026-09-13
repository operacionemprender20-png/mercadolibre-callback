from mercado_libre import obtener_categoria, obtener_categorias


# ============================================================
# NAVEGACIÓN NORMAL
# ============================================================

def construir_indice_subcategorias(category_id, access_token):
    """
    Obtiene SOLO las subcategorías directas de la categoría
    seleccionada. Esta función se usa para navegar nivel por nivel.
    """

    categoria = obtener_categoria(category_id, access_token)

    categoria_id_real = categoria.get("id")
    categoria_nombre = categoria.get("name", "")

    if categoria_id_real != category_id:
        raise ValueError(
            f"Categoría solicitada={category_id}, "
            f"categoría recibida={categoria_id_real}"
        )

    hijos = categoria.get("children_categories", [])

    if not hijos:
        return []

    total_publicaciones = sum(
        hijo.get("total_items_in_this_category", 0) or 0
        for hijo in hijos
    )

    resultado = []

    for hijo in hijos:

        subcategoria_id = hijo.get("id")

        if not subcategoria_id:
            continue

        publicaciones = (
            hijo.get("total_items_in_this_category", 0) or 0
        )

        participacion = (
            publicaciones / total_publicaciones * 100
            if total_publicaciones > 0
            else 0
        )

        if publicaciones >= 50000:
            competencia = "Alta"
        elif publicaciones >= 10000:
            competencia = "Media"
        else:
            competencia = "Baja"

        resultado.append({
            "id": subcategoria_id,
            "nombre": hijo.get("name", ""),
            "publicaciones": publicaciones,
            "participacion": round(participacion, 2),
            "competencia": competencia,

            # Para controlar correctamente la navegación
            "parent_id": category_id,
            "parent_nombre": categoria_nombre,
            "siguiente_category_id": subcategoria_id
        })

    resultado.sort(
        key=lambda x: x["publicaciones"],
        reverse=True
    )

    for posicion, subcategoria in enumerate(resultado, start=1):
        subcategoria["ranking"] = posicion

    return resultado


# ============================================================
# INVENTARIO COMPLETO DEL ÁRBOL
# ============================================================

def construir_inventario_categorias(access_token):
    """
    Recorre TODAS las categorías principales de Mercado Libre Chile
    y todos sus descendientes.

    Esta función es para INVENTARIO, no para ejecutarla
    constantemente.
    """

    categorias_principales = obtener_categorias(access_token)

    visitadas = set()
    categorias = []

    resumen_principales = []

    profundidad_maxima = 0


    def recorrer(category_id, nivel, ruta, principal_id, principal_nombre):
        """
        Recorre recursivamente una rama del árbol.
        """

        nonlocal profundidad_maxima

        # Evita procesar dos veces el mismo ID
        if category_id in visitadas:
            return {
                "total": 0,
                "terminales": 0
            }

        visitadas.add(category_id)

        categoria = obtener_categoria(
            category_id,
            access_token
        )

        nombre = categoria.get("name", "")
        hijos = categoria.get("children_categories", [])

        publicaciones = (
            categoria.get("total_items_in_this_category", 0) or 0
        )

        es_terminal = len(hijos) == 0

        nueva_ruta = ruta + [nombre]

        profundidad_maxima = max(
            profundidad_maxima,
            nivel
        )

        categorias.append({
            "id": category_id,
            "nombre": nombre,
            "nivel": nivel,

            "principal_id": principal_id,
            "principal_nombre": principal_nombre,

            "parent_id": (
                categoria.get("path_from_root", [])[-2]["id"]
                if len(categoria.get("path_from_root", [])) >= 2
                else None
            ),

            "publicaciones": publicaciones,

            "es_terminal": es_terminal,

            "cantidad_hijos": len(hijos),

            "ruta": " > ".join(nueva_ruta)
        })

        total_rama = 1

        terminales_rama = (
            1 if es_terminal else 0
        )

        for hijo in hijos:

            hijo_id = hijo.get("id")

            if not hijo_id:
                continue

            resultado_hijo = recorrer(
                hijo_id,
                nivel + 1,
                nueva_ruta,
                principal_id,
                principal_nombre
            )

            total_rama += resultado_hijo["total"]

            terminales_rama += resultado_hijo["terminales"]

        return {
            "total": total_rama,
            "terminales": terminales_rama
        }


    # ========================================================
    # RECORRER CADA CATEGORÍA PRINCIPAL
    # ========================================================

    for principal in categorias_principales:

        principal_id = principal.get("id")
        principal_nombre = principal.get("name", "")

        if not principal_id:
            continue

        resultado = recorrer(
            principal_id,
            nivel=0,
            ruta=[],
            principal_id=principal_id,
            principal_nombre=principal_nombre
        )

        resumen_principales.append({
            "id": principal_id,
            "nombre": principal_nombre,
            "categorias_totales": resultado["total"],
            "categorias_terminales": resultado["terminales"]
        })


    # ========================================================
    # ESTADÍSTICAS POR NIVEL
    # ========================================================

    categorias_por_nivel = {}

    for categoria in categorias:

        nivel = categoria["nivel"]

        categorias_por_nivel[nivel] = (
            categorias_por_nivel.get(nivel, 0) + 1
        )


    # ========================================================
    # RESULTADO
    # ========================================================

    return {
        "resumen": {
            "categorias_principales": len(categorias_principales),

            "categorias_totales": len(categorias),

            "categorias_terminales": sum(
                1
                for categoria in categorias
                if categoria["es_terminal"]
            ),

            "profundidad_maxima": profundidad_maxima,

            "categorias_por_nivel": categorias_por_nivel
        },

        "categorias_principales": resumen_principales,

        "categorias": categorias
    }
def construir_inventario_rama(category_id, access_token):
    """
    Recorre una sola categoría principal y todos sus descendientes.
    """

    visitadas = set()
    categorias = []
    profundidad_maxima = 0

    categoria_principal = obtener_categoria(
        category_id,
        access_token
    )

    principal_nombre = categoria_principal.get("name", "")

    def recorrer(id_actual, nivel, ruta):
        nonlocal profundidad_maxima

        if id_actual in visitadas:
            return

        visitadas.add(id_actual)

        categoria = obtener_categoria(
            id_actual,
            access_token
        )

        nombre = categoria.get("name", "")
        hijos = categoria.get("children_categories", [])

        publicaciones = (
            categoria.get("total_items_in_this_category", 0) or 0
        )

        es_terminal = len(hijos) == 0

        nueva_ruta = ruta + [nombre]

        profundidad_maxima = max(
            profundidad_maxima,
            nivel
        )

        categorias.append({
            "id": id_actual,
            "nombre": nombre,
            "nivel": nivel,
            "publicaciones": publicaciones,
            "es_terminal": es_terminal,
            "cantidad_hijos": len(hijos),
            "ruta": " > ".join(nueva_ruta)
        })

        for hijo in hijos:
            hijo_id = hijo.get("id")

            if hijo_id:
                recorrer(
                    hijo_id,
                    nivel + 1,
                    nueva_ruta
                )

    recorrer(
        category_id,
        0,
        []
    )

    terminales = sum(
        1
        for categoria in categorias
        if categoria["es_terminal"]
    )

    return {
        "categoria_principal": {
            "id": category_id,
            "nombre": principal_nombre
        },

        "resumen": {
            "categorias_encontradas": len(categorias),
            "categorias_terminales": terminales,
            "profundidad_maxima": profundidad_maxima
        },

        "categorias": categorias
    }

