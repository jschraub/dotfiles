"""Cancellation ordering and authentication invariants without network or PAM."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'quickshell/.config/quickshell/atelier'))
from greetd_protocol import COMMAND, ENVIRONMENT, GreetdProtocol
sys.path.pop(0)


class GreetdProtocolTest(unittest.TestCase):
    def setUp(self):
        self.requests, self.events = [], []
        self.client = GreetdProtocol(self.requests.append, self.events.append)
        self.client.command({'type': 'create', 'user': 'fixture-account'})

    def test_cancel_ack_is_not_authentication_and_replacement_waits_for_it(self):
        self.client.cancel()
        with self.assertRaises(ValueError):
            self.client.command({'type': 'create', 'user': 'fixture-account'})
        self.client.reply({'type': 'success'})  # Old create response, already cancelled.
        self.assertNotIn('ready', [event['type'] for event in self.events])
        self.client.reply({'type': 'success'})  # Cancellation acknowledgement.
        self.assertEqual(self.client.state, 'inactive')
        self.assertEqual(self.events[-1]['type'], 'cancelled')
        self.client.command({'type': 'create', 'user': 'fixture-account'})
        self.assertEqual(self.client.state, 'authenticating')
        self.assertNotIn('ready', [event['type'] for event in self.events])

    def test_cancel_failure_never_authorizes_another_attempt(self):
        self.client.cancel()
        self.client.reply({'type': 'error', 'error_type': 'auth_error'})
        with self.assertRaises(ValueError):
            self.client.reply({'type': 'error', 'error_type': 'error'})
        self.assertNotIn('ready', [event['type'] for event in self.events])

    def test_authentication_and_fixed_command_are_required_for_launch(self):
        with self.assertRaises(ValueError):
            self.client.command({'type': 'launch', 'command': COMMAND, 'environment': ENVIRONMENT})
        self.client.reply({'type': 'success'})
        with self.assertRaises(ValueError):
            self.client.command({'type': 'launch', 'command': ['/bin/sh'], 'environment': ENVIRONMENT})
        self.client.command({'type': 'launch', 'command': COMMAND, 'environment': ENVIRONMENT})
        self.client.reply({'type': 'success'})
        self.assertEqual(self.events[-1]['type'], 'launched')

    def test_authentication_failure_cancels_before_retry(self):
        self.client.reply({'type': 'error', 'error_type': 'auth_error', 'description': 'Verification timed out'})
        self.assertEqual(self.requests[-1]['type'], 'cancel_session')
        self.assertIn('auth_failure', [event['type'] for event in self.events])
        with self.assertRaises(ValueError):
            self.client.command({'type': 'create', 'user': 'fixture-account'})
        self.client.reply({'type': 'success'})
        self.client.command({'type': 'create', 'user': 'fixture-account'})

    def test_password_response_goes_only_to_greetd_not_to_ui_events(self):
        self.client.reply({'type': 'auth_message', 'auth_message_type': 'secret', 'auth_message': 'Password:'})
        secret = 'fixture-only-transport-secret'
        self.client.command({'type': 'respond', 'response': secret})
        self.assertEqual(self.requests[-1]['response'], secret)
        self.assertNotIn(secret, json.dumps(self.events))
