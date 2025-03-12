// frontend/src/components/Navbar.tsx
import React from 'react';
import { Link } from 'react-router-dom';

const Navbar = () => {
  return (
    <nav className="bg-blue-600 text-white p-4">
      <div className="container mx-auto flex justify-between items-center">
        <Link to="/" className="text-xl font-bold">TechTrove</Link>
        <div className="space-x-4">
          <Link to="/products">Productos</Link>
          <Link to="/cart">Carrito</Link>
          <Link to="/login">Iniciar Sesión</Link>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;