import os

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/", methods=["GET"])
def inicio():
    return jsonify(
        status="ok",
        message="Servicio de Mercado Libre activo"
    ), 200


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

    # Por ahora solo confirma la recepción.
    # Después cambiaremos el código por los tokens OAuth.
    return jsonify(
        status="success",
        message="Código de autorización recibido",
        code=code
    ), 200


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
