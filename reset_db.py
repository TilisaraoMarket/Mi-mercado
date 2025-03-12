from app import app, db, crear_productos_ejemplo

with app.app_context():
    print("Eliminando base de datos...")
    db.drop_all()
    print("Creando nueva base de datos...")
    db.create_all()
    print("Creando productos de ejemplo...")
    crear_productos_ejemplo()
    print("¡Base de datos reiniciada exitosamente!")
