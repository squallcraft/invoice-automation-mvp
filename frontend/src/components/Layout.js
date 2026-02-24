import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Layout.css';

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="layout">
      <header className="layout-header">
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/semi">Subir Excel/CSV</NavLink>
          <NavLink to="/config">Configuración</NavLink>
        </nav>
        <div className="layout-user">
          <span>{user?.email}</span>
          <button type="button" onClick={logout}>Salir</button>
        </div>
      </header>
      <main className="layout-main">
        <Outlet />
      </main>
    </div>
  );
}
