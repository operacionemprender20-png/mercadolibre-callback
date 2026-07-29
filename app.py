import os

import requests
from flask import Flask, jsonify, redirect, request
from mercado_libre import obtener_categorias, obtener_categoria
from crawler import construir_indice_subcategorias

app = Flask(__name__)

CLIENT_ID = os.environ.get("MELI_CLIENT_ID")
CLIENT_SECRET = os.environ.get("MELI_CLIENT_SECRET")
REDIRECT_URI = "https://mercadolibre-callback.onrender.com/callback"

# Almacenamiento temporal. Se pierde cuando Render reinicia.
tokens = {}

@app.route("/categorias", methods=["GET"])
def categorias():
    access_token = tokens.get("access_token")

    if not access_token:
        return jsonify(
            status="error",
            message="Primero debes autorizar la aplicación entrando a /authorize"
        ), 401

    try:
        categorias = obtener_categorias(access_token)

        return jsonify(
            status="ok",
            total=len(categorias),
            categorias=categorias
        ), 200

    except Exception as e:
        return jsonify(
            status="error",
            message=str(e)
        ), 500

@app.route("/categoria/<category_id>", methods=["GET"])
def categoria(category_id):
    access_token = tokens.get("access_token")

    if not access_token:
        return jsonify(
            status="error",
            message="Primero debes autorizar la aplicación entrando a /authorize"
        ), 401

    try:
        categoria = obtener_categoria(category_id, access_token)

        return jsonify(
            status="ok",
            categoria=categoria
        ), 200

    except Exception as e:
        return jsonify(
            status="error",
            message=str(e)
        ), 500
        
@app.route("/indice/<category_id>")
def indice_subcategorias(category_id):
    access_token = tokens.get("access_token")

    if not access_token:
        return jsonify({
            "status": "error",
            "mensaje": "No hay access token. Debes autenticarte nuevamente."
        }), 401

    try:
        subcategorias = construir_indice_subcategorias(
            category_id,
            access_token
        )

        return jsonify({
            "status": "ok",
            "category_id": category_id,
            "total_subcategorias": len(subcategorias),
            "subcategorias": subcategorias
        })

    except requests.RequestException as error:
        return jsonify({
            "status": "error",
            "mensaje": str(error)
        }), 500

@app.route("/", methods=["GET"])
def inicio():
    return jsonify(
        status="ok",
        message="Servicio de Mercado Libre activo",
        authorize_url="/authorize"
    ), 200


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
            description=request.args.get("error_description", "")
        ), 400

    if not code:
        return jsonify(
            status="ok",
            message="Endpoint callback disponible"
        ), 200

    if not CLIENT_ID or not CLIENT_SECRET:
        return jsonify(
            status="error",
            message="Faltan MELI_CLIENT_ID o MELI_CLIENT_SECRET en Render"
        ), 500

    token_response = requests.post(
        "https://api.mercadolibre.com/oauth/token",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
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

    result = token_response.json()

    if not token_response.ok:
        return jsonify(
            status="error",
            message="Mercado Libre no pudo generar los tokens",
            details=result
        ), token_response.status_code

    tokens["access_token"] = result.get("access_token")
    tokens["refresh_token"] = result.get("refresh_token")
    tokens["expires_in"] = result.get("expires_in")
    tokens["user_id"] = result.get("user_id")

    return jsonify(
        status="success",
        message="Autorización completada y tokens recibidos",
        user_id=tokens["user_id"],
        expires_in=tokens["expires_in"],
        access_token_guardado=bool(tokens["access_token"]),
        refresh_token_guardado=bool(tokens["refresh_token"])
    ), 200


@app.route("/me", methods=["GET"])
def me():
    access_token = tokens.get("access_token")

    if not access_token:
        return jsonify(
            status="error",
            message="Primero debes autorizar la aplicación entrando a /authorize"
        ), 401

    response = requests.get(
        "https://api.mercadolibre.com/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )

    return jsonify(response.json()), response.status_code


@app.route("/notifications", methods=["GET", "POST"])
def notifications():
    if request.method == "GET":
        return jsonify(
            status="ok",
            message="Endpoint de notificaciones disponible"
        ), 200

    notification = request.get_json(silent=True)
    print("Notificación recibida:", notification)

    return jsonify(status="received"), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
