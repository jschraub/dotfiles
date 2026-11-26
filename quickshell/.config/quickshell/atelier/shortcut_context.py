"""Read-only workspace shortcut reference. Never executes profile data or shortcuts."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
LIMIT = 1024 * 1024


def read_json(path):
    with path.open('rb') as stream:
        data = stream.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('Shortcut reference file exceeds 1 MiB')
    return json.loads(data)


def text(value, limit=240):
    return ''.join(c for c in str(value) if c.isprintable())[:limit]


def rows(values, source):
    if not isinstance(values, list) or len(values) > 500:
        raise ValueError('Expected at most 500 shortcuts per profile')
    result = []
    for value in values:
        if not isinstance(value, dict) or not all(isinstance(value.get(k), str) for k in ('key', 'description')):
            raise ValueError('Each shortcut needs a key and description')
        result.append({'key': text(value['key']), 'description': text(value['description']),
                       'category': text(value.get('category', 'General')),
                       'context': text(value.get('context', '')), 'source': source})
    return result


def profiles(config):
    builtins = read_json(HERE / 'shortcut_profiles.json')['profiles']
    warning = ''
    try:
        custom = read_json(config / 'atelier/shortcuts.json')
        custom = custom['profiles']
        if not isinstance(custom, list) or len(custom) > 32:
            raise ValueError('Expected at most 32 custom profiles')
        # Validate the entire custom document before applying any of it.
        custom = [profile(p, 'User reference') for p in custom]
    except FileNotFoundError:
        custom = []
    except (OSError, ValueError, KeyError, TypeError):
        custom = []
        warning = 'Custom shortcut profiles could not be loaded. Check ~/.config/atelier/shortcuts.json.'
    result = {p['id']: p for p in (profile(p, 'Documented defaults') for p in builtins)}
    result.update({p['id']: p for p in custom})
    return result, warning


def profile(value, source):
    if not isinstance(value, dict):
        raise ValueError('Expected a shortcut profile')
    identifier = value.get('id', '')
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', identifier) or identifier == 'desktop':
        raise ValueError('Invalid shortcut profile ID')
    result = {'id': identifier, 'name': text(value.get('name', identifier), 60),
              'rows': rows(value.get('bindings', []), source),
              'note': text(value.get('note', source), 400), 'source': source}
    for field in ('classes', 'processes', 'executables'):
        names = value.get(field, [])
        if not isinstance(names, list) or len(names) > 32 or not all(isinstance(n, str) for n in names):
            raise ValueError('Profile matches must be lists of exact names')
        result[field] = names if field == 'executables' else [n.casefold() for n in names]
    return result


def installed_profile(p):
    names = p['executables'] or [p['id']] + p['processes'] + p['classes']
    return any(shutil.which(name) for name in names if re.fullmatch(r'[A-Za-z0-9_.+-]+', name))


def installed_views(result, catalog, installed):
    """Available references only, with a combined searchable library."""
    references = [dict(id='reference:' + p['id'], label=p['name'], rows=p['rows'],
                       note=p['note'], terminal=False)
                  for p in catalog.values() if p['id'] in installed]
    combined = list(result['tabs'][0]['rows'])
    for reference in references:
        combined.extend(dict(row, category=reference['label'] + ' / ' + row['category'])
                        for row in reference['rows'])
    result['library'] = [dict(id='installed', label='All shortcuts', rows=combined, terminal=False,
                              note='Search all installed applications and tools with shortcut profiles, whether open or closed.'),
                         result['tabs'][0]] + references
    result['tools'] = [dict(id=p['id'], label=p['name'], rows=p['rows'], note=p['note'])
                       for p in catalog.values() if p['processes'] and p['id'] in installed]


def pretty(key):
    key = key.replace('arrow_', '').replace('digit_', '').replace('_', ' ').replace('+', ' + ')
    return re.sub(r'\b(ctrl|shift|alt|super|return|escape|tab|pageup|pagedown|left|right|up|down|home|end|[a-z]|f\d+)\b',
                  lambda match: match[0].upper() if len(match[0]) == 1 or match[0].startswith('f')
                  else match[0].capitalize(), key).strip()


GHOSTTY_ACTIONS = {
    'copy_to_clipboard': 'Copy selection', 'paste_from_clipboard': 'Paste clipboard',
    'paste_from_selection': 'Paste primary selection', 'reload_config': 'Reload configuration',
    'open_config': 'Open configuration', 'increase_font_size': 'Increase font size',
    'decrease_font_size': 'Decrease font size', 'reset_font_size': 'Reset font size',
    'new_window': 'New window', 'new_tab': 'New tab', 'close_tab': 'Close tab',
    'quit': 'Quit Ghostty', 'close_window': 'Close window', 'previous_tab': 'Previous tab',
    'next_tab': 'Next tab', 'last_tab': 'Last tab', 'new_split': 'New split',
    'goto_split': 'Focus split', 'resize_split': 'Resize split', 'goto_tab': 'Go to tab',
    'scroll_page_up': 'Scroll page up', 'scroll_page_down': 'Scroll page down',
    'scroll_to_top': 'Scroll to top', 'scroll_to_bottom': 'Scroll to bottom',
    'toggle_split_zoom': 'Zoom split', 'toggle_fullscreen': 'Toggle fullscreen',
    'toggle_command_palette': 'Command palette', 'start_search': 'Search scrollback',
    'end_search': 'Close search', 'select_all': 'Select all', 'adjust_selection': 'Adjust selection',
    'jump_to_prompt': 'Jump to prompt', 'move_tab': 'Move tab', 'inspector': 'Inspector',
}


def ghostty_rows(run):
    result = []
    for line in run(['ghostty', '+list-keybinds', '--plain'], timeout=3).splitlines()[:1000]:
        if not line.startswith('keybind = ') or '=' not in line[10:]:
            continue
        # Split at the last '=' because '=' and '+' can themselves be keys.
        key, action = line[10:].rsplit('=', 1)
        action, _, argument = action.partition(':')
        description = GHOSTTY_ACTIONS.get(action)
        if not description:
            continue  # Never display arbitrary text/send-command payloads.
        context = argument if re.fullmatch(r'[a-z0-9_,.-]{1,40}', argument) else ''
        result.append({'key': pretty(text(key)), 'description': description,
                       'category': 'Ghostty', 'context': context, 'source': 'Ghostty configuration'})
    return result


def opencode_rows(base, config):
    """Only read global TUI bindings, never server/provider configuration."""
    note = 'OpenCode V2 defaults + global cli.json. Session/environment/plugin bindings are not inspected.'
    try:
        overrides = read_json(config / 'opencode/cli.json').get('keybinds', {})
        if not isinstance(overrides, dict):
            raise ValueError('Invalid keybinds')
    except FileNotFoundError:
        overrides = {}
    except (OSError, ValueError, AttributeError):
        overrides = {}
        note = 'OpenCode V2 defaults; cli.json could not be read. Session overrides are not inspected.'
    def keys(value):
        if isinstance(value, dict):
            value = value.get('key')
        values = value if isinstance(value, list) else [value]
        return [key.strip() for part in values if isinstance(part, str)
                for key in part.split(',') if key.strip() not in ('none', '')][:16]
    leaders = keys(overrides.get('leader', 'ctrl+x'))
    result = []
    for row in base:
        value = overrides.get(row['context'], row['key'])
        expanded = []
        for key in keys(value):
            if '<leader>' in key:
                expanded.extend(key.replace('<leader>', leader + ' → ') for leader in leaders)
            else:
                expanded.append(key)
        if not expanded:
            continue
        result.append(dict(row, key=' / '.join(pretty(text(key)) for key in expanded),
                           source='OpenCode global override' if row['context'] in overrides else row['source']))
    return result, note


def terminal_processes(pids, proc=Path('/proc')):
    """Inspect descendant names and foreground process groups, never argv/env/TTY data."""
    found, seen, pending = set(), set(), list(pids)
    while pending and len(seen) < 256:
        pid = pending.pop()
        if type(pid) is not int or pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        try:
            directory = proc / str(pid)
            if directory.stat().st_uid != os.getuid():
                continue
            stat = (directory / 'stat').read_text()
            end = stat.rindex(')')
            fields = stat[end + 2:].split()
            # /proc/PID/stat fields 5, 7, 8: pgrp, tty_nr, tpgid.
            name = stat[stat.index('(') + 1:end].casefold()
            if fields[0] != 'Z' and int(fields[4]) != 0 and fields[2] == fields[5]:
                found.add(name)
            # Linux records children on the thread that spawned them. Ghostty
            # can spawn its shells from a worker, not its main thread.
            for index, task in enumerate((directory / 'task').iterdir()):
                if index >= 128:
                    break
                try:
                    children = (task / 'children').read_text().split()
                    pending.extend(int(child) for child in children[:256] if child.isdecimal())
                    pending = pending[-256:]
                except OSError:
                    continue
        except (OSError, ValueError, IndexError):
            continue
    return found


def snapshot(desktop, *, config, run, window_address=''):
    """One frozen, refreshable snapshot. App tabs never switch or focus real windows."""
    catalog, warning = profiles(config)
    ghostty = catalog.get('ghostty')
    if ghostty and ghostty['source'] == 'Documented defaults':
        try:
            ghostty['rows'] = ghostty_rows(run)
            ghostty['note'] = 'Ghostty configured bindings (queried on open). Per-window command-line overrides are not inspected.'
        except (OSError, subprocess.SubprocessError):
            ghostty['note'] = 'Ghostty configuration unavailable; showing documented defaults.'
    if 'opencode' in catalog and catalog['opencode']['source'] == 'Documented defaults':
        catalog['opencode']['rows'], catalog['opencode']['note'] = opencode_rows(catalog['opencode']['rows'], config)
    desktop_tab = {'id': 'desktop', 'label': 'Desktop', 'rows': desktop, 'terminal': False,
                   'note': 'Live Hyprland bindings. ' + warning}
    installed = {p['id'] for p in catalog.values() if installed_profile(p)}
    result = {'tabs': [desktop_tab], 'selected': 'desktop'}
    installed_views(result, catalog, installed)
    try:
        all_clients = json.loads(run(['hyprctl', '-j', 'clients']))
        monitors = json.loads(run(['hyprctl', '-j', 'monitors']))
        active = json.loads(run(['hyprctl', '-j', 'activewindow']))
        monitor = next((m for m in monitors if m.get('focused')), {})
        workspace = (monitor.get('specialWorkspace') or {}).get('id') or (monitor.get('activeWorkspace') or {}).get('id')
        if workspace is None:
            raise ValueError('No focused workspace')
        clients = [c for c in all_clients if c.get('mapped') and not c.get('hidden')
                   and ((c.get('workspace') or {}).get('id') == workspace or c.get('pinned'))]
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        desktop_tab['note'] += ' Workspace applications unavailable.'
        return result
    # A running desktop application also proves availability for launchers that
    # are not on PATH, such as Flatpak applications.
    installed.update(p['id'] for p in catalog.values()
                     if any(c.get('mapped') and str(c.get('class', '')).casefold() in p['classes']
                            for c in all_clients))
    target = next((c for c in clients if c.get('address') == window_address), None)
    if target is None:
        target = next((c for c in clients if c.get('address') == active.get('address')), None)
    grouped = {}
    for client in clients:
        cls = text(client.get('class') or client.get('initialClass') or 'unknown', 100).casefold()
        grouped.setdefault(cls, []).append(client)
    for cls, windows in grouped.items():
        matched = next((p for p in catalog.values() if cls in p['classes']), None)
        terminal = bool(matched and matched['id'] == 'ghostty')
        app_rows = list(matched['rows']) if matched else []
        note = matched['note'] if matched else 'No shortcut profile yet. Add a data-only profile in ~/.config/atelier/shortcuts.json.'
        label = matched['name'] if matched else text(windows[0].get('class') or 'Unknown application', 60)
        tool_ids = []
        if terminal:
            pids = {w.get('pid') for w in windows if type(w.get('pid')) is int}
            visible_addresses = {c.get('address') for c in clients}
            # One Ghostty process can span workspaces. Only attribute tools to
            # this workspace when ALL mapped windows for that PID are here.
            local_pids = {pid for pid in pids if all(c.get('address') in visible_addresses
                          for c in all_clients if c.get('pid') == pid and c.get('mapped'))}
            names = terminal_processes(local_pids) if local_pids else set()
            tools = [p for p in catalog.values() if names.intersection(p['processes'])]
            tool_ids = [t['id'] for t in tools]
            installed.update(tool_ids)
            for tool in tools:
                app_rows.extend(tool['rows'])
            note += (' Foreground tools in this terminal process tree: ' + ', '.join(t['name'] for t in tools) + '.'
                     if tools else ' No known foreground terminal tool detected.')
            note += ' Detection spans workspace-local Ghostty windows/tabs, not necessarily the focused pane.'
            if local_pids != pids:
                note += ' Tools in a terminal process shared with other workspaces are withheld.'
            note += ' Use All installed to browse other available tools.'
        identifier = 'app:' + cls
        result['tabs'].append({'id': identifier, 'label': label + (f' ({len(windows)})' if len(windows) > 1 else ''),
                               'rows': app_rows, 'baseRows': list(matched['rows']) if matched else [],
                               'terminal': terminal, 'note': note, 'toolIds': tool_ids})
        if target in windows:
            result['selected'] = identifier
    installed_views(result, catalog, installed)
    return result
