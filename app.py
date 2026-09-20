import os
from datetime import datetime, timedelta, timezone

import psycopg2
import requests
from flask import Flask, jsonify, redirect, request

from mercado_libre import (
    obtener_categorias,
    obtener_categoria,
    obtener_subcategorias,
    buscar_productos,
    buscar_productos_por_texto,
    buscar_catalogo,
    obtener_tendencias,
    obtener_tendencias_categoria,
    obtener_mas_vendidos_categoria
)

from crawler import (
    construir_indice_subcategorias,
    construir_inventario_categorias,
    construir_inventario_rama
)


app = Flask(__name__)

CLIENT_ID = os.environ.get("MELI_CLIENT_ID")
CLIENT_SECRET = os.environ.get("MELI_CLIENT_SECRET")
DATABASE_URL = os.environ.get("DATABASE_URL")

REDIRECT_URI = "https://mercadolibre-callback.onrender.com/callback"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


# ============================================================
# BASE DE DATOS
# ============================================================

def obtener_conexion():
    if not DATABASE_URL:
        raise RuntimeError("Falta la variable DATABASE_URL en Render")

    return psycopg2.connect(DATABASE_URL)


def inicializar_base_datos():
    conexion = obtener_conexion()

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mercado_libre_tokens (
                    user_id BIGINT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

        conexion.commit()

    finally:
        conexion.close()


def guardar_tokens(resultado):
    access_token = resultado.get("access_token")
    refresh_token = resultado.get("refresh_token")
    expires_in = resultado.get("expires_in")
    user_id = resultado.get("user_id")

    if not access_token:
        raise RuntimeError("Mercado Libre no devolvió access_token")

    if not refresh_token:
        raise RuntimeError("Mercado Libre no devolvió refresh_token")

    if not expires_in:
        raise RuntimeError("Mercado Libre no devolvió expires_in")

    if not user_id:
        raise RuntimeError("Mercado Libre no devolvió user_id")

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=int(expires_in))
    )

    conexion = obtener_conexion()

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO mercado_libre_tokens (
                    user_id,
                    access_token,
                    refresh_token,
                    expires_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, NOW())

                ON CONFLICT (user_id)
                DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = NOW()
            """, (
                int(user_id),
                access_token,
                refresh_token,
                expires_at
            ))

        conexion.commit()

    finally:
        conexion.close()


def obtener_tokens_guardados():
    conexion = obtener_conexion()

    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                SELECT
                    user_id,
                    access_token,
                    refresh_token,
                    expires_at
                FROM mercado_libre_tokens
                ORDER BY updated_at DESC
                LIMIT 1
            """)

            fila = cursor.fetchone()

    finally:
        conexion.close()

    if not fila:
        return None

    return {
        "user_id": fila[0],
        "access_token": fila[1],
        "refresh_token": fila[2],
        "expires_at": fila[3]
    }


# ============================================================
# RENOVACIÓN AUTOMÁTICA DEL TOKEN
# ============================================================

def renovar_access_token(refresh_token):
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "Faltan MELI_CLIENT_ID o MELI_CLIENT_SECRET en Render"
        )

    respuesta = requests.post(
        TOKEN_URL,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token
        },
        timeout=30
    )

    try:
        resultado = respuesta.json()
    except ValueError:
        raise RuntimeError(
            f"Mercado Libre devolvió HTTP {respuesta.status_code}: "
            f"{respuesta.text}"
        )

    if not respuesta.ok:
        raise RuntimeError(
            f"No se pudo renovar el access token: {resultado}"
        )

    guardar_tokens(resultado)

    return resultado["access_token"]


def obtener_access_token():
    tokens = obtener_tokens_guardados()

    if not tokens:
        return None

    expires_at = tokens["expires_at"]

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    ahora = datetime.now(timezone.utc)

    # Renovamos cinco minutos antes del vencimiento.
    if expires_at <= ahora + timedelta(minutes=5):
        return renovar_access_token(
            tokens["refresh_token"]
        )

    return tokens["access_token"]


