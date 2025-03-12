# Lista de Verificación para Render con MongoDB

## Archivos Necesarios
- [x] `Procfile` con el contenido: `web: gunicorn app:app`
- [x] `requirements.txt` con dependencias de MongoDB (pymongo, dnspython)
- [x] `app.py` con configuración de MongoDB

## Configuración en el Dashboard de Render
1. **Configuración Básica**
   - Nombre del servicio: mimercado
   - Tipo: Web Service
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: (dejar en blanco, usar Procfile)

2. **Variables de Entorno Importantes**
   ```
   PORT=10000
   FLASK_ENV=production
   MONGODB_URI=mongodb+srv://usuario:contraseña@cluster.mongodb.net/nombre_base_datos?retryWrites=true&w=majority
   SECRET_KEY=tu_clave_secreta
   ```

3. **Configuración de MongoDB**
   - Asegúrate de que tu cluster de MongoDB Atlas esté activo
   - Verifica que la IP de Render esté en la lista blanca de MongoDB Atlas
   - La URL de MongoDB debe ser del tipo Atlas (mongodb+srv://)
   - Verifica que el usuario tenga permisos correctos

## Pasos para Verificar MongoDB
1. En MongoDB Atlas:
   - Verifica que el cluster esté activo
   - Ve a Network Access y añade 0.0.0.0/0 para permitir acceso desde cualquier IP
   - Verifica que el usuario tenga rol de readWrite en la base de datos

2. En Render:
   - Verifica que MONGODB_URI esté correctamente configurado
   - Asegúrate de que la URL incluya el nombre de la base de datos
   - Revisa los logs buscando errores de conexión a MongoDB

## Solución de Problemas
1. Verifica los logs en Render para errores de MongoDB
2. Prueba la ruta /health para verificar la conexión a MongoDB
3. Si hay errores de conexión:
   - Verifica el formato de la URL de MongoDB
   - Confirma que las credenciales sean correctas
   - Asegúrate de que el cluster esté accesible
4. Verifica la configuración de CORS si hay problemas de acceso desde el frontend
