import os
import requests

API_URL = "https://api.mercadolibre.com"
SITE_ID = "MLC"


def obtener_headers():
    token = os.getenv("MELI_ACCESS_TOKEN")

    if not token:
        return {}

    return {
        "Authorization": f"Bearer {token}"
    }


def obtener_categorias():
    url = f"{API_URL}/sites/{SITE_ID}/categories"

    respuesta = requests.get(
        url,
        headers=obtener_headers(),
        timeout=30
    )
    respuesta.raise_for_status()

    return respuesta.json()


def obtener_categoria(category_id):
    url = f"{API_URL}/categories/{category_id}"

    respuesta = requests.get(
        url,
        headers=obtener_headers(),
        timeout=30
    )
    respuesta.raise_for_status()

    return respuesta.json()
