# Serena Nails · serenanailsuy.com

Sitio de Serena Nails (Flask) con programa de fidelización **Club Serena**.

## Correr en local

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
ADMIN_PASSWORD=algo-local FLASK_DEBUG=1 .venv/Scripts/python app.py
```

Abrí http://localhost:5000. El panel está en `/admin`. En local los datos se guardan en `serena.db` (SQLite).

## Qué se edita dónde

| Qué | Dónde |
|---|---|
| Precios, servicios, contacto, reglas del Club | `content.py` |
| Textos de la página | `templates/index.html` |
| Colores, tipografías, animaciones CSS | `static/css/main.css` |
| Video de portada | subir `static/video/hero.mp4` (se detecta solo) |
| Videos del espacio (formato reel) | subir `static/video/espacio-1.mp4`, `espacio-2.mp4`… (se detectan solos) |

Recomendación para videos: verticales, de 6 a 10 segundos, sin audio, de menos de 4 MB cada uno.

## Render: variables de entorno

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | **Obligatoria en producción.** URL de Postgres (Render Postgres o Neon). Sin esto, las tarjetas se guardan en un SQLite que Render borra en cada deploy. |
| `SECRET_KEY` | Cadena larga y aleatoria para firmar la sesión del panel. |
| `ADMIN_PASSWORD` | Contraseña del panel `/admin` de Sheila. |

Comando de inicio: `gunicorn app:app`

## Club Serena (reglas)

- Clienta nueva: la tarjeta arranca con **2 sellos de regalo**.
- Cada servicio suma 1 sello.
- **Sello 5**: ese servicio tiene 25% de descuento.
- **Sello 10**: ese servicio tiene 50% de descuento y la tarjeta vuelve a 0.

Flujo: Sheila crea la tarjeta en `/admin` y se la manda por WhatsApp con un botón. La clienta la guarda en la pantalla de inicio de su celular. En cada visita, Sheila escanea el QR (con el panel abierto en su celular) y toca "Sumar sello".
