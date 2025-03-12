const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const dotenv = require('dotenv');

// Importar rutas
const authRoutes = require('./routes/auth');
const productRoutes = require('./routes/products');

dotenv.config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Conexión a MongoDB
mongoose.connect(process.env.MONGODB_URI)
    .then(() => console.log('Conectado a MongoDB'))
    .catch(err => console.error('Error de conexión a MongoDB:', err));

// Rutas
app.use('/api/auth', authRoutes);
app.use('/api/products', productRoutes);

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
    console.log(`Servidor corriendo en puerto ${PORT}`);
});