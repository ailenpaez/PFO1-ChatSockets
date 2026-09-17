"""
  1. Tests unitarios de database.py (con una DB temporal)
  2. Tests unitarios de client.py (con un socket simulado)
  3. Tests de integración de server.py (levantan el servidor real)

Para correr todo:
    pytest tests/test_chat.py -v

Para correr solo los tests rápidos (sin levantar el servidor):
    pytest tests/test_chat.py -v -m unitario

Para correr solo los tests de integración (con el servidor real):
    pytest tests/test_chat.py -v -m integracion
"""

import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

# permite importar server.py, client.py, database.py y config.py,
# que están un nivel arriba (en la raíz del proyecto)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import client
import config
import database


# *************************************************
# 1. TESTS UNITARIOS: database.py
# *************************************************

@pytest.fixture
def db_temporal(tmp_path, monkeypatch):
    """
    Redirige database.DATA_DIR y database.DB_PATH a una carpeta
    temporal creada por pytest, e inicializa la tabla 'mensajes'.
    Cada test recibe una base de datos limpia.
    """

    carpeta = tmp_path / "data"
    ruta_db = carpeta / "chat.db"

    monkeypatch.setattr(database, "DATA_DIR", carpeta)
    monkeypatch.setattr(database, "DB_PATH", ruta_db)

    database.inicializar_db()

    return ruta_db


@pytest.mark.unitario
def test_inicializar_db_crea_carpeta_y_tabla(db_temporal):
    """
    inicializar_db() debe crear la carpeta data/ y la tabla mensajes
    con las columnas exactas que pide la consigna.
    """

    assert db_temporal.exists()

    conexion = sqlite3.connect(db_temporal)
    columnas = [
        fila[1]
        for fila in conexion.execute("PRAGMA table_info(mensajes)")
    ]
    conexion.close()

    assert columnas == ["id", "contenido", "fecha_envio", "ip_cliente"]


@pytest.mark.unitario
def test_guardar_mensaje_persiste_los_4_campos(db_temporal):
    """
    guardar_mensaje() debe insertar una fila con contenido,
    fecha_envio e ip_cliente exactamente como se pasaron.
    """

    database.guardar_mensaje(
        "hola mundo",
        "2026-09-16 12:00:00",
        "127.0.0.1"
    )

    conexion = sqlite3.connect(db_temporal)
    fila = conexion.execute(
        "SELECT contenido, fecha_envio, ip_cliente FROM mensajes"
    ).fetchone()
    conexion.close()

    assert fila == ("hola mundo", "2026-09-16 12:00:00", "127.0.0.1")


@pytest.mark.unitario
def test_guardar_mensaje_autoincrementa_id(db_temporal):
    """
    Cada mensaje nuevo debe recibir un id distinto y creciente.
    """

    database.guardar_mensaje("primero", "2026-09-16 12:00:00", "127.0.0.1")
    database.guardar_mensaje("segundo", "2026-09-16 12:00:01", "127.0.0.1")

    conexion = sqlite3.connect(db_temporal)
    ids = [
        fila[0]
        for fila in conexion.execute("SELECT id FROM mensajes ORDER BY id")
    ]
    conexion.close()

    assert ids == [1, 2]


@pytest.mark.unitario
def test_lock_evita_perdida_de_mensajes_con_hilos_concurrentes(db_temporal):
    """
    Dispara 20 hilos que escriben en simultáneo. Si el db_lock no
    funcionara, sqlite podría rechazar escrituras concurrentes
    ('database is locked') y se perderían mensajes.
    """

    CANTIDAD_HILOS = 20
    hilos = []

    def escribir(n):
        database.guardar_mensaje(
            f"mensaje {n}",
            "2026-09-16 12:00:00",
            "127.0.0.1"
        )

    for n in range(CANTIDAD_HILOS):
        hilo = threading.Thread(target=escribir, args=(n,))
        hilos.append(hilo)
        hilo.start()

    for hilo in hilos:
        hilo.join()

    conexion = sqlite3.connect(db_temporal)
    total = conexion.execute("SELECT COUNT(*) FROM mensajes").fetchone()[0]
    conexion.close()

    assert total == CANTIDAD_HILOS


