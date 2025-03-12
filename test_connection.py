from flask import current_app
from pymongo import MongoClient
from pymongo.errors import ConnectionError

def test_mongo_connection():
    try:
        # Obtener la URI de MongoDB desde las variables de entorno
        client = MongoClient(current_app.config['MONGODB_URI'])
        
        # Intentar una operación simple para verificar la conexión
        client.admin.command('ping')
        
        print("¡Conexión exitosa a MongoDB!")
        
        # Mostrar las bases de datos disponibles
        print("Bases de datos disponibles:")
        print(client.list_database_names())
        
        return True
    except ConnectionError as e:
        print(f"Error de conexión: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False
    finally:
        client.close()