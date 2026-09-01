from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, name: str = "YFPhoneCam.Desktop.0.1") -> None:
        super().__init__()
        self._name = name
        self._server = QLocalServer(self)

    def acquire(self) -> bool:
        existing = QLocalSocket(self)
        existing.connectToServer(self._name)
        if existing.waitForConnected(250):
            existing.write(b"activate")
            existing.flush()
            existing.waitForBytesWritten(250)
            existing.disconnectFromServer()
            return False

        QLocalServer.removeServer(self._name)
        if not self._server.listen(self._name):
            return False
        self._server.newConnection.connect(self._accept_connection)
        return True

    def _accept_connection(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self._activate(s))

    def _activate(self, socket: QLocalSocket) -> None:
        socket.readAll()
        socket.disconnectFromServer()
        self.activated.emit()
