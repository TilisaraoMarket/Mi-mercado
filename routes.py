from flask import Blueprint, request, jsonify
from models import db, Usuario

main_bp = Blueprint("main", __name__)

@main_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400

    email = data.get("email")
    password = data.get("password")
    nombre = data.get("nombre")
    apellido = data.get("apellido")

    # Verificación de campos
    if not email or not password or not nombre or not apellido:
        return jsonify({"error": "Faltan datos requeridos"}), 400

    # Revisar si ya existe un usuario con ese email
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"error": "El usuario ya existe"}), 400

    # Crear nuevo usuario
    usuario = Usuario(email=email, password=password, nombre=nombre, apellido=apellido)
    db.session.add(usuario)
    db.session.commit()

    return jsonify({"message": "Usuario registrado exitosamente"}), 201