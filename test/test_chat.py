"""Pruebas automatizadas del chat multiusuario."""

import json
import socket
import unittest

from server import (
    MAX_MESSAGE_SIZE,
    ChatMessageHandler,
    ChatRoom,
    ClientSession,
    ProtocolError,
    receive_message,
)


class ChatRoomTests(unittest.TestCase):
    def setUp(self) -> None:
        self.room = ChatRoom()
        self.sockets: list[socket.socket] = []
        self.peers: list[socket.socket] = []

    def create_session(self, alias: str) -> ClientSession:
        server_side, client_side = socket.socketpair()
        self.sockets.append(server_side)
        self.peers.append(client_side)

        return ClientSession(
            client_socket=server_side,
            address=("127.0.0.1", 0),
            alias=alias,
        )

    def tearDown(self) -> None:
        self.room.close_all()

        for sock in self.sockets + self.peers:
            try:
                sock.close()
            except OSError:
                pass

    def test_rejects_empty_alias(self) -> None:
        session = self.create_session("   ")
        self.assertFalse(self.room.register(session))

    def test_rejects_alias_longer_than_20_characters(self) -> None:
        session = self.create_session("A" * 21)
        self.assertFalse(self.room.register(session))

    def test_rejects_duplicate_alias_ignoring_case(self) -> None:
        first = self.create_session("Juan")
        second = self.create_session("jUaN")

        self.assertTrue(self.room.register(first))
        self.assertFalse(self.room.register(second))

    def test_register_and_remove_client(self) -> None:
        session = self.create_session("Maria")

        self.assertTrue(self.room.register(session))
        self.assertEqual(self.room.count(), 1)

        removed = self.room.remove(session.client_socket)

        self.assertIs(removed, session)
        self.assertEqual(self.room.count(), 0)

    def test_broadcast_reaches_multiple_clients(self) -> None:
        first = self.create_session("Juan")
        second = self.create_session("Maria")

        self.assertTrue(self.room.register(first))
        self.assertTrue(self.room.register(second))

        self.room.broadcast(
            {"tipo": "mensaje", "alias": "Juan", "texto": "Hola"}
        )

        for peer in self.peers:
            peer.settimeout(1.0)
            received = peer.recv(4096)
            message = json.loads(received.decode("utf-8"))
            self.assertEqual(message["texto"], "Hola")

    def test_message_handler_broadcasts_chat_message(self) -> None:
        first = self.create_session("Juan")
        second = self.create_session("Maria")

        self.room.register(first)
        self.room.register(second)

        handler = ChatMessageHandler(self.room)
        handler.handle(
            first,
            {"tipo": "mensaje", "texto": "Prueba de chat"},
        )

        for peer in self.peers:
            peer.settimeout(1.0)
            message = json.loads(peer.recv(4096).decode("utf-8"))
            self.assertEqual(message["alias"], "Juan")
            self.assertEqual(message["texto"], "Prueba de chat")

    def test_removing_one_client_preserves_the_others(self) -> None:
        first = self.create_session("Juan")
        second = self.create_session("Maria")

        self.room.register(first)
        self.room.register(second)

        self.room.remove(first.client_socket)

        self.room.broadcast(
            {"tipo": "mensaje", "alias": "Maria", "texto": "Sigo aquí"}
        )

        second_peer = self.peers[1]
        second_peer.settimeout(1.0)
        message = json.loads(
            second_peer.recv(4096).decode("utf-8")
        )

        self.assertEqual(message["texto"], "Sigo aquí")
        self.assertEqual(self.room.count(), 1)

    def test_invalid_json_is_rejected(self) -> None:
        server_side, client_side = socket.socketpair()

        try:
            client_side.sendall(b"{json incorrecto}\n")
            with self.assertRaises(ProtocolError):
                receive_message(server_side, bytearray())
        finally:
            server_side.close()
            client_side.close()

    def test_oversized_message_is_rejected(self) -> None:
        server_side, client_side = socket.socketpair()

        try:
            client_side.sendall(
                b"x" * MAX_MESSAGE_SIZE + b"\n"
            )
            with self.assertRaises(ProtocolError):
                receive_message(server_side, bytearray())
        finally:
            server_side.close()
            client_side.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
