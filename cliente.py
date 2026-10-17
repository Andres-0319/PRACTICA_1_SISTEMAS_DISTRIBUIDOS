"""Cliente concurrente para el chat TCP multiusuario."""

import json
import logging
import queue
import socket
import threading
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

DEFAULT_PORT = 8080
MAX_MESSAGE_SIZE = 4096
RECV_SIZE = 2048
MAX_ALIAS_LENGTH = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)


class ProtocolError(ValueError):
    """Error al interpretar mensajes del protocolo."""


def encode_message(message: dict[str, Any]) -> bytes:
    """Codifica un objeto JSON terminado en salto de línea."""
    try:
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("No se pudo codificar el mensaje.") from exc

    if len(data) > MAX_MESSAGE_SIZE:
        raise ProtocolError("El mensaje supera el límite permitido.")
    return data


def receive_message(
    sock: socket.socket,
    buffer: bytearray,
) -> dict[str, Any] | None:
    """Lee un mensaje JSON completo aunque TCP fragmente los datos."""
    while True:
        newline_index = buffer.find(b"\n")
        if newline_index >= 0:
            raw = bytes(buffer[:newline_index])
            del buffer[:newline_index + 1]

            if len(raw) + 1 > MAX_MESSAGE_SIZE:
                raise ProtocolError("Mensaje demasiado grande.")

            try:
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProtocolError("Respuesta JSON inválida.") from exc

            if not isinstance(message, dict):
                raise ProtocolError("La respuesta no es un objeto JSON.")
            return message

        if len(buffer) >= MAX_MESSAGE_SIZE:
            raise ProtocolError("Mensaje demasiado grande o incompleto.")

        chunk = sock.recv(RECV_SIZE)
        if not chunk:
            if buffer:
                raise ProtocolError(
                    "El servidor cerró la conexión con datos incompletos."
                )
            return None
        buffer.extend(chunk)


