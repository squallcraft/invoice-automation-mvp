#!/usr/bin/env python3
"""
Crear usuario admin. Uso:
  flask --app app.app shell
  >>> from scripts.create_admin import create_admin_user
  >>> create_admin_user("o.guzman@grupoenix.com", "123456789")

O desde la raíz del backend:
  python -c "
  import os, sys
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from app import create_app, db
  from app.models import User
  from app.routes.auth import _hash_password
  app = create_app()
  with app.app_context():
      u = User.query.filter_by(email='o.guzman@grupoenix.com').first()
      if u:
          u.password_hash = _hash_password('123456789')
          u.is_admin = True
          db.session.commit()
          print('Admin actualizado:', u.email)
      else:
          u = User(email='o.guzman@grupoenix.com', password_hash=_hash_password('123456789'), is_admin=True)
          db.session.add(u)
          db.session.commit()
          print('Admin creado:', u.email)
  "
"""
import os
import sys

# Allow running from backend/ (scripts/create_admin.py) or from project root
_this_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(_this_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.chdir(backend_dir)
os.environ.setdefault("FLASK_APP", "app.app")


def _hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256((password + "invoice_mvp_salt").encode()).hexdigest()


def create_admin_user(email: str, password: str):
    from app import create_app, db
    from app.models import User

    app = create_app()
    with app.app_context():
        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()
        pw_hash = _hash_password(password)
        if user:
            user.password_hash = pw_hash
            user.is_admin = True
            db.session.commit()
            print(f"Admin actualizado: {user.email}")
        else:
            user = User(
                email=email,
                password_hash=pw_hash,
                is_admin=True,
            )
            db.session.add(user)
            db.session.commit()
            print(f"Admin creado: {user.email}")
        return user


if __name__ == "__main__":
    email = os.environ.get("ADMIN_EMAIL", "o.guzman@grupoenix.com")
    password = os.environ.get("ADMIN_PASSWORD", "123456789")
    create_admin_user(email, password)
