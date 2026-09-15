import sqlite3

from config import DATA_DIR, DB_PATH

def inicializar_db():
    """
    Crea la carpeta data y la tabla mensajes si todavía
    no existen.
    """

    # crear carpeta data si no existe
    DATA_DIR.mkdir(exist_ok=True)

    conexion = sqlite3.connect(DB_PATH)

    try:
        cursor = conexion.cursor()

# datos de la tabla:
# id
# contenido
# fecha_envio
# ip_cliente

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mensajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contenido TEXT NOT NULL,
                fecha_envio TEXT NOT NULL,
                ip_cliente TEXT NOT NULL
            )
        """)

        conexion.commit()

    finally:
        conexion.close()


def guardar_mensaje(contenido, fecha_envio, ip_cliente):
    """
    Guarda un mensaje recibido por el servidor
    en la base de datos SQLite.
    """

    conexion = sqlite3.connect(DB_PATH)

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            INSERT INTO mensajes (
                contenido,
                fecha_envio,
                ip_cliente
            )
            VALUES (?, ?, ?)
        """, (
            contenido,
            fecha_envio,
            ip_cliente
        ))

        conexion.commit()

    finally:
        conexion.close()