# ============================================================
# INICIALIZACIÓN
# ============================================================

try:
    inicializar_base_datos()
    print("Base de datos inicializada correctamente")
except Exception as error:
    print("Error inicializando PostgreSQL:", str(error))


# ============================================================
# INICIO
# ============================================================

@app.route("/", methods=["GET"])
def inicio():
    return jsonify(
        status="ok",
        message="Servicio TrendVenta / Mercado Libre activo",
        authorize_url="/authorize"
    ), 200


# ============================================================
# AUTORIZACIÓN MERCADO LIBRE
# ============================================================

@app.route("/authorize", methods=["GET"])
def authorize():
    if not CLIENT_ID:
        return jsonify(
            status="error",
            message="Falta la variable MELI_CLIENT_ID en Render"
        ), 500

    authorization_url = (
        "https://auth.mercadolibre.cl/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )

    return redirect(authorization_url)


@app.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return jsonify(
            status="error",
            error=error,
            description=request.args.get(
                "error_description",
                ""
            )
        ), 400

    if not code:
        return jsonify(
            status="ok",
            message="Endpoint callback disponible"
        ), 200

    if not CLIENT_ID or not CLIENT_SECRET:
        return jsonify(
            status="error",
            message=(
                "Faltan MELI_CLIENT_ID o "
                "MELI_CLIENT_SECRET en Render"
            )
        ), 500

    try:
        token_response = requests.post(
            TOKEN_URL,
            headers={
                "Accept": "application/json",
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI
            },
            timeout=30
        )

        resultado = token_response.json()

        if not token_response.ok:
            return jsonify(
                status="error",
                message=(
                    "Mercado Libre no pudo generar "
                    "los tokens"
                ),
                details=resultado
            ), token_response.status_code

        guardar_tokens(resultado)

        return jsonify(
            status="success",
            message=(
                "Autorización completada. "
                "Tokens guardados en PostgreSQL."
            ),
            user_id=resultado.get("user_id"),
            expires_in=resultado.get("expires_in"),
            access_token_guardado=True,
            refresh_token_guardado=True,
            almacenamiento="postgresql"
        ), 200

    except Exception as error:
        return jsonify(
            status="error",
            message=str(error)
        ), 500


# ============================================================
# ESTADO DE AUTENTICACIÓN
# ============================================================

@app.route("/token-status", methods=["GET"])
def token_status():
    try:
        tokens = obtener_tokens_guardados()

        if not tokens:
            return jsonify(
                status="sin_autorizacion",
                token_guardado=False,
                authorize_url="/authorize"
            ), 200

        return jsonify(
            status="ok",
            token_guardado=True,
            user_id=tokens["user_id"],
            expires_at=tokens["expires_at"].isoformat()
        ), 200

    except Exception as error:
        return jsonify(
            status="error",
            message=str(error)
        ), 500


# ============================================================
# USUARIO
# ============================================================

@app.route("/me", methods=["GET"])
def me():
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify(
                status="error",
                message=(
                    "Primero debes autorizar la aplicación "
                    "entrando a /authorize"
                )
            ), 401

        response = requests.get(
            "https://api.mercadolibre.com/users/me",
            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },
            timeout=30
        )

        return jsonify(
            response.json()
        ), response.status_code

    except Exception as error:
        return jsonify(
            status="error",
            message=str(error)
        ), 500


# ============================================================
# CATEGORÍAS
# ============================================================

@app.route("/categorias", methods=["GET"])
def categorias():
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify(
                status="error",
                message=(
                    "Primero debes autorizar la aplicación "
                    "entrando a /authorize"
                )
            ), 401

        resultado = obtener_categorias(
            access_token
        )

        return jsonify(
            status="ok",
            total=len(resultado),
            categorias=resultado
        ), 200

    except Exception as error:
        return jsonify(
            status="error",
            message=str(error)
        ), 500


