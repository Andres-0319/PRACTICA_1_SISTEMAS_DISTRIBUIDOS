# Importamos las librerías necesarias para el funcionamiento del servidor.
import json          # Permite convertir diccionarios a mensajes JSON.
import logging       # Permite mostrar información y errores del servidor.
import socket        # Permite crear la comunicación mediante TCP.
import threading     # Permite atender varios clientes al mismo tiempo.
from abc import ABC, abstractmethod  # Permite crear clases abstractas.
from dataclasses import dataclass, field  # Facilita la creación de clases de datos.
from typing import Any  # Permite indicar que una variable acepta distintos tipos.


# Configuración básica del servidor.
HOST = "0.0.0.0"  # Acepta conexiones desde cualquier interfaz de red del equipo.
PORT = 8080       # Puerto por el que se conectarán los clientes.
MAX_MESSAGE_SIZE = 4096  # Tamaño máximo permitido para un mensaje.
RECV_SIZE = 2048         # Cantidad de bytes recibidos en cada lectura.
MAX_ALIAS_LENGTH = 20    # Longitud máxima permitida para el alias.


# Configuramos los registros para mostrar información durante la ejecución.
logging.basicConfig(
    level=logging.INFO,  # Muestra mensajes informativos y errores.
    format="%(asctime)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)


# Excepción personalizada para los errores del protocolo de comunicación.
class ProtocolError(ValueError):
    """Error al recibir un mensaje que no cumple el protocolo."""


# PARTE 1: CODIFICACIÓN DE MENSAJES
def encode_message(message: dict[str, Any]) -> bytes:
    """Convierte un diccionario a JSON UTF-8 terminado en salto de línea."""

    try:
        # Convertimos el diccionario a JSON y agregamos un salto de línea
        # para indicar dónde termina cada mensaje enviado por TCP.
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")

    except (TypeError, ValueError) as exc:
        # Si el mensaje no se puede convertir a JSON, generamos un error.
        raise ProtocolError("No se pudo serializar el mensaje.") from exc

    # Comprobamos que el mensaje no supere el tamaño máximo permitido.
    if len(data) > MAX_MESSAGE_SIZE:
        raise ProtocolError("El mensaje supera el tamaño permitido.")

    # Devolvemos el mensaje convertido a bytes para enviarlo por el socket.
    return data


# PARTE 2: RECEPCIÓN DE MENSAJES
def receive_message(
    client_socket: socket.socket,
    buffer: bytearray,
) -> dict[str, Any] | None:
    """Lee un mensaje JSON completo, aunque TCP fragmente los datos."""

    while True:
        # Buscamos el salto de línea que marca el final del mensaje.
        newline_index = buffer.find(b"\n")

        if newline_index >= 0:
            # Extraemos el mensaje completo hasta el salto de línea.
            raw_message = bytes(buffer[:newline_index])

            # Eliminamos del buffer el mensaje procesado y su delimitador.
            del buffer[:newline_index + 1]

            # Verificamos el tamaño del mensaje recibido.
            if len(raw_message) + 1 > MAX_MESSAGE_SIZE:
                raise ProtocolError("El mensaje supera el tamaño permitido.")

            try:
                # Convertimos los bytes recibidos a texto UTF-8
                # y después interpretamos el contenido como JSON.
                message = json.loads(raw_message.decode("utf-8"))

            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                # Si el texto o el JSON son inválidos, informamos del error.
                raise ProtocolError("Mensaje JSON inválido.") from exc

            # El protocolo exige que cada mensaje sea un objeto JSON,
            # que normalmente se representa mediante un diccionario.
            if not isinstance(message, dict):
                raise ProtocolError("El mensaje debe ser un objeto JSON.")

            # Devolvemos el mensaje completo al código que lo solicitó.
            return message

        # Si no encontramos el delimitador, comprobamos el tamaño acumulado.
        if len(buffer) >= MAX_MESSAGE_SIZE:
            raise ProtocolError("Mensaje demasiado grande o sin delimitador.")

        # Recibimos una parte de los datos enviados por el cliente.
        chunk = client_socket.recv(RECV_SIZE)

        # Si no llegan datos, significa que la conexión se cerró.
        if not chunk:
            # Si quedaron bytes sin completar un mensaje, hay un error.
            if buffer:
                raise ProtocolError(
                    "Conexión cerrada con un mensaje incompleto."
                )

            # None indica que el cliente cerró la conexión normalmente.
            return None

        # Agregamos los bytes recibidos al buffer.
        # Esto permite reconstruir mensajes que llegan fragmentados por TCP.
        buffer.extend(chunk)


# PARTE 3: ENVÍO DE MENSAJES
def send_message(
    client_socket: socket.socket,
    message: dict[str, Any],
    send_lock: threading.Lock | None = None,
) -> None:
    """Envía un mensaje completo; el bloqueo evita escrituras simultáneas."""

    # Convertimos el diccionario a bytes antes de transmitirlo.
    payload = encode_message(message)

    # Si no existe un bloqueo, enviamos directamente el mensaje.
    if send_lock is None:
        client_socket.sendall(payload)

    else:
        # El bloqueo evita que dos hilos escriban simultáneamente
        # sobre el mismo socket y mezclen sus mensajes.
        with send_lock:
            client_socket.sendall(payload)


# PARTE 4: INFORMACIÓN DE CADA CLIENTE
@dataclass(eq=False)
class ClientSession:
    """Datos de una sesión de usuario conectada."""

    client_socket: socket.socket  # Socket que representa la conexión.
    address: tuple[str, int]      # Dirección IP y puerto del cliente.
    alias: str                    # Nombre del usuario en el chat.

    # Cada cliente tiene su propio bloqueo para controlar los envíos.
    send_lock: threading.Lock = field(default_factory=threading.Lock)


# PARTE 5: ADMINISTRACIÓN DE LA SALA DE CHAT
class ChatRoom:
    """Mantiene el registro de clientes y distribuye mensajes."""

    def __init__(self) -> None:
        # Diccionario que relaciona cada socket con su sesión de usuario.
        self._clients: dict[socket.socket, ClientSession] = {}

        # Bloqueo para proteger la lista de clientes cuando varios hilos
        # intentan modificarla o consultarla al mismo tiempo.
        self._lock = threading.RLock()

    def register(self, session: ClientSession) -> bool:
        """Registra un cliente si su alias es válido y está disponible."""

        # Eliminamos los espacios al principio y al final del alias.
        alias = session.alias.strip()

        # Rechazamos los alias vacíos o demasiado largos.
        if not alias or len(alias) > MAX_ALIAS_LENGTH:
            return False

        # Protegemos el registro mientras comprobamos y añadimos al cliente.
        with self._lock:

            # Comprobamos que no exista otro usuario con el mismo alias.
            # casefold permite comparar nombres sin distinguir mayúsculas
            # y minúsculas de manera más robusta.
            if any(
                current.alias.casefold() == alias.casefold()
                for current in self._clients.values()
            ):
                return False

            # Guardamos la sesión del nuevo cliente.
            self._clients[session.client_socket] = session
            return True

    def remove(self, client_socket: socket.socket) -> ClientSession | None:
        """Elimina un cliente y devuelve su sesión si estaba registrado."""

        # Eliminamos la sesión de forma segura.
        with self._lock:
            return self._clients.pop(client_socket, None)

    def contains(self, client_socket: socket.socket) -> bool:
        """Comprueba si un socket pertenece a un cliente registrado."""

        with self._lock:
            return client_socket in self._clients

    def broadcast(self, message: dict[str, Any]) -> None:
        """Envía el mensaje a todos los clientes registrados, incluido el emisor."""

        # Creamos una copia de las sesiones para recorrerlas sin mantener
        # el bloqueo durante todas las operaciones de envío.
        with self._lock:
            recipients = list(self._clients.values())

        # Aquí guardamos los clientes a los que no se pudo enviar el mensaje.
        failed: list[ClientSession] = []

        # Recorremos los destinatarios para difundir el mensaje.
        for recipient in recipients:

            # Verificamos que el cliente siga registrado antes de enviar.
            with self._lock:
                if (
                    self._clients.get(recipient.client_socket)
                    is not recipient
                ):
                    continue

            try:
                # Enviamos el mensaje utilizando el bloqueo de ese cliente.
                send_message(
                    recipient.client_socket,
                    message,
                    recipient.send_lock,
                )

            except (OSError, ProtocolError) as exc:
                # Registramos los errores de envío para revisar qué ocurrió.
                LOGGER.warning(
                    "Error enviando a %s (%s): %s",
                    recipient.alias,
                    recipient.address,
                    exc,
                )

                # Marcamos el cliente para retirarlo después del recorrido.
                failed.append(recipient)

        # Retiramos a los clientes que presentaron errores de envío.
        for recipient in failed:
            removed = self.remove(recipient.client_socket)

            # Cerramos la conexión si el cliente seguía registrado.
            if removed is not None:
                try:
                    recipient.client_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

                try:
                    recipient.client_socket.close()
                except OSError:
                    pass

                LOGGER.info(
                    "Cliente retirado por fallo de envío: %s (%s)",
                    recipient.alias,
                    recipient.address,
                )

    def close_all(self) -> list[ClientSession]:
        """Retira todos los clientes y devuelve sus sesiones."""

        # Guardamos las sesiones actuales y vaciamos el registro.
        with self._lock:
            sessions = list(self._clients.values())
            self._clients.clear()
            return sessions


# PARTE 6: CLASE ABSTRACTA PARA PROCESAR MENSAJES
class MessageHandler(ABC):
    """Abstracción para procesar mensajes de chat."""

    @abstractmethod
    def handle(self, session: ClientSession, message: dict[str, Any]) -> None:
        """Procesa un mensaje recibido de una sesión identificada."""

        # Las clases que hereden de esta clase deben implementar handle().
        raise NotImplementedError


# PARTE 7: VALIDACIÓN Y DIFUSIÓN DE MENSAJES DEL CHAT
class ChatMessageHandler(MessageHandler):
    """Valida los mensajes de chat y los difunde."""

    def __init__(self, room: ChatRoom) -> None:
        # Guardamos la sala donde están conectados los usuarios.
        self._room = room

    def handle(self, session: ClientSession, message: dict[str, Any]) -> None:

        # Ignoramos mensajes de clientes que ya no estén registrados.
        if not self._room.contains(session.client_socket):
            return

        # Solo permitimos mensajes cuyo tipo sea "mensaje".
        if message.get("tipo") != "mensaje":
            send_message(
                session.client_socket,
                {"tipo": "error", "texto": "Tipo de mensaje no permitido."},
                session.send_lock,
            )
            return

        # Obtenemos el texto que envió el usuario.
        text = message.get("texto")

        # Verificamos que el texto sea una cadena y no esté vacío.
        if not isinstance(text, str) or not text.strip():
            send_message(
                session.client_socket,
                {"tipo": "error", "texto": "El mensaje no puede estar vacío."},
                session.send_lock,
            )
            return

        # Comprobamos que el contenido no sea demasiado largo.
        # Se mide en bytes UTF-8 porque algunos caracteres ocupan varios bytes.
        if len(text.encode("utf-8")) > MAX_MESSAGE_SIZE - 256:
            send_message(
                session.client_socket,
                {"tipo": "error", "texto": "El mensaje es demasiado largo."},
                session.send_lock,
            )
            return

        # Distribuimos el mensaje a todos los clientes conectados.
        # El alias se obtiene de la sesión registrada en el servidor.
        self._room.broadcast({
            "tipo": "mensaje",
            "alias": session.alias,
            "texto": text,
        })


# PARTE 8: ADMINISTRACIÓN DE LA CONEXIÓN DE UN CLIENTE
class ClientHandler:
    """Administra una conexión individual desde la identificación hasta la salida."""

    def __init__(
        self,
        client_socket: socket.socket,
        address: tuple[str, int],
        message_handler: MessageHandler,
        room: ChatRoom,
    ) -> None:
        # Guardamos los datos necesarios para atender a este cliente.
        self._client_socket = client_socket
        self._address = address
        self._message_handler = message_handler
        self._room = room

        # Bloqueo para evitar envíos simultáneos desde este manejador.
        self._send_lock = threading.Lock()

    def _send_error(self, text: str) -> None:
        """Envía un mensaje de error al cliente sin propagar fallos de envío."""

        try:
            send_message(
                self._client_socket,
                {"tipo": "error", "texto": text},
                self._send_lock,
            )
        except (OSError, ProtocolError):
            # Si la conexión ya no funciona, ignoramos el error de envío.
            pass

    def process(self) -> None:
        """Controla el ciclo completo de atención de un cliente."""

        # Buffer donde se acumulan los datos recibidos por TCP.
        buffer = bytearray()

        # Al inicio, el cliente todavía no tiene una sesión registrada.
        session: ClientSession | None = None

        try:
            # Cerramos conexiones que permanezcan 60 segundos sin actividad
            # durante una operación de recepción.
            self._client_socket.settimeout(60.0)

            # Registramos la llegada de una nueva conexión.
            LOGGER.info(
                "Conexión entrante desde %s:%s",
                self._address[0],
                self._address[1],
            )

            # Esperamos el primer mensaje del cliente.
            first_message = receive_message(self._client_socket, buffer)

            # Si la conexión se cerró, terminamos el procesamiento.
            if first_message is None:
                return

            # El primer mensaje debe identificar al usuario.
            if first_message.get("tipo") != "usuario":
                self._send_error(
                    "Debes identificarte antes de enviar mensajes."
                )
                return

            # Extraemos el alias enviado por el cliente.
            alias = first_message.get("alias")

            # Comprobamos que el alias sea una cadena no vacía.
            if not isinstance(alias, str) or not alias.strip():
                self._send_error("El alias no puede estar vacío.")
                return

            # Quitamos espacios innecesarios.
            alias = alias.strip()

            # Validamos la longitud del alias.
            if len(alias) > MAX_ALIAS_LENGTH:
                self._send_error(
                    f"El alias no puede superar {MAX_ALIAS_LENGTH} caracteres."
                )
                return

            # Creamos la sesión del cliente con su socket, dirección y alias.
            session = ClientSession(
                client_socket=self._client_socket,
                address=self._address,
                alias=alias,
                send_lock=self._send_lock,
            )

            # Intentamos registrar al usuario en la sala.
            # Si el alias ya está ocupado, rechazamos la conexión al chat.
            if not self._room.register(session):
                self._send_error("El alias ya está en uso.")
                return

            # Confirmamos al usuario que se ha identificado correctamente.
            send_message(
                self._client_socket,
                {"tipo": "bienvenida", "alias": session.alias},
                self._send_lock,
            )

            # Registramos la conexión en los logs del servidor.
            LOGGER.info(
                "Usuario conectado: %s desde %s:%s",
                session.alias,
                self._address[0],
                self._address[1],
            )

            # Avisamos a todos los usuarios de que alguien se ha conectado.
            self._room.broadcast({
                "tipo": "sistema",
                "texto": f"{session.alias} se ha unido al chat.",
            })

            # Bucle principal: atiende mensajes mientras el usuario
            # permanezca registrado en la sala.
            while self._room.contains(self._client_socket):

                # Esperamos el siguiente mensaje enviado por el cliente.
                message = receive_message(self._client_socket, buffer)

                # Si la conexión se cerró, salimos del bucle.
                if message is None:
                    break

                # Consultamos el tipo de mensaje recibido.
                message_type = message.get("tipo")

                # Si el cliente solicita salir, terminamos su atención.
                if message_type == "salir":
                    break

                # No permitimos que un cliente vuelva a identificarse
                # dentro de una conexión que ya tiene un alias.
                if message_type == "usuario":
                    self._send_error(
                        "Ya estás identificado en esta conexión."
                    )
                    continue

                # Delegamos la validación y difusión del mensaje.
                self._message_handler.handle(session, message)

        # Gestionamos el tiempo de espera agotado.
        except socket.timeout:
            LOGGER.info("Tiempo de espera agotado para %s", self._address)

        # Gestionamos errores en el formato del protocolo.
        except ProtocolError as exc:
            LOGGER.warning(
                "Error de protocolo desde %s: %s",
                self._address,
                exc,
            )
            self._send_error(str(exc))

        # Gestionamos desconexiones y errores de comunicación.
        except (ConnectionError, OSError) as exc:
            LOGGER.info("Conexión perdida con %s: %s", self._address, exc)

        finally:
            # Se ejecuta al terminar el procesamiento, incluso si hubo errores.

            # Intentamos retirar al cliente del registro.
            removed = self._room.remove(self._client_socket)

            # Cerramos la comunicación de entrada y salida del socket.
            try:
                self._client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            # Liberamos el socket para no dejar conexiones abiertas.
            try:
                self._client_socket.close()
            except OSError:
                pass

            # Solo anunciamos la salida si el cliente estaba registrado.
            if removed is not None:
                LOGGER.info(
                    "Usuario desconectado: %s desde %s:%s",
                    removed.alias,
                    self._address[0],
                    self._address[1],
                )

                # Avisamos al resto de usuarios que alguien salió del chat.
                self._room.broadcast({
                    "tipo": "sistema",
                    "texto": f"{removed.alias} ha salido del chat.",
                })


# PARTE 9: SERVIDOR TCP MULTIHILOS
class ThreadedSocketServer:
    """Escucha conexiones TCP y crea un hilo por cliente."""

    def __init__(
        self,
        host: str = HOST,
        port: int = PORT,
        message_handler: MessageHandler | None = None,
    ) -> None:
        # Guardamos la dirección y el puerto del servidor.
        self._host = host
        self._port = port

        # Creamos la sala compartida por todos los clientes.
        self._room = ChatRoom()

        # Usamos el manejador proporcionado o creamos el predeterminado.
        self._message_handler = (
            message_handler if message_handler is not None
            else ChatMessageHandler(self._room)
        )

        # Aquí guardaremos el socket principal del servidor.
        self._server_socket: socket.socket | None = None

        # Evento compartido que permite indicar que el servidor debe detenerse.
        self._stop_event = threading.Event()

        # Conjunto con los hilos que atienden a los clientes.
        self._threads: set[threading.Thread] = set()

        # Bloqueo para proteger el conjunto de hilos.
        self._threads_lock = threading.Lock()

    def start(self) -> None:
        """Inicia el servidor y comienza a aceptar conexiones."""

        # Creamos un socket IPv4 que utiliza el protocolo TCP.
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket = server_socket

        # Permite reutilizar la dirección local cuando corresponda.
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Asociamos el socket a la dirección IP y al puerto configurados.
        server_socket.bind((self._host, self._port))

        # Ponemos el socket en modo escucha para aceptar clientes.
        server_socket.listen()

        # Evita que accept() bloquee indefinidamente.
        server_socket.settimeout(1.0)

        LOGGER.info(
            "Servidor escuchando en %s:%s",
            self._host,
            self._port,
        )

        try:
            # Bucle principal del servidor: continúa hasta recibir una orden
            # de detenerse.
            while not self._stop_event.is_set():

                try:
                    # Esperamos una conexión entrante.
                    client_socket, address = server_socket.accept()

                except socket.timeout:
                    # Si no llega ningún cliente durante un segundo,
                    # volvemos a comprobar si el servidor debe detenerse.
                    continue

                except OSError:
                    # Si el socket se cerró porque se detuvo el servidor,
                    # salimos del bucle; de lo contrario, propagamos el error.
                    if self._stop_event.is_set():
                        break
                    raise

                # Creamos un manejador independiente para el nuevo cliente.
                handler = ClientHandler(
                    client_socket,
                    address,
                    self._message_handler,
                    self._room,
                )

                # Función que ejecutará el hilo de este cliente.
                def ejecutar_manejador(
                    manejador: ClientHandler = handler,
                ) -> None:
                    try:
                        # Procesamos la conexión sin bloquear al servidor
                        # principal ni la aceptación de otros clientes.
                        manejador.process()

                    finally:
                        # Al finalizar, eliminamos el hilo del registro.
                        with self._threads_lock:
                            self._threads.discard(
                                threading.current_thread()
                            )

                # Creamos un hilo nuevo para atender a este cliente.
                thread = threading.Thread(
                    target=ejecutar_manejador,
                    name=f"Cliente-{address[0]}:{address[1]}",
                    daemon=True,
                )

                # Guardamos el hilo antes de iniciarlo.
                with self._threads_lock:
                    self._threads.add(thread)

                # Iniciamos el hilo. A partir de aquí puede ejecutarse
                # de manera concurrente con los demás hilos de clientes.
                thread.start()

        # Permitimos detener el servidor con Ctrl+C.
        except KeyboardInterrupt:
            LOGGER.info("Interrupción recibida. Cerrando el servidor.")

        finally:
            # Nos aseguramos de liberar los recursos al finalizar.
            self.stop()

    def stop(self) -> None:
        """Detiene el servidor y cierra todas las conexiones activas."""

        # Evitamos ejecutar varias veces el proceso de cierre.
        if self._stop_event.is_set():
            return

        # Avisamos a los bucles del servidor que deben detenerse.
        self._stop_event.set()

        # Cerramos el socket principal para dejar de aceptar conexiones.
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass

        # Retiramos todas las sesiones registradas.
        sessions = self._room.close_all()

        # Cerramos las conexiones de todos los clientes activos.
        for session in sessions:
            try:
                session.client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                session.client_socket.close()
            except OSError:
                pass

        # Obtenemos el hilo que está ejecutando el cierre.
        current_thread = threading.current_thread()

        # Copiamos la lista de hilos para esperar su finalización.
        with self._threads_lock:
            threads = list(self._threads)

        # Esperamos hasta dos segundos por cada hilo, excepto el actual.
        for thread in threads:
            if thread is not current_thread:
                thread.join(timeout=2.0)

        LOGGER.info("Servidor detenido correctamente.")


# PARTE 10: PUNTO DE ENTRADA DEL PROGRAMA
if __name__ == "__main__":

    # Si ejecutamos directamente este archivo, iniciamos el servidor.
    ThreadedSocketServer().start()
