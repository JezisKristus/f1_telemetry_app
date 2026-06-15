import logging
import socket

logger = logging.getLogger(__name__)


class UDPForwarder:
    """Forwards raw UDP telemetry packets to downstream listeners (e.g. SimHub)."""

    def __init__(self, forward_host="127.0.0.1", forward_port=20778):
        self.forward_host = forward_host
        self.forward_port = forward_port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._enabled = forward_port is not None and forward_port > 0

    def forward(self, data: bytes):
        if not self._enabled:
            return
        try:
            self._sock.sendto(data, (self.forward_host, self.forward_port))
        except OSError as e:
            logger.debug("UDP forward failed: %s", e)

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass
