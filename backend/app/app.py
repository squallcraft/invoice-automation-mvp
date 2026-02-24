"""
Punto de entrada: crear app y ejecutar (desarrollo).
Producción: gunicorn -w 4 -b 0.0.0.0:5000 "app.app:create_app()"
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_ENV") == "development")
