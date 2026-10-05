"""Contenido editable del sitio: servicios, precios, contacto y reglas de fidelización.

Para cambiar un precio o agregar un servicio, editá este archivo y hacé deploy.
"""

BUSINESS = {
    "name": "Serena Nails",
    "owner": "Sheila Navcevich",
    "city": "Paysandú",
    "address": "Juncal 673",
    "address_full": "Juncal 673, Paysandú, Uruguay",
    "maps_url": "https://www.google.com/maps/search/?api=1&query=Juncal+673+Paysand%C3%BA+Uruguay",
    "maps_embed": "https://www.google.com/maps?q=Juncal+673,+Paysand%C3%BA,+Uruguay&output=embed",
    "phone": "+59897300766",
    "phone_display": "097 300 766",
    "whatsapp": "59897300766",
    "instagram": "https://www.instagram.com/serenanails.uy/",
    "instagram_handle": "@serenanails.uy",
    "email": "navcevichsh@gmail.com",
    "calendly": "https://calendly.com/serena-nails",
    "url": "https://serenanailsuy.com",
}

# Cada servicio: slug, nombre, descripción corta, precio (int en UYU o None = "Consultar"),
# lista "incluye", duración aproximada opcional y link de reserva.
SERVICES = {
    "manos": [
        {
            "slug": "kapping",
            "name": "Kapping gel",
            "tagline": "Refuerzo sobre la uña natural",
            "desc": "Una capa de gel sobre tu uña natural que la fortalece y le da firmeza, para que crezca sana y luzca impecable.",
            "price": 750,
            "includes": ["Preparación y cutículas", "Refuerzo en gel", "Color a elección"],
            "book": "https://calendly.com/serena-nails/kapping",
        },
        {
            "slug": "soft-gel",
            "name": "Soft gel",
            "tagline": "Extensiones livianas y naturales",
            "desc": "Extensión con tips flexibles de gel: el largo y la forma que soñás, livianas y con terminación natural.",
            "price": 900,
            "includes": ["Preparación y cutículas", "Tips soft gel a medida", "Forma y largo a elección"],
            "book": "https://calendly.com/serena-nails/soft-gel",
            "featured": True,
        },
        {
            "slug": "semipermanente",
            "name": "Semipermanente",
            "tagline": "Color, brillo y duración",
            "desc": "Esmaltado que se mantiene impecable por semanas, con brillo espejo y sin descascararse.",
            "price": 650,
            "includes": ["Preparación y cutículas", "Esmaltado semipermanente", "Brillo de larga duración"],
            "book": "https://calendly.com/serena-nails/semipermanente",
        },
        {
            "slug": "nail-art",
            "name": "Nail art",
            "tagline": "Diseños a tu medida",
            "desc": "Diseños delicados y personalizados para sumar a cualquier servicio. Traé tu idea o creamos una juntas.",
            "price": None,
            "includes": ["Diseño personalizado", "Se suma a cualquier servicio"],
            "book": "https://calendly.com/serena-nails",
        },
    ],
    "pies": [
        {
            "slug": "pedicuria-spa",
            "name": "Pedicuría spa",
            "tagline": "Un ritual completo para tus pies",
            "desc": "Limpieza profunda, remoción de durezas y callosidades, exfoliación y un masaje relajante para que salgas caminando en las nubes.",
            "price": 1200,
            "includes": ["Remoción de durezas y piel muerta", "Exfoliación", "Masaje de pies", "Cutículas y limado"],
            "book": "https://calendly.com/serena-nails",
            "featured": True,
        },
        {
            "slug": "semipermanente-pies",
            "name": "Semipermanente en pies",
            "tagline": "Color que dura",
            "desc": "Esmaltado semipermanente en los pies con brillo y duración, ideal para todo el año.",
            "price": None,
            "includes": ["Preparación", "Esmaltado semipermanente", "Masaje de pies"],
            "book": "https://calendly.com/serena-nails",
        },
        {
            "slug": "kapping-pies",
            "name": "Kapping en pies",
            "tagline": "Refuerzo y prolijidad",
            "desc": "Refuerzo en gel sobre la uña natural del pie, para uñas más firmes y parejas.",
            "price": None,
            "includes": ["Preparación", "Refuerzo en gel", "Masaje de pies"],
            "book": "https://calendly.com/serena-nails",
        },
    ],
    "extras": [
        {
            "slug": "remocion",
            "name": "Remoción",
            "tagline": "Retiro cuidadoso del material",
            "desc": "Retiramos el material sin dañar tu uña natural.",
            "price": None,
            "includes": [],
            "book": "https://calendly.com/serena-nails/remocion",
        },
    ],
}

# Servicios que se pueden registrar en la tarjeta de fidelización (panel admin).
LOYALTY_SERVICE_CHOICES = [s["name"] for group in ("manos", "pies") for s in SERVICES[group]] + ["Otro"]

LOYALTY = {
    "total": 10,          # sellos por tarjeta
    "welcome": 2,         # sellos de regalo para clientas nuevas
    "rewards": {5: 25, 10: 50},  # n° de sello -> % de descuento en ese servicio
}

GALLERY = [
    {"src": "img/trabajo-1.webp", "sm": "img/trabajo-1-sm.webp", "alt": "Uñas blancas con detalle de nail art"},
    {"src": "img/trabajo-2.webp", "sm": "img/trabajo-2-sm.webp", "alt": "Uñas nude con línea francesa fina"},
    {"src": "img/trabajo-3.webp", "sm": "img/trabajo-3-sm.webp", "alt": "Francesa en celeste con detalles"},
    {"src": "img/trabajo-4.webp", "sm": "img/trabajo-4-sm.webp", "alt": "Uñas cortas en rosa suave"},
    {"src": "img/trabajo-5.webp", "sm": "img/trabajo-5-sm.webp", "alt": "Francesa con brillo dorado"},
    {"src": "img/trabajo-6.webp", "sm": "img/trabajo-6-sm.webp", "alt": "Uñas rosadas con línea dorada"},
]

# Clips para el "reel" del espacio. Poné archivos .mp4 (verticales, 6-10 s, sin audio)
# en static/video/ y listalos acá; mientras esté vacío se muestra un slideshow de fotos.
SPACE_VIDEOS = []
HERO_VIDEO = None  # p.ej. "video/hero.mp4" (horizontal o vertical, en loop y sin audio)