# *************************************************
# 2. TESTS UNITARIOS DE client.py
# *************************************************

class FakeSocket:
    """
    Reemplaza a un socket real: guarda lo que se le envía
    y devuelve respuestas pre-armadas en orden.
    """

    def __init__(self, respuestas):
        self.enviados = []
        self._respuestas = list(respuestas)

    def sendall(self, datos):
        self.enviados.append(datos.decode("utf-8"))

    def recv(self, buffer_size):
        return self._respuestas.pop(0).encode("utf-8")


@pytest.mark.unitario
def test_enviar_mensajes_envia_texto_no_vacio(monkeypatch):
    """
    Un mensaje con contenido debe enviarse por el socket tal cual
    lo escribió el usuario.
    """

    entradas = iter(["hola servidor", "éxito"])
    monkeypatch.setattr("builtins.input", lambda _: next(entradas))

    fake = FakeSocket(respuestas=["Mensaje recibido: 2026-09-16 12:00:00"])

    client.enviar_mensajes(fake)

    assert fake.enviados == ["hola servidor"]


@pytest.mark.unitario
def test_enviar_mensajes_no_envia_mensaje_vacio(monkeypatch):
    """
    Un mensaje vacío no debe llegar a sendall(); el loop debe
    pedir otro mensaje en su lugar.
    """

    entradas = iter(["", "  ", "recién ahora sí", "éxito"])
    monkeypatch.setattr("builtins.input", lambda _: next(entradas))

    fake = FakeSocket(respuestas=["Mensaje recibido: 2026-09-16 12:00:00"])

    client.enviar_mensajes(fake)

    assert fake.enviados == ["recién ahora sí"]


@pytest.mark.unitario
@pytest.mark.parametrize(
    "palabra_salida", ["éxito", "Éxito", "EXITO", "exito"]
)
def test_enviar_mensajes_corta_con_exito_en_cualquier_variante(
    monkeypatch, palabra_salida
):
    """
    El loop debe terminar al escribir 'éxito', sin importar
    mayúsculas o si falta la tilde (consigna: enviar mensajes
    "hasta que el usuario escriba éxito").
    """

    entradas = iter([palabra_salida])
    monkeypatch.setattr("builtins.input", lambda _: next(entradas))

    fake = FakeSocket(respuestas=[])

    # si el loop no cortara, este test colgaría (StopIteration lo evita)
    client.enviar_mensajes(fake)

    assert fake.enviados == []


# *************************************************
# 3. TESTS DE INTEGRACIÓN DE server.py (proceso real + sockets reales)
# *************************************************

def _esperar_puerto(host, port, timeout=5):
    """
    Reintenta conectar hasta que el servidor esté escuchando,
    en vez de usar un time.sleep() fijo (más rápido y más confiable).
    """

    limite = time.time() + timeout

    while time.time() < limite:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)

    return False


@pytest.fixture
def servidor():
    """
    Levanta 'python3 server.py' como proceso real antes del test,
    con una carpeta data/ limpia, y lo apaga al terminar.
    """

    data_dir = PROJECT_ROOT / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

    proceso = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if not _esperar_puerto(config.HOST, config.PORT, timeout=5):
        proceso.terminate()
        pytest.fail("El servidor no llegó a escuchar en el puerto esperado.")

    yield proceso

    proceso.terminate()
    try:
        proceso.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proceso.kill()

    if data_dir.exists():
        shutil.rmtree(data_dir)


def _conectar():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((config.HOST, config.PORT))
    return s


