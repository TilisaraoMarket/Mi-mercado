# Pasos de Seguridad para MongoDB

1. En MongoDB Atlas:
   - Crear un nuevo usuario con permisos limitados
   - Configurar Network Access para permitir solo IPs necesarias
   - Habilitar autenticación de dos factores
   - Monitorear el acceso a la base de datos

2. En Render:
   - Configurar variables de entorno de forma segura
   - No exponer credenciales en el código
   - Usar HTTPS para todas las conexiones
   - Configurar CORS apropiadamente

3. Buenas Prácticas:
   - Rotar contraseñas regularmente
   - Mantener backups regulares
   - Monitorear logs de acceso
   - Usar el principio de mínimo privilegio