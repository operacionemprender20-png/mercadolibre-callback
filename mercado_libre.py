import os
import requests

API_URL = "https://api.mercadolibre.com"
SITE_ID = "MLC"


def obtener_headers(access_token=None):
    if not access_token:
        return {}

    return {
        "Authorization": f"Bearer {access_token}"
    }


def obtener_categorias(access_token=None):
    url = f"{API_URL}/sites/{SITE_ID}/categories"

    respuesta = requests.get(
        url,
        headers=obtener_headers(access_token),
        timeout=30
    )
    respuesta.raise_for_status()

    return respuesta.json()


def obtener_categoria(category_id, access_token=None):
    url = f"{API_URL}/categories/{category_id}"

    respuesta = requests.get(
        url,
        headers=obtener_headers(access_token),
        timeout=30
    )
    respuesta.raise_for_status()

    return respuesta.json()

def obtener_subcategorias(category_id, access_token=None):
    categoria = obtener_categoria(category_id, access_token)

    subcategorias = []

    for subcategoria in categoria.get("children_categories", []):
        subcategorias.append({
            "id": subcategoria.get("id"),
            "nombre": subcategoria.get("name"),
            "publicaciones": subcategoria.get(
                "total_items_in_this_category",
                0
            )
        })

    return subcategorias

def buscar_productos(category_id, access_token=None, limit=10):
    url = f"{API_URL}/sites/{SITE_ID}/search"

    parametros = {
        "category": category_id,
        "limit": limit
    }

    respuesta = requests.get(
        url,
        headers=obtener_headers(access_token),
        params=parametros,
        timeout=30
    )

    if not respuesta.ok:
        return {
            "status": "error",
            "codigo_http": respuesta.status_code,
            "url_consultada": respuesta.url,
            "respuesta_mercado_libre": respuesta.text
        }

    return respuesta.json()
