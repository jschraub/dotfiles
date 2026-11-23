"""Private pipe/socket boundary for the root-installed greeter's greetd protocol."""
import json
import os
import selectors
import socket
import struct
import sys

from greetd_protocol import GreetdProtocol

MAX_FRAME = 1024 * 1024


def emit(value):
    # Only state/provider messages are emitted. Input responses are never echoed.
    print(json.dumps(value), flush=True)


def main():
    address = os.environ.get('GREETD_SOCK', '')
    if not address.startswith('/'):
        raise ValueError('Missing greetd socket')
    with socket.socket(socket.AF_UNIX) as connection, selectors.DefaultSelector() as selector:
        connection.connect(address)
        connection.setblocking(False)
        outgoing = bytearray()
        frames = bytearray()
        commands = bytearray()

        def send(value):
            payload = json.dumps(value, ensure_ascii=False).encode()
            outgoing.extend(struct.pack('=I', len(payload)) + payload)
            selector.modify(connection, selectors.EVENT_READ | selectors.EVENT_WRITE, 'socket')

        protocol = GreetdProtocol(send, emit)
        selector.register(connection, selectors.EVENT_READ, 'socket')
        selector.register(sys.stdin.fileno(), selectors.EVENT_READ, 'stdin')
        emit({'type': 'available', 'value': True})
        while True:
            for key, events in selector.select():
                if key.data == 'stdin':
                    data = os.read(sys.stdin.fileno(), 65536)
                    if not data:
                        return
                    commands.extend(data)
                    if len(commands) > MAX_FRAME:
                        raise ValueError('Oversized command')
                    while b'\n' in commands:
                        line, _, remaining = commands.partition(b'\n')
                        commands[:] = remaining
                        protocol.command(json.loads(line))
                else:
                    if events & selectors.EVENT_WRITE and outgoing:
                        count = connection.send(outgoing)
                        del outgoing[:count]
                        if not outgoing:
                            selector.modify(connection, selectors.EVENT_READ, 'socket')
                    if events & selectors.EVENT_READ:
                        data = connection.recv(65536)
                        if not data:
                            return
                        frames.extend(data)
                        while len(frames) >= 4:
                            length = struct.unpack('=I', frames[:4])[0]
                            if length == 0 or length > MAX_FRAME:
                                raise ValueError('Invalid frame size')
                            if len(frames) < length + 4:
                                break
                            value = json.loads(frames[4:length + 4])
                            del frames[:length + 4]
                            if not isinstance(value, dict):
                                raise ValueError('Invalid reply')
                            protocol.reply(value)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, AttributeError):
        emit({'type': 'error', 'message': 'Sign-in connection failed. Please try again.'})
    finally:
        emit({'type': 'available', 'value': False})
