import socket
import sqlite3
import threading

from datetime import datetime

from config import HOST, PORT, BUFFER_SIZE
from database import inicializar_db, guardar_mensaje


def inicializar_socket():
    """
    Crea y configura el socket TCP/IP del servidor.
    """

    # config socket tcp/ip
    servidor = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    # permite reutilizar el puerto al reiniciar el servidor
    # evita el error "Address already in use" por TIME_WAIT)
    servidor.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    # localhost+puerto
    servidor.bind((HOST, PORT))

    # socket escuchando
    servidor.listen()

    # evita que accept() quede bloqueado indefinidamente
    servidor.settimeout(1.0)

    return servidor


def atender_cliente(conexion, direccion):
    """
    Recibe múltiples mensajes de un cliente mientras
    la conexión permanezca abierta.

    Se ejecuta en un hilo propio por cada cliente.
    """

    ip_cliente = direccion[0]

    print(f"Cliente conectado desde {direccion}")

    with conexion:

        while True:

            try:

                # esperando datos del cliente
                datos = conexion.recv(BUFFER_SIZE)

                # sin datos, el cliente cerró la conexión
                if not datos:
                    print(f"Cliente {direccion} desconectado.")
                    break

                mensaje = datos.decode("utf-8").strip()

                if not mensaje:
                    continue

                # generar fecha/hora de recepción del mensaje
                timestamp = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                # guarda mensaje en sqlite
                guardar_mensaje(
                    mensaje,
                    timestamp,
                    ip_cliente
                )

                print(
                    f"[{timestamp}] "
                    f"{ip_cliente}: {mensaje}"
                )

                # respuesta solicitada
                respuesta = (
                    f"Mensaje recibido: {timestamp}"
                )

                conexion.sendall(
                    respuesta.encode("utf-8")
                )

            except sqlite3.Error as error:

                print(
                    "Error al acceder a la base de datos:",
                    error
                )

                try:
                    conexion.sendall(
                        "Error al guardar el mensaje".encode("utf-8")
                    )

                except OSError:
                    pass

                break

            except ConnectionResetError:

                print(
                    f"El cliente {direccion} "
                    "cerró inesperadamente la conexión."
                )

                break

            except OSError as error:

                print(
                    f"Error de comunicación con {direccion}:",
                    error
                )

                break


def aceptar_conexiones(servidor):
    """
    Mantiene al servidor esperando conexiones.

    Cada cliente aceptado se delega a un hilo separado,
    así el servidor puede atender a varios a la vez.
    """

    print("=" * 50)
    print("Servidor iniciado")
    print(f"Escuchando en {HOST}:{PORT}")
    print("Presioná Ctrl + C para detenerlo")
    print("=" * 50)

    while True:

        try:

            # accept() espera hasta que aparezca un cliente.
            conexion, direccion = servidor.accept()

            # cada cliente se atiende en su propio hilo.
            # daemon=True hace que los hilos terminen
            # automáticamente al cerrar el servidor.
            hilo = threading.Thread(
                target=atender_cliente,
                args=(conexion, direccion),
                daemon=True
            )

            hilo.start()

        except socket.timeout:

            # si no aparece un cliente en 1 segundo,
            # vuelve a escuchar conexiones
            continue


def main():

    servidor = None

    try:

        # inicia sqlite antes que servidor
        inicializar_db()

        # crea socket
        servidor = inicializar_socket()

        # acepta cliente
        aceptar_conexiones(servidor)

    except sqlite3.Error as error:

        print(
            "No se pudo acceder a la base de datos:"
        )

        print(error)

    except OSError as error:

        print(
            f"No se pudo iniciar el servidor "
            f"en el puerto {PORT}."
        )

        print(
            "Es posible que el puerto ya esté ocupado."
        )

        print(error)

    except KeyboardInterrupt:

        print("\nServidor detenido por el usuario.")

    finally:

        if servidor:
            servidor.close()

        print("Servidor finalizado.")


if __name__ == "__main__":
    main()