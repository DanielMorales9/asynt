import struct
from asyncio.protocols import Protocol


class VariableExchanger(Protocol):

    def __init__(self, rt, peer_pid=None):
        self.runtime = rt
        self.peer_pid = peer_pid
        self.bytes = bytearray()
        self.buffer = {}
        self.transport = None

    def connection_made(self, transport):
        """
        Called when a connection is made.
        """
        self.transport = transport
        if self.peer_pid is not None:  # party is client (peer is server)
            pid = self.runtime.pid.to_bytes(1, 'little')  # send pid
            transport.write(pid)
            self.handshake()

    def handshake(self):
        self.runtime.parties[self.peer_pid].protocol = self
        if all(p.protocol is not None for p in self.runtime.parties):
            self.runtime.parties[self.runtime.pid].protocol.set_result(
                self.runtime)

    def send_data(self, pc, payload):
        """
        Send payload
        """
        payload_size = len(payload)
        fmt = f'!HI{payload_size}s'
        t = (pc, payload_size, payload)
        self.transport.write(struct.pack(fmt, *t))

    def data_received(self, data):
        """Called when data is received from the peer.

        Received bytes are unpacked as a program counter and the payload
        (actual data). The payload is passed to the appropriate Future, if any.

        First message from peer is processed differently if peer is a client.
        """
        start = 6
        self.bytes.extend(data)
        if self.peer_pid is None:  # peer is client (party is server)
            peer_pid = int.from_bytes(self.bytes[:1], 'little')
            self.peer_pid = peer_pid
            len_packet = 1
            self.handshake()
            del self.bytes[:len_packet]

        while self.bytes:
            fmt = '!HI'
            pc, payload_size = struct.unpack(fmt, data[:start])
            len_packet = start + payload_size

            if len(self.bytes) < len_packet:
                return

            fmt = f'!{payload_size}s'
            unpacked = struct.unpack(fmt, self.bytes[start:len_packet])

            del self.bytes[:len_packet]
            payload = unpacked[-1]
            if pc in self.buffer:
                self.buffer[pc].set_result(payload)
            else:
                self.buffer[pc] = payload

    def connection_lost(self, exc):
        pass

    def close_connection(self):
        """Close connection with the peer."""
        self.transport.close()
