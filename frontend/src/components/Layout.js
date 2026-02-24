import React, { useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Layout.css';

const navItems = [
  { to: '/', label: 'Ventas', icon: '📋' },
  { to: '/config', label: 'Configuración', icon: '⚙' },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  return (
    <div className="slack-layout">
      <aside className="slack-sidebar">
        <div className="slack-sidebar-header">
          <span className="slack-workspace-name">Invoice Automation</span>
        </div>
        <nav className="slack-sidebar-nav">
          {navItems.map(({ to, end, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                'slack-nav-item' + (isActive ? ' slack-nav-item-active' : '')
              }
            >
              <span className="slack-nav-icon">{icon}</span>
              <span className="slack-nav-label">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="slack-sidebar-footer">
          <div
            className="slack-user-trigger"
            onClick={() => setUserMenuOpen((o) => !o)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setUserMenuOpen((o) => !o)}
          >
            <span className="slack-user-avatar">
              {(user?.email || '?').charAt(0).toUpperCase()}
            </span>
            <span className="slack-user-email">{user?.email}</span>
          </div>
          {userMenuOpen && (
            <div className="slack-user-menu">
              <div className="slack-user-menu-email">{user?.email}</div>
              <button type="button" className="slack-user-menu-logout" onClick={logout}>
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </aside>
      <main className="slack-main">
        <Outlet />
      </main>
    </div>
  );
}
