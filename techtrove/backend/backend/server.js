const express = require('express');
  const bodyParser = require('body-parser');
  const cors = require('cors');
  const mongoose = require('mongoose');

  // Lee la variable de entorno MONGODB_URI (defínela en tu .env o hosting)
  // Ejemplo: MONGODB_URI="mongodb+srv://user:password@<tu-cluster>.mongodb.net/mi_base?retryWrites=true&w=majority"
  const mongoUri = process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/mi_base_local';

  // Conexión con Mongoose
  mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true })
    .then(() => console.log('Conectado a MongoDB'))
    .catch(err => console.error('Error al conectar a MongoDB', err));

  // Definir un esquema y modelo de usuarios
  const userSchema = new mongoose.Schema({
    email: { type: String, required: true, unique: true },
    password: { type: String, required: true },
    name: { type: String, required: true }
  });

  const User = mongoose.model('User', userSchema);

  const app = express();
  app.use(bodyParser.json());
  app.use(cors());

  // Ruta para iniciar sesión
  app.post('/api/login', async (req, res) => {
    const { email, password } = req.body;

    try {
      // Buscar al usuario por email
      const user = await User.findOne({ email });
      if (!user) {
        return res.status(401).json({ error: 'Credenciales incorrectas.' });
      }

      // Verificar contraseña (o en proyectos reales, comparar hash)
      if (user.password !== password) {
        return res.status(401).json({ error: 'Credenciales incorrectas.' });
      }

      return res.json({ message: 'Inicio de sesión exitoso', name: user.name });
    } catch (error) {
      console.error('Error en /api/login:', error);
      return res.status(500).json({ error: 'Error interno del servidor' });
    }
  });

  // Ruta básica para registro
  app.post('/api/register', async (req, res) => {
    const { email, password, name } = req.body;

    if (!email || !password || !name) {
      return res.status(400).json({ error: 'Faltan campos requeridos' });
    }

    try {
      // Verificar si existe usuario
      const existingUser = await User.findOne({ email });
      if (existingUser) {
        return res.status(409).json({ error: 'El usuario ya existe' });
      }

      // Crear nuevo usuario
      const newUser = new User({ email, password, name });
      await newUser.save();

      return res.json({ message: 'Registro exitoso', userId: newUser._id });
    } catch (error) {
      console.error('Error en /api/register:', error);
      return res.status(500).json({ error: 'Error interno del servidor' });
    }
  });

  // Ejemplo de ruta privada
  // En producción, se verificaría un token o sesión para autorizar el acceso.
  app.get('/api/profile', (req, res) => {
    return res.json({ profile: 'Este es tu perfil privado (simulación)' });
  });

  // Puedes servir archivos estáticos si lo deseas:
  // app.use(express.static('ruta-del-build-frontend'));

  // Iniciar el servidor
  const PORT = process.env.PORT || 3001;
  app.listen(PORT, () => {
    console.log(`Servidor escuchando en http://localhost:${PORT}`);
  });