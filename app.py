import json
from flask import Flask, request, jsonify, session, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
from flask_cors import CORS
from datetime import timedelta, datetime
from enum import Enum
import stripe
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from werkzeug.utils import secure_filename
from sqlalchemy.orm import validates
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from whitenoise import WhiteNoise
from werkzeug.middleware.proxy_fix import ProxyFix

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Priorizar variables de entorno sobre config.json
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    config = {
        'app': {
            'secret_key': os.getenv('SECRET_KEY', 'default-secret-key'),
            'session_lifetime_days': int(os.getenv('SESSION_LIFETIME_DAYS', '7'))
        },
        'database': {
            'uri': os.getenv('DATABASE_URL', 'sqlite:///app.db'),
            'track_modifications': False,
# Configuración de la aplicación
app = Flask(__name__)
CORS(app)

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///market.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['STATIC_FOLDER'] = 'static'

# Configuración de seguridad para sesiones
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    REMEMBER_COOKIE_SECURE=True,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='Lax'
)

# Configurar ProxyFix para manejar correctamente los headers en producción
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Configurar DATABASE_URL para PostgreSQL en Render
database_url = os.getenv('DATABASE_URL')
if database_url:
    # Handle Render's Postgres URL format
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = config['database']['uri']

# Inicializar SQLAlchemy primero para que esté disponible independientemente de MongoDB
db = SQLAlchemy(app)

# Configuración de MongoDB con manejo de errores
mongo = None
try:
    mongodb_uri = os.environ.get('MONGODB_URI', config['database'].get('mongo_uri'))
    if not mongodb_uri:
        logger.warning("MONGODB_URI no está configurado. Usando URI por defecto.")
        mongodb_uri = 'mongodb://localhost:27017/mimercado'
    
    # Validar formato de URI de MongoDB
    if not (mongodb_uri.startswith('mongodb://') or mongodb_uri.startswith('mongodb+srv://')):
        raise ValueError("Formato de URI de MongoDB inválido. Debe comenzar con 'mongodb://' o 'mongodb+srv://'")
    
    logger.info(f"Configurando MongoDB con URI: {mongodb_uri.split('@')[-1]}")  # Log solo la parte después de @ por seguridad
    app.config["MONGO_URI"] = mongodb_uri
    
    # Inicializar MongoDB
    mongo = PyMongo(app)
    
    # Verificar conexión a MongoDB
    mongo.db.command('ping')
    logger.info(f"Conexión a MongoDB establecida correctamente. Base de datos: {mongo.db.name}")
except Exception as e:
    logger.error(f"Error al configurar o conectar con MongoDB: {str(e)}")
    # MongoDB no estará disponible, pero la aplicación seguirá funcionando con SQLAlchemy
# Configuración de CORS actualizada
CORS(app, 
     supports_credentials=True,
     resources={r"/*": {
         "origins": [
             "https://mimercado.onrender.com", 
             "https://www.mimercado.com", 
             "http://localhost:3000",
             "http://localhost:5000"
         ],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization"],
         "expose_headers": ["Content-Range", "X-Content-Range"],
         "supports_credentials": True
     }})

# Configurar WhiteNoise para servir archivos estáticos eficientemente
app.wsgi_app = WhiteNoise(
    app.wsgi_app,
    root=os.path.join(os.path.dirname(__file__), 'static'),
    prefix='/',
    index_file=True,
    autorefresh=True
)

# Configuración de Stripe
app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY', 'pk_test_your_key')
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY', 'sk_test_4eC39HqLyjWDarjtT1zdp7dc')
stripe.api_key = app.config['STRIPE_SECRET_KEY']

class EstadoPago(Enum):
    PENDIENTE = 'pendiente'
    COMPLETADO = 'completado'
    FALLIDO = 'fallido'
    REEMBOLSADO = 'reembolsado'
def verificar_usuarios():
    """Verifica si existen usuarios en el sistema y crea uno por defecto si no hay ninguno."""
    try:
        cantidad_usuarios = Usuario.query.count()
        if cantidad_usuarios == 0:
            # Crear usuario por defecto
            usuario_default = Usuario(
                email='admin@mimercado.com',
                nombre='Admin',
                apellido='Sistema',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(usuario_default)
            db.session.commit()
            logger.info("Usuario administrador por defecto creado")
            return True
        return False
    except Exception as e:
        logger.error(f"Error al verificar usuarios: {str(e)}")
        return False

# Function to insert payment statuses into MongoDB
def insert_payment_statuses():
    if mongo is None:
        logger.error("No se pueden insertar estados de pago: MongoDB no está disponible")
        return
        
    try:
        # Define the payment statuses
        payment_statuses = [
            {"status": EstadoPago.PENDIENTE.value},
            {"status": EstadoPago.COMPLETADO.value},
            {"status": EstadoPago.FALLIDO.value},
            {"status": EstadoPago.REEMBOLSADO.value}
        ]
        
        # Check if collection exists and has data
        existing_statuses = mongo.db.estados_pago.find_one()
        if existing_statuses:
            logger.info("Los estados de pago ya existen en MongoDB")
            return
            
        # Insert the payment statuses into the 'estados_pago' collection
        result = mongo.db.estados_pago.insert_many(payment_statuses)
        logger.info(f"Estados de pago insertados en MongoDB: {len(result.inserted_ids)} documentos")
    except Exception as e:
        logger.error(f"Error al insertar estados de pago en MongoDB: {str(e)}")

# Example route to trigger the insertion
@app.route('/insert-payment-statuses')
def insert_statuses_route():
    try:
        if mongo is None:
            logger.error("No se pueden insertar estados de pago: MongoDB no está disponible")
            return jsonify({
                "status": "error",
                "message": "MongoDB no está disponible"
            }), 500
            
        insert_payment_statuses()
        logger.info("Estados de pago insertados manualmente a través de la ruta API")
        return jsonify({
            "status": "success",
            "message": "Estados de pago insertados en MongoDB correctamente"
        })
    except Exception as e:
        logger.error(f"Error al insertar estados de pago desde la ruta API: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/test-mongodb')
def test_mongodb():
    try:
        if mongo is None:
            logger.error("La conexión a MongoDB no está disponible")
            return jsonify({
                "status": "error",
                "message": "La conexión a MongoDB no está disponible",
                "details": "MongoDB no está configurado o no se pudo establecer la conexión"
            }), 500
            
        # Intenta una operación simple
        mongo.db.command('ping')
        logger.info("Prueba de conexión a MongoDB exitosa")
        
        # Obtener información de la base de datos
        db_stats = mongo.db.command('dbStats')
        collections = mongo.db.list_collection_names()
        
        logger.info(f"MongoDB stats: {db_stats.get('collections')} colecciones, {db_stats.get('objects')} objetos")
        
        return jsonify({
            "status": "success", 
            "message": "Conectado a MongoDB exitosamente",
            "database": mongo.db.name,
            "collections": collections,
            "stats": {
                "collections": db_stats.get('collections', 0),
                "objects": db_stats.get('objects', 0),
                "dataSize": db_stats.get('dataSize', 0)
            }
        })
    except Exception as e:
        logger.error(f"Error al probar la conexión a MongoDB: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": "Error al conectar con MongoDB",
            "details": str(e)
        }), 500

class MetodoPago(Enum):
    TARJETA = 'tarjeta'
    TRANSFERENCIA = 'transferencia'
    MERCADOPAGO = 'mercadopago'

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre = db.Column(db.String(100), nullable=True)
    apellido = db.Column(db.String(100), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(200), nullable=True)
    ciudad = db.Column(db.String(100), nullable=True)
    codigo_postal = db.Column(db.String(10), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=db.func.current_timestamp())
    productos = db.relationship('Producto', backref='vendedor', lazy=True)
    reviews = db.relationship('Review', backref='usuario', lazy=True)
    direcciones = db.relationship('DireccionEnvio', backref='usuario', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Float, nullable=False)
    imagen_url = db.Column(db.String(200))
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    stock = db.Column(db.Integer, default=0)
    reviews = db.relationship('Review', backref='producto', lazy=True)

    def calificacion_promedio(self):
        if not self.reviews:
            return 0
        return sum(r.calificacion for r in self.reviews) / len(self.reviews)

    def cantidad_reviews(self):
        return len(self.reviews)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    calificacion = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())

    @validates('calificacion')
    def validate_rating(self, key, value):
        if not 1 <= value <= 5:
            raise ValueError('La calificación debe estar entre 1 y 5')
        return value

class CarritoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    fecha_agregado = db.Column(db.DateTime, default=db.func.current_timestamp())

class Orden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(50), default='pendiente')  # pendiente, pagado, enviado, entregado
    total = db.Column(db.Float, nullable=False, default=0)
    items = db.relationship('ItemOrden', backref='orden', lazy=True)

    def calcular_total(self):
        self.total = sum(item.cantidad * item.precio_unitario for item in self.items)
        return self.total