@app.route("/categoria/<category_id>", methods=["GET"])
def categoria(category_id):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify(
                status="error",
                message=(
                    "Primero debes autorizar la aplicación "
                    "entrando a /authorize"
                )
            ), 401

        resultado = obtener_categoria(
            category_id,
            access_token
        )

        return jsonify(
            status="ok",
            categoria=resultado
        ), 200

    except Exception as error:
        return jsonify(
            status="error",
            message=str(error)
        ), 500


@app.route("/indice/<category_id>", methods=["GET"])
def indice_subcategorias(category_id):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        subcategorias = construir_indice_subcategorias(
            category_id,
            access_token
        )

        return jsonify({
            "status": "ok",
            "category_id": category_id,
            "total_subcategorias":
                len(subcategorias),
            "subcategorias": subcategorias
        }), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


# ============================================================
# INVENTARIO DE CATEGORÍAS
# ============================================================

@app.route(
    "/inventario-categorias",
    methods=["GET"]
)
def inventario_categorias():
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = construir_inventario_categorias(
            access_token
        )

        return jsonify({
            "status": "ok",
            **resultado
        }), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


@app.route(
    "/inventario/<category_id>",
    methods=["GET"]
)
def inventario_rama(category_id):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = construir_inventario_rama(
            category_id,
            access_token
        )

        return jsonify({
            "status": "ok",
            **resultado
        }), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


# ============================================================
# PRODUCTOS
# ============================================================

@app.route(
    "/productos/<category_id>",
    methods=["GET"]
)
def productos_categoria(category_id):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = buscar_productos(
            category_id,
            access_token,
            limit=1
        )

        return jsonify(resultado), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


# ============================================================
# BÚSQUEDA
# ============================================================

@app.route("/buscar/<texto>", methods=["GET"])
def buscar_por_texto(texto):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = buscar_productos_por_texto(
            texto,
            access_token,
            limit=1
        )

        return jsonify(resultado), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


# ============================================================
# CATÁLOGO
# ============================================================

@app.route("/catalogo/<texto>", methods=["GET"])
def catalogo(texto):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        domain_id = request.args.get(
            "domain_id"
        )

        resultado = buscar_catalogo(
            texto,
            access_token,
            limit=10,
            domain_id=domain_id
        )

        return jsonify(resultado), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500

# ============================================================
# TENDENCIAS
# ============================================================

@app.route("/tendencias", methods=["GET"])
def tendencias():
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = obtener_tendencias(
            access_token
        )

        return jsonify(resultado), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


@app.route(
    "/tendencias/<category_id>",
    methods=["GET"]
)
def tendencias_categoria(category_id):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = obtener_tendencias_categoria(
            category_id,
            access_token
        )

        return jsonify(resultado), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500


# ============================================================
# MÁS VENDIDOS
# ============================================================

@app.route(
    "/mas-vendidos/<category_id>",
    methods=["GET"]
)
def mas_vendidos_categoria(category_id):
    try:
        access_token = obtener_access_token()

        if not access_token:
            return jsonify({
                "status": "error",
                "mensaje":
                    "No hay access token. "
                    "Debes autenticarte nuevamente."
            }), 401

        resultado = obtener_mas_vendidos_categoria(
            category_id,
            access_token
        )

        return jsonify(resultado), 200

    except Exception as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500

# ============================================================
# NOTIFICACIONES
# ============================================================

@app.route(
    "/notifications",
    methods=["GET", "POST"]
)
def notifications():
    if request.method == "GET":
        return jsonify(
            status="ok",
            message=(
                "Endpoint de notificaciones "
                "disponible"
            )
        ), 200

    notification = request.get_json(
        silent=True
    )

    print(
        "Notificación recibida:",
        notification
    )

    return jsonify(
        status="received"
    ), 200


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