@pytest.mark.integracion
def test_respuesta_tiene_el_formato_pedido_por_la_consigna(servidor):
    """
    La consigna exige la respuesta exacta:
    "Mensaje recibido: <timestamp>"
    """

    s = _conectar()
    s.sendall("hola servidor".encode("utf-8"))
    respuesta = s.recv(config.BUFFER_SIZE).decode("utf-8")
    s.close()

    assert respuesta.startswith("Mensaje recibido: ")

    # el timestamp debe tener formato YYYY-MM-DD HH:MM:SS
    timestamp = respuesta.removeprefix("Mensaje recibido: ")
    assert len(timestamp) == 19
    assert timestamp[4] == "-" and timestamp[13] == ":"


@pytest.mark.integracion
def test_mensaje_se_guarda_en_la_base_de_datos(servidor):
    """
    Después de enviar un mensaje, debe existir una fila en
    data/chat.db con el contenido y la IP correctos.
    """

    s = _conectar()
    s.sendall("mensaje de prueba".encode("utf-8"))
    s.recv(config.BUFFER_SIZE)
    s.close()

    time.sleep(0.2)  # margen para que el server termine el INSERT

    conexion = sqlite3.connect(config.DB_PATH)
    fila = conexion.execute(
        "SELECT contenido, ip_cliente FROM mensajes "
        "WHERE contenido = ?",
        ("mensaje de prueba",)
    ).fetchone()
    conexion.close()

    assert fila == ("mensaje de prueba", "127.0.0.1")


@pytest.mark.integracion
def test_un_mismo_cliente_puede_enviar_varios_mensajes(servidor):
    """
    La consigna pide poder enviar múltiples mensajes en la misma
    conexión, no una conexión nueva por mensaje.
    """

    s = _conectar()

    respuestas = []
    for texto in ["primero", "segundo", "tercero"]:
        s.sendall(texto.encode("utf-8"))
        respuestas.append(s.recv(config.BUFFER_SIZE).decode("utf-8"))
    s.close()

    assert len(respuestas) == 3
    assert all(r.startswith("Mensaje recibido: ") for r in respuestas)


@pytest.mark.integracion
def test_dos_clientes_conectados_a_la_vez_no_se_bloquean(servidor):
    """
    Con threading.Thread por cliente, un segundo cliente no debería
    esperar a que el primero termine para recibir su respuesta.
    Sin el hilo, este test falla (el cliente 2 tarda ~3s en responder,
    el tiempo que el cliente 1 mantiene la conexión abierta); con el
    hilo, responde casi al instante.
    """

    resultados = {}

    def cliente_1_mantiene_conexion_abierta():
        s = _conectar()
        s.sendall(b"soy el cliente 1")
        resultados[1] = s.recv(config.BUFFER_SIZE).decode("utf-8")
        time.sleep(3)  # simula un usuario que tarda en escribir
        s.close()

    def cliente_2_deberia_responder_rapido():
        s = _conectar()
        s.sendall(b"soy el cliente 2")
        resultados[2] = s.recv(config.BUFFER_SIZE).decode("utf-8")
        s.close()

    hilo_1 = threading.Thread(target=cliente_1_mantiene_conexion_abierta)
    hilo_1.start()
    time.sleep(0.3)  # asegura que el cliente 1 conecte primero

    inicio = time.time()
    cliente_2_deberia_responder_rapido()
    duracion = time.time() - inicio

    hilo_1.join(timeout=5)

    assert 2 in resultados, "El cliente 2 nunca recibió respuesta (¿está bloqueado?)"
    assert duracion < 1.5, (
        f"El cliente 2 tardó {duracion:.1f}s: el servidor podría estar "
        "atendiendo un cliente a la vez en lugar de usar hilos."
    )


@pytest.mark.integracion
def test_puerto_ocupado_no_rompe_con_traceback(servidor):
    """
    Consigna: manejar el error de puerto ocupado. Se levanta un
    segundo servidor mientras el primero (fixture) sigue corriendo,
    y debe fallar con un mensaje prolijo, no con un traceback.
    """

    segundo = subprocess.run(
        [sys.executable, "server.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert "ocupado" in segundo.stdout.lower()
    assert "Traceback" not in segundo.stdout