class ItemOrden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('orden.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)

class Pago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    orden_id = db.Column(db.Integer, db.ForeignKey('orden.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    moneda = db.Column(db.String(3), default='ARS')
    estado = db.Column(db.String(20), nullable=False, default=EstadoPago.PENDIENTE.value)
    metodo_pago = db.Column(db.String(20), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    fecha_actualizacion = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    usuario = db.relationship('Usuario', backref=db.backref('pagos', lazy=True))
    orden = db.relationship('Orden', backref=db.backref('pagos', lazy=True))

class Factura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    pago_id = db.Column(db.Integer, db.ForeignKey('pago.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_emision = db.Column(db.DateTime, default=db.func.current_timestamp())
    subtotal = db.Column(db.Float, nullable=False)
    iva = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    razon_social = db.Column(db.String(200))
    cuit = db.Column(db.String(20))
    direccion_facturacion = db.Column(db.String(200))
    tipo_factura = db.Column(db.String(1), default='B')  # A, B, C

    pago = db.relationship('Pago', backref=db.backref('factura', uselist=False))
    usuario = db.relationship('Usuario', backref=db.backref('facturas', lazy=True))

    def generar_numero(self):
        ultimo_numero = Factura.query.order_by(Factura.numero.desc()).first()
        if ultimo_numero:
            try:
                num = int(ultimo_numero.numero) + 1
            except ValueError:
                num = 1
        else:
            num = 1
        self.numero = f"{num:08d}"

class DireccionEnvio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    calle = db.Column(db.String(200), nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    piso = db.Column(db.String(10))
    departamento = db.Column(db.String(10))
    codigo_postal = db.Column(db.String(10), nullable=False)
    ciudad = db.Column(db.String(100), nullable=False)
    provincia = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    es_principal = db.Column(db.Boolean, default=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

def crear_productos_ejemplo():
    # Verificar si existe un usuario administrador
    admin = Usuario.query.filter_by(email='admin@mimercado.com').first()
    if not admin:
        # Si no existe el usuario de verificar_usuarios(), crear uno para los productos
        admin = Usuario.query.filter_by(email='admin@example.com').first()
        if not admin:
            admin = Usuario(
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                nombre='Admin',
                apellido='User'
            )
            db.session.add(admin)
            db.session.commit()

    productos = [
        {
            'titulo': 'Laptop HP Pavilion',
            'descripcion': 'Laptop con procesador Intel i5, 8GB RAM, 256GB SSD',
            'precio': 799.99,
            'imagen_url': '/static/images/laptop.jpg',
            'stock': 10
        },
        {
            'titulo': 'Smartphone Samsung Galaxy',
            'descripcion': 'Teléfono Android con 128GB, cámara triple, 5G',
            'precio': 699.99,
            'imagen_url': '/static/images/phone.jpg',
            'stock': 15
        },
        {
            'titulo': 'Tablet Apple iPad',
            'descripcion': 'iPad de 10.2 pulgadas, 64GB, WiFi',
            'precio': 329.99,
            'imagen_url': '/static/images/tablet.jpg',
            'stock': 8
        },
        {
            'titulo': 'Smartwatch Apple Watch',
            'descripcion': 'Series 7, GPS, caja de aluminio',
            'precio': 399.99,
            'imagen_url': '/static/images/watch.jpg',
            'stock': 12
        },
        {
            'titulo': 'Auriculares Sony WH-1000XM4',
            'descripcion': 'Auriculares inalámbricos con cancelación de ruido',
            'precio': 349.99,
            'imagen_url': '/static/images/headphones.jpg',
            'stock': 20
        }
    ]

    # Verificar si ya existen productos
    if Producto.query.first() is not None:
        print("Ya existen productos")
        return

    for producto_data in productos:
        producto = Producto(
            titulo=producto_data['titulo'],
            descripcion=producto_data['descripcion'],
            precio=producto_data['precio'],
            imagen_url=producto_data['imagen_url'],
            stock=producto_data['stock'],
            vendedor_id=1  # ID del usuario administrador
        )
        db.session.add(producto)
    
    try:
        db.session.commit()
        print("Productos de ejemplo creados exitosamente")
    except Exception as e:
        db.session.rollback()
        print("Error al crear productos de ejemplo:", str(e))

def recreate_db():
    with app.app_context():
        # Eliminar todas las tablas
        db.drop_all()
        logger.info("Base de datos eliminada")
        
        # Crear todas las tablas nuevamente
        db.create_all()
        logger.info("Base de datos recreada")
        
        # Verificar y crear usuario inicial si es necesario
        verificar_usuarios()
        
        # Crear productos de ejemplo
        crear_productos_ejemplo()

# Recrear la base de datos al arrancar
recreate_db()

# Rutas para servir archivos estáticos
@app.route('/api/health')
def health_check():
    db_status = "connected"
    mongo_status = "connected"
    mongo_details = {}
    
    # Verificar estado de MongoDB
    if mongo is not None:
        try:
            mongo.db.command('ping')
            mongo_details = {
                "database_name": mongo.db.name,
                "collections": len(mongo.db.list_collection_names())
            }
        except Exception as e:
            mongo_status = "error"
            mongo_details = {"error": str(e)}
            logger.error(f"Error de conexión a MongoDB en health check: {str(e)}")
    else:
        mongo_status = "unavailable"
        mongo_details = {"reason": "MongoDB no está configurado o no se pudo establecer la conexión inicial"}
    
    # Verificar estado de SQL
    try:
        db.session.execute("SELECT 1")
    except Exception as e:
        db_status = "error"
        logger.error(f"Error de conexión a SQL en health check: {str(e)}")
    
    # Determinar el estado general de la aplicación
    overall_status = "healthy" if db_status == "connected" else "degraded"
    
    return jsonify({
        'status': overall_status,
        'message': 'Mi Mercado API is running' if overall_status == "healthy" else "Mi Mercado API is running with limited functionality",
        'timestamp': datetime.now().isoformat(),
        'databases': {
            'sql': {
                'status': db_status,
                'required': True
            },
            'mongodb': {
                'status': mongo_status,
                'required': False,
                'details': mongo_details
            }
        }
    })

@app.route('/health')
def simple_health_check():
    return 'OK', 200

@app.route('/api/system/status', methods=['GET'])
def system_status():
    try:
        # Verificar estado de la base de datos
        usuarios_count = Usuario.query.count()
        productos_count = Producto.query.count()
        
        return jsonify({
            'status': 'operational',
            'database': {
                'usuarios': usuarios_count,
                'productos': productos_count,
                'needs_setup': usuarios_count == 0
            },
            'message': 'Sistema funcionando correctamente'
        })
    except Exception as e:
        logger.error(f"Error al verificar estado del sistema: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def catch_all(path):
    if '.' not in path:  # Si no es un archivo estático
        return send_from_directory('static', 'index.html')
    return send_from_directory('static', path)

# Rutas de la API
@app.route('/api/login', methods=['POST'])
def login():
    print("Recibiendo solicitud de login")  # Debug
    data = request.get_json()
    
    if not data:
        print("No se recibieron datos")  # Debug
        return jsonify({'error': 'No se recibieron datos'}), 400
        
    email = data.get('email')
    password = data.get('password')

    print(f"Intentando login con email: {email}")  # Debug

    if not email or not password:
        print("Falta email o contraseña")  # Debug
        return jsonify({'error': 'Falta email o contraseña'}), 400

    try:
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.check_password(password):
            session['user_id'] = usuario.id
            session.permanent = True  # La sesión durará más tiempo
            print(f"Login exitoso para usuario: {email}")  # Debug
            return jsonify({'success': True, 'message': 'Login exitoso'})
        
        print("Credenciales incorrectas")  # Debug
        return jsonify({'error': 'Credenciales incorrectas'}), 401
        
    except Exception as e:
        print(f"Error en login: {str(e)}")  # Debug
        return jsonify({'error': 'Error al procesar el login'}), 500


@app.route('/api/check-auth')
def check_auth():
    if 'user_id' in session:
        return jsonify({'authenticated': True}), 200
    else:
        return jsonify({'authenticated': False}), 200  # No redirigir, solo devolver el estado

@app.route('/api/productos', methods=['POST'])
def crear_producto():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
        
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400
        
    titulo = data.get('titulo')
    descripcion = data.get('descripcion')
    precio = data.get('precio')
    imagen_url = data.get('imagen_url')
    
    if not all([titulo, descripcion, precio]):
        return jsonify({'error': 'Faltan datos requeridos'}), 400
    
    try:
        nuevo_producto = Producto(
            titulo=titulo,
            descripcion=descripcion,
            precio=float(precio),
            imagen_url=imagen_url,
            vendedor_id=session['user_id']
        )
        
        db.session.add(nuevo_producto)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Producto creado exitosamente',
            'producto_id': nuevo_producto.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error al crear el producto'}), 500

@app.route('/api/productos', methods=['GET'])
def obtener_productos():
    try:
        productos = Producto.query.all()
        return jsonify([{
            'id': p.id,
            'titulo': p.titulo,
            'descripcion': p.descripcion,
            'precio': p.precio,
            'imagen_url': p.imagen_url,
            'stock': p.stock,
            'vendedor_id': p.vendedor_id
        } for p in productos])
    except Exception as e:
        print('Error al obtener productos:', str(e))
        return jsonify({'error': 'Error al obtener productos'}), 500

@app.route('/api/productos/buscar')
def buscar_productos():
    query = request.args.get('q', '').lower()
    try:
        if not query:
            return obtener_productos()
            
        productos = Producto.query.filter(
            db.or_(
                Producto.titulo.ilike(f'%{query}%'),
                Producto.descripcion.ilike(f'%{query}%')
            )
        ).all()
        
        return jsonify([{
            'id': p.id,
            'titulo': p.titulo,
            'descripcion': p.descripcion,
            'precio': p.precio,
            'imagen_url': p.imagen_url,
            'stock': p.stock,
            'vendedor_id': p.vendedor_id,
            'fecha_creacion': p.fecha_creacion.isoformat()
        } for p in productos])
    except Exception as e:
        print('Error en búsqueda:', str(e))
        return jsonify({'error': 'Error al buscar productos'}), 500

@app.route('/api/productos/<int:producto_id>', methods=['GET'])
def obtener_producto(producto_id):
    try:
        producto = Producto.query.get_or_404(producto_id)
        return jsonify({
            'id': producto.id,
            'titulo': producto.titulo,
            'descripcion': producto.descripcion,
            'precio': producto.precio,
            'imagen_url': producto.imagen_url,
            'stock': producto.stock,
            'vendedor_id': producto.vendedor_id
        })
    except Exception as e:
        print('Error al obtener producto:', str(e))
        return jsonify({'error': 'Error al obtener producto'}), 500

@app.route('/api/carrito', methods=['GET'])
def obtener_carrito():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        items = CarritoItem.query.filter_by(usuario_id=session['user_id']).all()
        carrito = []
        for item in items:
            producto = Producto.query.get(item.producto_id)
            if producto:
                carrito.append({
                    'id': item.id,
                    'producto_id': item.producto_id,
                    'titulo': producto.titulo,
                    'precio': producto.precio,
                    'cantidad': item.cantidad,
                    'imagen_url': producto.imagen_url
                })
        return jsonify(carrito)
    except Exception as e:
        print('Error al obtener carrito:', str(e))
        return jsonify({'error': 'Error al obtener el carrito'}), 500

@app.route('/api/carrito/agregar', methods=['POST'])
def agregar_al_carrito():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    data = request.get_json()
    if not data or 'producto_id' not in data:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    try:
        producto_id = data['producto_id']
        cantidad = data.get('cantidad', 1)
        
        # Verificar si el producto existe
        producto = Producto.query.get(producto_id)
        if not producto:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        # Verificar si hay suficiente stock
        if producto.stock < cantidad:
            return jsonify({'error': 'No hay suficiente stock disponible'}), 400
        
        # Verificar si ya existe en el carrito
        item = CarritoItem.query.filter_by(
            usuario_id=session['user_id'],
            producto_id=producto_id
        ).first()
        
        if item:
            # Verificar si hay suficiente stock para la cantidad total
            if producto.stock < (item.cantidad + cantidad):
                return jsonify({'error': 'No hay suficiente stock disponible'}), 400
            item.cantidad += cantidad
        else:
            item = CarritoItem(
                usuario_id=session['user_id'],
                producto_id=producto_id,
                cantidad=cantidad
            )
            db.session.add(item)
        
        # Obtener el total de items en el carrito
        total_items = sum([item.cantidad for item in CarritoItem.query.filter_by(usuario_id=session['user_id']).all()])
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Producto agregado al carrito',
            'total_items': total_items
        })
    except Exception as e:
        db.session.rollback()
        print('Error al agregar al carrito:', str(e))
        return jsonify({'error': 'Error al agregar al carrito'}), 500

@app.route('/api/carrito/eliminar/<int:item_id>', methods=['DELETE'])
def eliminar_del_carrito(item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        item = CarritoItem.query.filter_by(
            id=item_id,
            usuario_id=session['user_id']
        ).first()
        
        if not item:
            return jsonify({'error': 'Item no encontrado'}), 404
        
        db.session.delete(item)
        
        # Obtener el total de items en el carrito antes de hacer commit
        total_items = sum([item.cantidad for item in CarritoItem.query.filter_by(usuario_id=session['user_id']).all()])
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Item eliminado del carrito',
            'total_items': total_items - item.cantidad  # Restar la cantidad del item eliminado
        })
    except Exception as e:
        db.session.rollback()
        print('Error al eliminar del carrito:', str(e))
        return jsonify({'error': 'Error al eliminar del carrito'}), 500

@app.route('/api/carrito/vaciar', methods=['DELETE'])
def vaciar_carrito():
    try:
        # Imprimir información de depuración
        print('Intentando vaciar carrito...')
        print(f'Sesión actual: {session}')
        
        # Verificar si el usuario está autenticado
        if 'user_id' not in session:
            print('Error: No hay sesión de usuario')
            return jsonify({'error': 'No autorizado', 'details': 'No hay sesión activa'}), 401

        # Obtener el ID de usuario de la sesión
        usuario_id = session['user_id']
        print(f'ID de usuario: {usuario_id}')

        # Verificar si hay items en el carrito antes de intentar eliminar
        items_en_carrito = CarritoItem.query.filter_by(usuario_id=usuario_id).all()
        print(f'Número de items en el carrito: {len(items_en_carrito)}')

        if not items_en_carrito:
            print('El carrito ya está vacío')
            return jsonify({'message': 'El carrito ya está vacío'}), 200

        # Eliminar todos los items del carrito para el usuario actual
        deleted_count = CarritoItem.query.filter_by(usuario_id=usuario_id).delete(synchronize_session=False)
        print(f'Número de items eliminados: {deleted_count}')
        
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Carrito vaciado exitosamente', 
            'deleted_items': deleted_count
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f'Error crítico al vaciar el carrito: {str(e)}')
        import traceback
        traceback.print_exc()  # Imprimir el stack trace completo
        return jsonify({
            'success': False,
            'error': 'Error al vaciar el carrito', 
            'details': str(e)
        }), 500

@app.route('/api/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        # Obtener items del carrito
        items = CarritoItem.query.filter_by(usuario_id=session['user_id']).all()
        if not items:
            return jsonify({'error': 'El carrito está vacío'}), 400
        
        # Calcular total
        total = 0
        orden_items = []
        for item in items:
            producto = Producto.query.get(item.producto_id)
            if producto:
                total += producto.precio * item.cantidad
                orden_items.append({
                    'producto_id': producto.id,
                    'cantidad': item.cantidad,
                    'precio_unitario': producto.precio
                })
        
        # Crear orden
        orden = Orden(
            usuario_id=session['user_id'],
            total=total
        )
        db.session.add(orden)
        db.session.flush()
        
        # Crear items de la orden
        for item in orden_items:
            orden_item = ItemOrden(
                orden_id=orden.id,
                producto_id=item['producto_id'],
                cantidad=item['cantidad'],
                precio_unitario=item['precio_unitario']
            )
            db.session.add(orden_item)
        
        # Limpiar carrito
        for item in items:
            db.session.delete(item)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Orden creada exitosamente',
            'orden_id': orden.id,
            'total': total
        })
        
    except Exception as e:
        db.session.rollback()
        print('Error en checkout:', str(e))
        return jsonify({'error': 'Error al procesar la orden'}), 500

@app.route('/api/ordenes', methods=['GET'])
def obtener_ordenes():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        ordenes = Orden.query.filter_by(usuario_id=session['user_id']).order_by(Orden.fecha_creacion.desc()).all()
        return jsonify([{
            'id': o.id,
            'fecha': o.fecha_creacion.isoformat(),
            'estado': o.estado,
            'total': o.total
        } for o in ordenes])
    except Exception as e:
        print('Error al obtener órdenes:', str(e))
        return jsonify({'error': 'Error al obtener órdenes'}), 500

@app.route('/api/ordenes', methods=['POST'])
def crear_orden():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        data = request.get_json()
        items = data.get('items', [])

        if not items:
            return jsonify({'error': 'El carrito está vacío'}), 400

        # Verificar que los productos existen y tienen stock
        for item in items:
            producto = Producto.query.get(item['id'])
            if not producto:
                return jsonify({'error': f'Producto {item["id"]} no encontrado'}), 404
            if producto.stock < item['cantidad']:
                return jsonify({'error': f'Stock insuficiente para {producto.titulo}'}), 400

        # Crear la orden
        orden = Orden(
            usuario_id=session['user_id'],
            estado='pendiente',
            fecha_creacion=datetime.now()
        )
        db.session.add(orden)
        db.session.flush()  # Para obtener el ID de la orden

        # Agregar items a la orden y actualizar stock
        for item in items:
            producto = Producto.query.get(item['id'])
            item_orden = ItemOrden(
                orden_id=orden.id,
                producto_id=item['id'],
                cantidad=item['cantidad'],
                precio_unitario=producto.precio  # Usar el precio actual del producto
            )
            # Actualizar stock
            producto.stock -= item['cantidad']
            db.session.add(item_orden)
        
        # Calcular y guardar el total
        orden.calcular_total()
        db.session.commit()

        return jsonify({
            'success': True,
            'orden_id': orden.id,
            'message': 'Orden creada exitosamente'
        })

    except Exception as e:
        db.session.rollback()
        print('Error al crear orden:', str(e))
        return jsonify({'error': 'Error al crear la orden'}), 500

@app.route('/api/ordenes/<int:orden_id>', methods=['GET'])
def obtener_orden(orden_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        orden = Orden.query.get(orden_id)
        if not orden:
            return jsonify({'error': 'Orden no encontrada'}), 404

        if orden.usuario_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        # Calcular subtotal
        subtotal = sum(item.cantidad * item.precio_unitario for item in orden.items)

        return jsonify({
            'id': orden.id,
            'fecha': orden.fecha_creacion.isoformat(),
            'estado': orden.estado,
            'subtotal': subtotal,
            'items': [{
                'id': item.producto_id,
                'cantidad': item.cantidad,
                'precio_unitario': item.precio_unitario,
                'subtotal': item.cantidad * item.precio_unitario
            } for item in orden.items]
        })

    except Exception as e:
        print('Error al obtener orden:', str(e))
        return jsonify({'error': 'Error al obtener la orden'}), 500

@app.route('/api/perfil', methods=['GET'])
def obtener_perfil():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        usuario = Usuario.query.get(session['user_id'])
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
            
        return jsonify({
            'email': usuario.email,
            'nombre': usuario.nombre,
            'apellido': usuario.apellido,
            'telefono': usuario.telefono,
            'direccion': usuario.direccion,
            'ciudad': usuario.ciudad,
            'codigo_postal': usuario.codigo_postal
        })
    except Exception as e:
        print('Error al obtener perfil:', str(e))
        return jsonify({'error': 'Error al obtener perfil'}), 500

@app.route('/api/perfil', methods=['PUT'])
def actualizar_perfil():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        usuario = Usuario.query.get(session['user_id'])
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos'}), 400
            
        # Actualizar campos del perfil
        if 'nombre' in data:
            usuario.nombre = data['nombre']
        if 'apellido' in data:
            usuario.apellido = data['apellido']
        if 'telefono' in data:
            usuario.telefono = data['telefono']
        if 'direccion' in data:
            usuario.direccion = data['direccion']
        if 'ciudad' in data:
            usuario.ciudad = data['ciudad']
        if 'codigo_postal' in data:
            usuario.codigo_postal = data['codigo_postal']
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Perfil actualizado exitosamente'})
    except Exception as e:
        db.session.rollback()
        print('Error al actualizar perfil:', str(e))
        return jsonify({'error': 'Error al actualizar perfil'}), 500

@app.route('/api/cambiar-password', methods=['POST'])
def cambiar_password():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401
    
    try:
        usuario = Usuario.query.get(session['user_id'])
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
            
        data = request.get_json()
        if not data or 'password_actual' not in data or 'password_nuevo' not in data:
            return jsonify({'error': 'Faltan datos requeridos'}), 400
            
        # Verificar contraseña actual
        if not usuario.check_password(data['password_actual']):
            return jsonify({'error': 'Contraseña actual incorrecta'}), 400
            
        # Actualizar contraseña
        usuario.set_password(data['password_nuevo'])
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Contraseña actualizada exitosamente'})
    except Exception as e:
        db.session.rollback()
        print('Error al cambiar contraseña:', str(e))
        return jsonify({'error': 'Error al cambiar contraseña'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Sesión cerrada exitosamente'})

# Rutas para pagos y facturación
@app.route('/api/pagos/crear-intento', methods=['POST'])
def crear_intento_pago():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        data = request.get_json()
        orden_id = data.get('orden_id')
        metodo_pago = data.get('metodo_pago')

        # Obtener la orden
        orden = Orden.query.get(orden_id)
        if not orden:
            return jsonify({'error': 'Orden no encontrada'}), 404

        # Calcular el monto total
        monto_total = sum(item.cantidad * item.precio_unitario for item in orden.items)
        
        # Crear intento de pago en Stripe
        if metodo_pago == MetodoPago.TARJETA.value:
            try:
                intent = stripe.PaymentIntent.create(
                    amount=int(monto_total * 100),  # Stripe usa centavos
                    currency='ars',
                    metadata={'orden_id': orden_id}
                )
                
                # Crear registro de pago en la base de datos
                pago = Pago(
                    usuario_id=session['user_id'],
                    orden_id=orden_id,
                    monto=monto_total,
                    metodo_pago=metodo_pago,
                    stripe_payment_intent_id=intent.id
                )
                db.session.add(pago)
                db.session.commit()

                return jsonify({
                    'clientSecret': intent.client_secret,
                    'pago_id': pago.id
                })

            except stripe.error.StripeError as e:
                return jsonify({'error': str(e)}), 400

        # Manejar otros métodos de pago
        elif metodo_pago == MetodoPago.TRANSFERENCIA.value:
            # Crear pago pendiente para transferencia bancaria
            pago = Pago(
                usuario_id=session['user_id'],
                orden_id=orden_id,
                monto=monto_total,
                metodo_pago=metodo_pago
            )
            db.session.add(pago)
            db.session.commit()

            return jsonify({
                'pago_id': pago.id,
                'instrucciones': 'Realice la transferencia a la siguiente cuenta bancaria: XXX'
            })

        else:
            return jsonify({'error': 'Método de pago no soportado'}), 400

    except Exception as e:
        db.session.rollback()
        print('Error al crear intento de pago:', str(e))
        return jsonify({'error': 'Error al procesar el pago'}), 500

@app.route('/api/pagos/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, 'tu_stripe_webhook_secret'
        )

        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            pago = Pago.query.filter_by(stripe_payment_intent_id=payment_intent.id).first()
            
            if pago:
                pago.estado = EstadoPago.COMPLETADO.value
                db.session.commit()

                # Generar factura
                generar_factura(pago)

        elif event.type == 'payment_intent.payment_failed':
            payment_intent = event.data.object
            pago = Pago.query.filter_by(stripe_payment_intent_id=payment_intent.id).first()
            
            if pago:
                pago.estado = EstadoPago.FALLIDO.value
                db.session.commit()

        return jsonify({'status': 'success'})

    except Exception as e:
        print('Error en webhook:', str(e))
        return jsonify({'error': str(e)}), 400

def generar_factura(pago):
    try:
        usuario = Usuario.query.get(pago.usuario_id)
        
        # Calcular montos
        subtotal = pago.monto / 1.21  # Asumiendo IVA del 21%
        iva = pago.monto - subtotal

        factura = Factura(
            pago_id=pago.id,
            usuario_id=pago.usuario_id,
            subtotal=subtotal,
            iva=iva,
            total=pago.monto,
            razon_social=f"{usuario.nombre} {usuario.apellido}",
            direccion_facturacion=usuario.direccion
        )
        factura.generar_numero()
        
        db.session.add(factura)
        db.session.commit()

        return factura

    except Exception as e:
        print('Error al generar factura:', str(e))
        db.session.rollback()
        raise

@app.route('/api/facturas/<int:factura_id>', methods=['GET'])
def obtener_factura(factura_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        factura = Factura.query.get(factura_id)
        if not factura:
            return jsonify({'error': 'Factura no encontrada'}), 404

        if factura.usuario_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        return jsonify({
            'numero': factura.numero,
            'fecha_emision': factura.fecha_emision.isoformat(),
            'razon_social': factura.razon_social,
            'cuit': factura.cuit,
            'direccion': factura.direccion_facturacion,
            'tipo_factura': factura.tipo_factura,
            'subtotal': factura.subtotal,
            'iva': factura.iva,
            'total': factura.total
        })

    except Exception as e:
        print('Error al obtener factura:', str(e))
        return jsonify({'error': 'Error al obtener factura'}), 500

@app.route('/api/pagos/<int:pago_id>', methods=['GET'])
def obtener_pago(pago_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        pago = Pago.query.get(pago_id)
        if not pago:
            return jsonify({'error': 'Pago no encontrado'}), 404

        if pago.usuario_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        return jsonify({
            'id': pago.id,
            'orden_id': pago.orden_id,
            'monto': pago.monto,
            'estado': pago.estado,
            'metodo_pago': pago.metodo_pago,
            'fecha_creacion': pago.fecha_creacion.isoformat(),
            'fecha_actualizacion': pago.fecha_actualizacion.isoformat()
        })

    except Exception as e:
        print('Error al obtener pago:', str(e))
        return jsonify({'error': 'Error al obtener pago'}), 500

@app.route('/api/facturas/<int:pago_id>/descargar', methods=['GET'])
def descargar_factura(pago_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        # Buscar la factura asociada al pago
        factura = Factura.query.filter_by(pago_id=pago_id).first()
        if not factura:
            return jsonify({'error': 'Factura no encontrada'}), 404

        if factura.usuario_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        # Generar PDF de la factura
        pdf_content = generar_pdf_factura(factura)
        
        # Crear respuesta con el PDF
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=factura_{factura.numero}.pdf'
        
        return response

    except Exception as e:
        print('Error al descargar factura:', str(e))
        return jsonify({'error': 'Error al descargar factura'}), 500

def generar_pdf_factura(factura):
    try:
        # Aquí usaremos ReportLab para generar el PDF
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO

        # Crear buffer para el PDF
        buffer = BytesIO()
        
        # Crear el documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Contenido del documento
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        elements.append(Paragraph(f"FACTURA {factura.tipo_factura}", styles['Title']))
        elements.append(Spacer(1, 20))
        
        # Información de la empresa
        elements.append(Paragraph("Mi Mercado", styles['Heading1']))
        elements.append(Paragraph("CUIT: XX-XXXXXXXX-X", styles['Normal']))
        elements.append(Paragraph("Dirección: Calle Ejemplo 123", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Información del cliente
        elements.append(Paragraph("DATOS DEL CLIENTE", styles['Heading2']))
        elements.append(Paragraph(f"Razón Social: {factura.razon_social}", styles['Normal']))
        elements.append(Paragraph(f"CUIT: {factura.cuit}", styles['Normal']))
        elements.append(Paragraph(f"Dirección: {factura.direccion_facturacion}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Detalles de la factura
        data = [
            ['Concepto', 'Subtotal', 'IVA', 'Total'],
            ['Productos', f"${factura.subtotal:.2f}", f"${factura.iva:.2f}", f"${factura.total:.2f}"]
        ]
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        
        # Construir PDF
        doc.build(elements)
        
        # Obtener el contenido del PDF
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content

    except Exception as e:
        print('Error al generar PDF:', str(e))
        raise

@app.route('/api/pagos/<int:pago_id>/comprobante', methods=['POST'])
def subir_comprobante(pago_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        pago = Pago.query.get(pago_id)
        if not pago:
            return jsonify({'error': 'Pago no encontrado'}), 404

        if pago.usuario_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        if 'comprobante' not in request.files:
            return jsonify({'error': 'No se envió ningún archivo'}), 400

        archivo = request.files['comprobante']
        if archivo.filename == '':
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

        if archivo and allowed_file(archivo.filename):
            # Crear directorio si no existe
            comprobantes_dir = os.path.join(app.root_path, 'comprobantes')
            if not os.path.exists(comprobantes_dir):
                os.makedirs(comprobantes_dir)

            # Guardar archivo
            filename = secure_filename(f"comprobante_{pago_id}_{archivo.filename}")
            archivo.save(os.path.join(comprobantes_dir, filename))

            # Actualizar estado del pago
            pago.estado = EstadoPago.PENDIENTE.value
            db.session.commit()

            return jsonify({'success': True, 'message': 'Comprobante recibido'})
        else:
            return jsonify({'error': 'Tipo de archivo no permitido'}), 400

    except Exception as e:
        print('Error al subir comprobante:', str(e))
        return jsonify({'error': 'Error al procesar el comprobante'}), 500

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Rutas para gestión de direcciones de envío
@app.route('/api/direcciones', methods=['GET'])
def obtener_direcciones():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        direcciones = DireccionEnvio.query.filter_by(usuario_id=session['user_id']).all()
        return jsonify([{
            'id': d.id,
            'calle': d.calle,
            'numero': d.numero,
            'piso': d.piso,
            'departamento': d.departamento,
            'codigo_postal': d.codigo_postal,
            'ciudad': d.ciudad,
            'provincia': d.provincia,
            'telefono': d.telefono,
            'es_principal': d.es_principal
        } for d in direcciones])
    except Exception as e:
        print('Error al obtener direcciones:', str(e))
        return jsonify({'error': 'Error al obtener direcciones'}), 500

@app.route('/api/direcciones', methods=['POST'])
def crear_direccion():
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        data = request.get_json()
        nueva_direccion = DireccionEnvio(
            usuario_id=session['user_id'],
            calle=data['calle'],
            numero=data['numero'],
            piso=data.get('piso'),
            departamento=data.get('departamento'),
            codigo_postal=data['codigo_postal'],
            ciudad=data['ciudad'],
            provincia=data['provincia'],
            telefono=data['telefono'],
            es_principal=data.get('es_principal', False)
        )

        if nueva_direccion.es_principal:
            # Desmarcar otras direcciones principales
            DireccionEnvio.query.filter_by(
                usuario_id=session['user_id'],
                es_principal=True
            ).update({'es_principal': False})

        db.session.add(nueva_direccion)
        db.session.commit()

        return jsonify({
            'success': True,
            'direccion_id': nueva_direccion.id,
            'message': 'Dirección creada exitosamente'
        })
    except Exception as e:
        db.session.rollback()
        print('Error al crear dirección:', str(e))
        return jsonify({'error': 'Error al crear dirección'}), 500

# Rutas para gestión de productos (vendedores)
@app.route('/api/productos/<int:producto_id>', methods=['PUT'])
def editar_producto(producto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        producto = Producto.query.get(producto_id)
        if not producto:
            return jsonify({'error': 'Producto no encontrado'}), 404

        if producto.vendedor_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        data = request.get_json()
        producto.titulo = data.get('titulo', producto.titulo)
        producto.descripcion = data.get('descripcion', producto.descripcion)
        producto.precio = data.get('precio', producto.precio)
        producto.stock = data.get('stock', producto.stock)
        producto.imagen_url = data.get('imagen_url', producto.imagen_url)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Producto actualizado exitosamente'
        })
    except Exception as e:
        db.session.rollback()
        print('Error al actualizar producto:', str(e))
        return jsonify({'error': 'Error al actualizar producto'}), 500

@app.route('/api/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        producto = Producto.query.get(producto_id)
        if not producto:
            return jsonify({'error': 'Producto no encontrado'}), 404

        if producto.vendedor_id != session['user_id']:
            return jsonify({'error': 'No autorizado'}), 403

        db.session.delete(producto)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Producto eliminado exitosamente'
        })
    except Exception as e:
        db.session.rollback()
        print('Error al eliminar producto:', str(e))
        return jsonify({'error': 'Error al eliminar producto'}), 500

# Rutas para reseñas y calificaciones
@app.route('/api/productos/<int:producto_id>/reviews', methods=['GET'])
def obtener_reviews(producto_id):
    try:
        reviews = Review.query.filter_by(producto_id=producto_id).all()
        return jsonify([{
            'id': r.id,
            'usuario_id': r.usuario_id,
            'calificacion': r.calificacion,
            'comentario': r.comentario,
            'fecha_creacion': r.fecha_creacion.isoformat()
        } for r in reviews])
    except Exception as e:
        print('Error al obtener reviews:', str(e))
        return jsonify({'error': 'Error al obtener reviews'}), 500

@app.route('/api/productos/<int:producto_id>/reviews', methods=['POST'])
def crear_review(producto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debe iniciar sesión'}), 401

    try:
        # Verificar si el usuario ya ha dejado una review
        review_existente = Review.query.filter_by(
            producto_id=producto_id,
            usuario_id=session['user_id']
        ).first()

        if review_existente:
            return jsonify({'error': 'Ya has dejado una review para este producto'}), 400

        data = request.get_json()
        nueva_review = Review(
            producto_id=producto_id,
            usuario_id=session['user_id'],
            calificacion=data['calificacion'],
            comentario=data.get('comentario')
        )

        db.session.add(nueva_review)
        db.session.commit()

        return jsonify({
            'success': True,
            'review_id': nueva_review.id,
            'message': 'Review creada exitosamente'
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print('Error al crear review:', str(e))
        return jsonify({'error': 'Error al crear review'}), 500

@app.route('/api/productos/<int:producto_id>/stats', methods=['GET'])
def obtener_stats_producto(producto_id):
    try:
        producto = Producto.query.get_or_404(producto_id)
        return jsonify({
            'calificacion_promedio': producto.calificacion_promedio(),
            'cantidad_reviews': producto.cantidad_reviews(),
            'stock_disponible': producto.stock
        })
    except Exception as e:
        print('Error al obtener estadísticas:', str(e))
        return jsonify({'error': 'Error al obtener estadísticas'}), 500

@app.errorhandler(404)
def handle_404_error(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found'
    }), 404

@app.errorhandler(500)
def handle_500_error(error):
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(error)
    }), 500

# Inicializar MongoDB con datos necesarios al arrancar
with app.app_context():
    if mongo is not None:
        try:
            # Verificar conexión a MongoDB
            mongo.db.command('ping')
            logger.info("Verificación de conexión a MongoDB exitosa")
            
            # Insertar estados de pago si no existen
            insert_payment_statuses()
            
            # Listar colecciones disponibles
            collections = mongo.db.list_collection_names()
            logger.info(f"Colecciones disponibles en MongoDB: {collections}")
        except Exception as e:
            logger.error(f"Error de inicialización de MongoDB: {str(e)}")
            # Marcar MongoDB como no disponible si hay error durante la inicialización
            mongo = None
    else:
        logger.warning("MongoDB no está disponible. La aplicación funcionará con funcionalidad limitada.")

if __name__ == '__main__':
    # Obtener el puerto desde las variables de entorno
    port = int(os.environ.get('PORT', 80))
    # Ejecutar la aplicación
    app.run(host='0.0.0.0', port=port)
