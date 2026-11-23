"""Ordered greetd requests and cancellation; no sockets, passwords in logs, or PAM bypass."""
from collections import deque

COMMAND = ['/usr/bin/start-hyprland']
ENVIRONMENT = ['XDG_SESSION_TYPE=wayland', 'XDG_CURRENT_DESKTOP=Hyprland', 'XDG_SESSION_DESKTOP=Hyprland']


class GreetdProtocol:
    def __init__(self, send, emit):
        self.send = send
        self.emit = emit
        self.pending = deque()
        self.generation = 0
        self.state = 'inactive'
        self.user = ''
        self.cancelling = False
        self.response_required = False

    def request(self, kind, value):
        self.pending.append((kind, self.generation))
        self.send(value)

    def set_state(self, value):
        self.state = value
        self.emit({'type': 'state', 'state': value, 'user': self.user})

    def cancel(self):
        if self.cancelling:
            return
        if self.state == 'inactive' and not self.pending:
            self.emit({'type': 'cancelled'})
            return
        self.cancelling = True
        self.response_required = False
        self.generation += 1
        self.request('cancel', {'type': 'cancel_session'})

    def command(self, value):
        kind = value.get('type')
        if kind == 'cancel':
            self.cancel()
        elif kind == 'create':
            user = value.get('user')
            if self.state != 'inactive' or self.pending or not isinstance(user, str) or not user or len(user) > 256 or '\x00' in user:
                raise ValueError('Invalid create request')
            self.user = user
            self.set_state('authenticating')
            self.request('auth', {'type': 'create_session', 'username': user})
        elif kind == 'respond':
            response = value.get('response')
            if self.cancelling or not self.response_required or self.state != 'authenticating':
                return
            if not isinstance(response, str) or len(response) > 65536 or '\x00' in response:
                raise ValueError('Invalid response')
            self.response_required = False
            self.request('auth', {'type': 'post_auth_message_response', 'response': response})
        elif kind == 'launch':
            if self.cancelling or self.state != 'ready' or self.pending:
                raise ValueError('Not authenticated')
            if value.get('command') != COMMAND or value.get('environment') != ENVIRONMENT:
                raise ValueError('Invalid session command')
            self.set_state('launching')
            self.request('launch', {'type': 'start_session', 'cmd': COMMAND, 'env': ENVIRONMENT})
        else:
            raise ValueError('Invalid command')

    def reply(self, value):
        if not self.pending:
            raise ValueError('Unsolicited greetd reply')
        kind, generation = self.pending.popleft()
        if generation != self.generation:
            return  # Replies to the cancelled attempt are never authentication.
        reply_type = value.get('type')
        if kind == 'cancel':
            if reply_type != 'success':
                raise ValueError('Cancellation failed')
            self.cancelling = False
            self.set_state('inactive')
            self.emit({'type': 'cancelled'})
        elif reply_type == 'error':
            self.response_required = False
            self.emit({'type': 'auth_failure' if value.get('error_type') == 'auth_error' else 'error',
                       'message': value.get('description', 'Sign-in failed')})
            self.cancel()
        elif reply_type == 'success':
            if kind == 'auth':
                self.set_state('ready')
                self.emit({'type': 'ready'})
            elif kind == 'launch':
                self.set_state('launched')
                self.emit({'type': 'launched'})
            else:
                raise ValueError('Unexpected success')
        elif reply_type == 'auth_message' and kind == 'auth':
            style = value.get('auth_message_type')
            if style not in ('secret', 'visible', 'info', 'error') or not isinstance(value.get('auth_message'), str):
                raise ValueError('Invalid authentication message')
            self.response_required = style in ('secret', 'visible')
            self.emit({'type': 'message', 'message': value['auth_message'], 'error': style == 'error',
                       'responseRequired': self.response_required, 'echoResponse': style != 'secret'})
            if not self.response_required:
                self.request('auth', {'type': 'post_auth_message_response'})
        else:
            raise ValueError('Unexpected greetd reply')
