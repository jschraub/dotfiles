"""Workspace reference tests. No real apps, TTY reads, or application commands."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'quickshell/.config/quickshell/atelier'
spec = importlib.util.spec_from_file_location('shortcut_context', LIBRARY / 'shortcut_context.py')
shortcuts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shortcuts)


def client(address, cls, workspace=1, **extra):
    return dict(dict(address=address, pid=123 if 'ghostty' in cls else 456, mapped=True, hidden=False,
                     workspace={'id': workspace}, **{'class': cls}), **extra)


class ShortcutContextTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = Path(temp.name)
        self.clients = [client('terminal', 'com.mitchellh.ghostty'),
                        client('browser', 'zen'), client('other', 'zen', 2)]
        self.monitors = [{'focused': True, 'activeWorkspace': {'id': 1}}]
        self.active = {}
        self.calls = []
        self.available = {'ghostty', 'zen-browser', 'opencode'}
        which = patch.object(shortcuts.shutil, 'which',
                             side_effect=lambda name: '/bin/' + name if name in self.available else None)
        which.start()
        self.addCleanup(which.stop)

    def run_command(self, command, **kwargs):
        self.calls.append(command)
        if command == ['ghostty', '+list-keybinds', '--plain']:
            return 'keybind = ctrl+==increase_font_size:1\nkeybind = ctrl+shift+p=toggle_command_palette\n'
        return json.dumps({'clients': self.clients, 'monitors': self.monitors,
                           'activewindow': self.active}[command[-1]])

    def snapshot(self, **kwargs):
        with patch.object(shortcuts, 'terminal_processes', return_value={'opencode'}):
            return shortcuts.snapshot([], config=self.config, run=self.run_command, **kwargs)

    def test_tabs_include_workspace_apps_and_open_on_previously_focused_app(self):
        # Menu focus has already cleared activewindow; original address wins.
        data = self.snapshot(window_address='terminal')
        self.assertEqual([t['label'] for t in data['tabs']], ['Desktop', 'Ghostty', 'Zen'])
        self.assertEqual(data['selected'], 'app:com.mitchellh.ghostty')
        terminal = data['tabs'][1]
        self.assertTrue(any(r['description'] == 'Command palette' for r in terminal['rows']))
        self.assertTrue(any(r['description'] == 'New session' for r in terminal['rows']))
        self.assertIn('not necessarily the focused pane', terminal['note'])

    def test_apps_are_deduplicated_and_window_titles_never_leave_module(self):
        self.clients.append(dict(client('second', 'com.mitchellh.ghostty'), title='PRIVATE DOCUMENT TITLE'))
        data = self.snapshot(window_address='second')
        self.assertEqual(data['tabs'][1]['label'], 'Ghostty (2)')
        self.assertNotIn('PRIVATE DOCUMENT TITLE', json.dumps(data))

    def test_hidden_unmapped_and_other_workspace_apps_are_excluded(self):
        self.clients.extend([client('hidden', 'hidden-app', hidden=True),
                             client('unmapped', 'unmapped-app', mapped=False),
                             client('pinned', 'pinned-app', 2, pinned=True)])
        labels = [t['label'] for t in self.snapshot()['tabs']]
        self.assertEqual(labels, ['Desktop', 'Ghostty', 'Zen', 'pinned-app'])

    def test_stale_focus_hint_does_not_select_another_workspace(self):
        self.active = {'address': 'browser'}
        data = self.snapshot(window_address='other')
        self.assertEqual(data['selected'], 'app:zen')

    def test_special_workspace_is_respected(self):
        self.monitors[0]['specialWorkspace'] = {'id': -99}
        self.clients.append(client('special', 'special-app', -99))
        self.assertEqual([t['label'] for t in self.snapshot()['tabs']], ['Desktop', 'special-app'])

    def test_hyprland_failure_retains_desktop_reference(self):
        def broken(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)
        data = shortcuts.snapshot([{'key': 'SUPER+F1'}], config=self.config, run=broken)
        self.assertEqual(data['tabs'][0]['rows'], [{'key': 'SUPER+F1'}])
        self.assertIn('unavailable', data['tabs'][0]['note'])

    def test_unknown_app_has_honest_empty_profile(self):
        self.clients = [client('unknown', 'unregistered')]
        data = self.snapshot(window_address='unknown')
        self.assertEqual(data['selected'], 'app:unregistered')
        self.assertEqual(data['tabs'][1]['rows'], [])
        self.assertIn('No shortcut profile yet', data['tabs'][1]['note'])

    def test_ghostty_effective_config_handles_equals_key_and_drops_command_payloads(self):
        run = Mock(return_value='keybind = ctrl+==increase_font_size:1\n'
                                'keybind = ctrl+x=text:PRIVATE PAYLOAD\n'
                                'keybind = ctrl+y=write_screen_file:open,plain\n')
        rows = shortcuts.ghostty_rows(run)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['key'], 'Ctrl + =')
        self.assertNotIn('PRIVATE', json.dumps(rows))
        self.assertEqual(run.call_args.kwargs['timeout'], 3)

    def test_custom_profiles_are_data_only_and_replace_builtins(self):
        self.available.add('herdr')
        custom = self.config / 'atelier/shortcuts.json'
        custom.parent.mkdir()
        custom.write_text(json.dumps({'profiles': [{
            'id': 'herdr', 'name': 'herdr', 'processes': ['herdr'],
            'bindings': [{'key': '?', 'description': 'Show help'}],
            'command': 'must never execute'
        }, {'id': 'zen', 'name': 'My Zen', 'classes': ['zen'],
            'bindings': [{'key': 'Alt+X', 'description': 'My shortcut'}]}]}))
        data = self.snapshot()
        self.assertEqual(data['tabs'][2]['label'], 'My Zen')
        self.assertEqual(data['tabs'][2]['rows'][0]['source'], 'User reference')
        self.assertIn('herdr', [p['id'] for p in data['tools']])
        self.assertNotIn('must never execute', json.dumps(data))
        self.assertTrue(all(c[0] in ('ghostty', 'hyprctl') for c in self.calls))

    def test_uninstalled_tools_are_not_offered_in_either_scope(self):
        data = self.snapshot()
        self.assertNotIn('tmux', [p['id'] for p in data['tools']])
        self.assertNotIn('reference:tmux', [p['id'] for p in data['library']])
        self.assertEqual(data['tabs'][1]['toolIds'], ['opencode'])

    def test_installed_but_closed_tool_is_only_in_library(self):
        self.available.add('tmux')
        data = self.snapshot()
        self.assertIn('reference:tmux', [p['id'] for p in data['library']])
        self.assertNotIn('tmux', data['tabs'][1]['toolIds'])
        self.assertFalse(any(r['category'] == 'tmux' for r in data['tabs'][1]['rows']))
        self.assertTrue(any('tmux' in r['category'] for r in data['library'][0]['rows']))

    def test_terminal_shared_with_other_workspace_does_not_leak_tools_into_workspace(self):
        self.clients.append(client('remote-terminal', 'com.mitchellh.ghostty', 2))
        with patch.object(shortcuts, 'terminal_processes') as probe:
            data = shortcuts.snapshot([], config=self.config, run=self.run_command)
        probe.assert_not_called()
        self.assertEqual(data['tabs'][1]['toolIds'], [])
        self.assertIn('withheld', data['tabs'][1]['note'])
        self.assertIn('reference:opencode', [p['id'] for p in data['library']])

    def test_open_tool_proves_availability_even_if_not_on_path(self):
        self.available.remove('opencode')
        data = self.snapshot()
        self.assertIn('opencode', data['tabs'][1]['toolIds'])
        self.assertIn('reference:opencode', [p['id'] for p in data['library']])

    def test_profile_can_specify_an_executable_different_from_process_name(self):
        custom = self.config / 'atelier/shortcuts.json'
        custom.parent.mkdir()
        custom.write_text(json.dumps({'profiles': [{
            'id': 'custom-tool', 'processes': ['tool-worker'],
            'executables': ['tool-launcher'], 'bindings': []
        }]}))
        self.available.add('tool-launcher')
        self.assertIn('reference:custom-tool', [p['id'] for p in self.snapshot()['library']])

    def test_malformed_custom_profiles_do_not_replace_valid_defaults(self):
        custom = self.config / 'atelier/shortcuts.json'
        custom.parent.mkdir()
        custom.write_text('{"profiles":[{"id":"desktop","bindings":[]}]}')
        data = self.snapshot()
        self.assertEqual(data['tabs'][2]['label'], 'Zen')
        self.assertIn('could not be loaded', data['tabs'][0]['note'])

    def test_opencode_leader_and_global_overrides_disabled_and_object_keys(self):
        path = self.config / 'opencode/cli.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'keybinds': {
            'leader': 'ctrl+space', 'session.new': ['<leader>n', 'alt+n'],
            'app.exit': False, 'session.interrupt': 'none',
            'command.palette.show': {'key': 'ctrl+k', 'preventDefault': False}
        }}))
        data = self.snapshot()
        rows = next(t for t in data['tools'] if t['id'] == 'opencode')['rows']
        keyed = {r['context']: r for r in rows}
        self.assertNotIn('app.exit', keyed)
        self.assertNotIn('session.interrupt', keyed)
        self.assertEqual(keyed['command.palette.show']['key'], 'Ctrl + K')
        self.assertIn('Ctrl + space → N', keyed['session.new']['key'])
        self.assertEqual(keyed['session.new']['source'], 'OpenCode global override')

    def test_disabled_opencode_leader_removes_only_leader_alternatives(self):
        path = self.config / 'opencode/cli.json'
        path.parent.mkdir()
        path.write_text('{"keybinds":{"leader":false}}')
        data = self.snapshot()
        rows = next(t for t in data['tools'] if t['id'] == 'opencode')['rows']
        keyed = {r['context']: r for r in rows}
        self.assertNotIn('session.new', keyed)
        self.assertEqual(keyed['app.exit']['key'], 'Ctrl + C / Ctrl + D')

    def test_invalid_opencode_config_is_labelled_and_defaults_remain_readable(self):
        path = self.config / 'opencode/cli.json'
        path.parent.mkdir()
        path.write_text('not-json')
        data = self.snapshot()
        tool = next(t for t in data['tools'] if t['id'] == 'opencode')
        self.assertIn('could not be read', tool['note'])
        self.assertEqual(next(r for r in tool['rows'] if r['context'] == 'session.new')['key'], 'Ctrl + X → N')

    def test_process_detection_is_descendant_and_foreground_only(self):
        proc = self.config / 'proc'
        def process(pid, name, pgrp, foreground, children='', tty=123, state='S'):
            directory = proc / str(pid)
            (directory / 'task' / str(pid)).mkdir(parents=True)
            (directory / 'stat').write_text(f'{pid} ({name}) {state} 1 {pgrp} 1 {tty} {foreground} 0\n')
            (directory / 'task' / str(pid) / 'children').write_text(children)
        process(1, 'ghostty', 1, -1, '2 3 4 5', tty=0)
        process(2, 'opencode', 2, 2)
        process(3, 'background', 3, 2)
        process(4, 'defunct', 2, 2, state='Z')
        process(5, 'detached', 5, -1, tty=0)
        process(99, 'unrelated', 99, 99)
        self.assertEqual(shortcuts.terminal_processes([1], proc), {'opencode'})
        (proc / '1/task/1/children').write_text('')
        worker = proc / '1/task/100'
        worker.mkdir()
        (worker / 'children').write_text('2 3 4 5')
        self.assertEqual(shortcuts.terminal_processes([1], proc), {'opencode'},
                         'Shells can be children of a terminal worker thread')

    def test_backend_emits_snapshot_with_matching_request_id(self):
        spec = importlib.util.spec_from_file_location('shortcut_backend', LIBRARY / 'backend.py')
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
        with patch.dict(sys.modules, shortcut_context=shortcuts), \
                patch.object(shortcuts, 'snapshot', return_value={'tabs': [], 'tools': []}) as snapshot, \
                patch.object(backend, 'keybindings', return_value=[]), patch.object(backend, 'emit') as emit:
            backend.action({'action': 'bindings', 'windowAddress': 'original', 'requestId': 7})
        self.assertEqual(snapshot.call_args.kwargs['window_address'], 'original')
        self.assertEqual(emit.call_args.args[0], 'binding-context')
        self.assertEqual(emit.call_args.args[1]['requestId'], 7)
