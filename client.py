import socket

from config import HOST, PORT, BUFFER_SIZE


def conectar_servidor():
    """
    Crea el socket del cliente y se conecta
    al servidor.
    """

    cliente = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    cliente.connect(
        (HOST, PORT)
    )

    return cliente


def enviar_mensajes(cliente):
    """
    Permite enviar múltiples mensajes hasta
    que el usuario escriba 'éxito'.
    """

    while True:

        mensaje = input(
            "\nEscribí un mensaje "
            "(o 'éxito' para salir): "
        ).strip()

        if mensaje.lower() == "éxito":

            print("Cerrando cliente...")

            break

        if not mensaje:

            print(
                "El mensaje no puede estar vacío."
            )

            continue

        cliente.sendall(
            mensaje.encode("utf-8")
        )

        respuesta = cliente.recv(
            BUFFER_SIZE
        )

        print(
            "Servidor:",
            respuesta.decode("utf-8")
        )


def main():

    try:

        cliente = conectar_servidor()

        print("=" * 50)
        print(
            f"Conectado al servidor "
            f"{HOST}:{PORT}"
        )
        print("=" * 50)

        with cliente:
            enviar_mensajes(cliente)

    except ConnectionRefusedError:

        print(
            "No se pudo conectar con el servidor."
        )

        print(
            "Verificá que servidor.py "
            "se encuentre ejecutándose."
        )

    except OSError as error:

        print(
            "Ocurrió un error de conexión:"
        )

        print(error)

    except KeyboardInterrupt:

        print("\nCliente cerrado.")


if __name__ == "__main__":
    main()