class SocketClient:
    """Gestiona una conexión persistente con el servidor de chat."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._receiver_thread: threading.Thread | None = None
        self._alias: str | None = None

    def connect(self, alias: str) -> bool:
        """Conecta al servidor y espera la aceptación del alias."""
        alias = alias.strip()
        if not alias:
            raise ValueError("El alias no puede estar vacío.")
        if len(alias) > MAX_ALIAS_LENGTH:
            raise ValueError(
                f"El alias no puede superar {MAX_ALIAS_LENGTH} caracteres."
            )

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket = sock

        try:
            sock.connect((self._host, self._port))
            sock.settimeout(10.0)
            with self._send_lock:
                sock.sendall(encode_message({"tipo": "usuario", "alias": alias}))

            buffer = bytearray()
            response = receive_message(sock, buffer)
            if response is None:
                raise ConnectionError(
                    "El servidor cerró la conexión durante la identificación."
                )
            if response.get("tipo") == "error":
                print(f"[Error] {response.get('texto', 'Identificación rechazada.')}")
                self.close()
                return False
            if response.get("tipo") != "bienvenida":
                raise ProtocolError("El servidor respondió un mensaje inesperado.")

            self._alias = response.get("alias", alias)
            sock.settimeout(None)
            self._receiver_thread = threading.Thread(
                target=self._receive_loop,
                args=(buffer,),
                name="ChatReceiver",
                daemon=True,
            )
            self._receiver_thread.start()
            print(f"Conectado al chat como {self._alias} en {self._host}:{self._port}")
            return True

        except (OSError, ProtocolError, ConnectionError) as exc:
            LOGGER.error("No se pudo conectar al chat: %s", exc)
            self.close()
            raise

    def send_message(self, text: str) -> None:
        """Envía un mensaje normal al chat."""
        sock = self._socket
        if sock is None or self._stop_event.is_set():
            raise ConnectionError("No existe una conexión activa.")
        if not text.strip():
            return

        try:
            payload = encode_message({"tipo": "mensaje", "texto": text})
            with self._send_lock:
                sock.sendall(payload)
        except (OSError, ProtocolError) as exc:
            self._stop_event.set()
            raise ConnectionError(f"No se pudo enviar el mensaje: {exc}") from exc

    def _send_exit(self) -> None:
        """Solicita al servidor una desconexión normal mediante /salir."""
        sock = self._socket
        if sock is None:
            return
        try:
            payload = encode_message({"tipo": "salir"})
            with self._send_lock:
                sock.sendall(payload)
        except (OSError, ProtocolError):
            # Si la conexión ya se perdió, close() igualmente limpiará el socket.
            pass

    def _receive_loop(self, buffer: bytearray) -> None:
        try:
            while not self._stop_event.is_set():
                sock = self._socket
                if sock is None:
                    break
                message = receive_message(sock, buffer)
                if message is None:
                    if not self._stop_event.is_set():
                        self._messages.put({
                            "tipo": "sistema",
                            "texto": "El servidor cerró la conexión.",
                        })
                    break
                self._messages.put(message)
        except (OSError, ProtocolError) as exc:
            if not self._stop_event.is_set():
                LOGGER.warning("Se perdió la conexión: %s", exc)
                self._messages.put({
                    "tipo": "sistema",
                    "texto": "Se perdió la conexión con el servidor.",
                })
        finally:
            self._stop_event.set()
            self._messages.put(None)

    def _display_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                message = self._messages.get(timeout=0.2)
            except queue.Empty:
                continue
            if message is None:
                break

            message_type = message.get("tipo")
            if message_type == "mensaje":
                print(f"\n[{message.get('alias', 'Desconocido')}]: {message.get('texto', '')}")
            elif message_type == "sistema":
                print(f"\n[Sistema] {message.get('texto', '')}")
            elif message_type == "error":
                print(f"\n[Error] {message.get('texto', '')}")

    def close(self) -> None:
        """Cierra la conexión y detiene la recepción."""
        self._stop_event.set()
        sock = self._socket
        self._socket = None

        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

        receiver = self._receiver_thread
        if receiver is not None and receiver is not threading.current_thread():
            receiver.join(timeout=2.0)

    def run_console(self) -> None:
        """Ejecuta la consola, permitiendo enviar y recibir en paralelo."""
        display_thread = threading.Thread(
            target=self._display_loop,
            name="ChatDisplay",
            daemon=True,
        )
        display_thread.start()

        input_queue: queue.Queue[str | None] = queue.Queue()

        def read_input() -> None:
            session: PromptSession[str] = PromptSession()
            try:
                while not self._stop_event.is_set():
                    text = session.prompt("> ")
                    input_queue.put(text)
                    if text.strip().lower() == "/salir":
                        break
            except (EOFError, KeyboardInterrupt):
                input_queue.put("/salir")
            finally:
                input_queue.put(None)

        input_thread = threading.Thread(
            target=read_input,
            name="ChatInput",
            daemon=True,
        )

        print("Escribe /salir y pulsa Enter para desconectarte.")
        try:
            with patch_stdout():
                input_thread.start()
                while not self._stop_event.is_set():
                    try:
                        text = input_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if text is None:
                        break
                    if text.strip().lower() == "/salir":
                        self._send_exit()
                        break
                    try:
                        self.send_message(text)
                    except ConnectionError as exc:
                        print(f"\n[Error] {exc}")
                        break
        except (KeyboardInterrupt, EOFError):
            print("\nCerrando el cliente...")
        finally:
            self.close()
            print("Cliente desconectado.")


def main() -> None:
    """Solicita los datos del servidor e inicia el cliente."""
    try:
        host = input("IP del servidor (ej. 192.168.1.100): ").strip()
        if not host:
            print("Debes introducir una dirección IP o nombre de host.")
            return

        alias = input("Tu alias (máximo 20 caracteres): ").strip()
        if not alias or len(alias) > MAX_ALIAS_LENGTH:
            print("El alias debe tener entre 1 y 20 caracteres.")
            return

        client = SocketClient(host, DEFAULT_PORT)
        try:
            if client.connect(alias):
                client.run_console()
        except (OSError, ConnectionError, ProtocolError, ValueError) as exc:
            print(f"No se pudo iniciar el chat: {exc}")
        finally:
            client.close()
    except (KeyboardInterrupt, EOFError):
        print("\nEjecución cancelada por el usuario.")


if __name__ == "__main__":
    main()
