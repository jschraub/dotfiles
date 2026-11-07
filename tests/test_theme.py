"""Portable appearance tests: temporary homes, no real apps, D-Bus, or sudo."""
import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = load('render_theme')
apply = load('apply_theme')


def parse(text):
    return apply.parse_jsonc(text)


class ThemeTest(unittest.TestCase):
    def setUp(self):
        quiet = redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def test_all_generated_outputs_match_palette(self):
        for relative, text in render.outputs().items():
            with self.subTest(path=relative):
                self.assertEqual((ROOT / relative).read_text(), text)

    def test_link_preserves_sources_under_folded_stow_directories(self):
        for relative in ['atelier.css', 'themes/Atelier Amber']:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                source_dir = base / 'dotfiles/ghostty/.config/ghostty'
                source = source_dir / relative
                source.parent.mkdir(parents=True)
                source.write_text('generated theme\n')
                config = base / 'home/.config'
                config.mkdir(parents=True)
                (config / 'ghostty').symlink_to(source_dir, target_is_directory=True)
                target = config / 'ghostty' / relative
                apply.link(source, target)
                self.assertFalse(source.is_symlink(), 'Installer replaced a tracked source with a symlink')
                self.assertEqual(source.read_text(), 'generated theme\n')
                self.assertEqual(list(source.parent.glob('*.pre-atelier.*')), [])

    def test_neutral_surfaces_and_readable_text(self):
        colors = json.loads((ROOT / 'theme/palette.json').read_text())['colors']
        def luminance(value):
            channels = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
            return sum(v * weight for v, weight in zip(linear, [.2126, .7152, .0722]))
        def contrast(a, b):
            values = sorted([luminance(colors[a]), luminance(colors[b])])
            return (values[1] + .05) / (values[0] + .05)
        for key in ['background', 'panel', 'raised', 'hover', 'line', 'text', 'muted', 'faint']:
            value = colors[key]
            self.assertEqual(value[1:3], value[3:5])
            self.assertEqual(value[3:5], value[5:7])
        for a, b in [('text', 'background'), ('muted', 'panel'), ('accent', 'panel'),
                     ('onAccent', 'accent'), ('text', 'selection'), ('text', 'raised'),
                     ('accent', 'selection'), ('onAccent', 'orange'), ('orange', 'panel')]:
            self.assertGreaterEqual(contrast(a, b), 4.5, (a, b, contrast(a, b)))
        for item, background in json.loads((ROOT / 'theme/palette.json').read_text())['promptBackgrounds'].items():
            colors['prompt_' + item] = background
            self.assertGreaterEqual(contrast('accent', 'prompt_' + item), 4.5, item)

    def test_jsonc_theme_edit_preserves_unrelated_settings_and_comments(self):
        for old in ['{}', '{\n// comment\n"x": [1,2,],\n}',
                    '{"theme": "old", "x": {"theme":"nested"}}',
                    '{"theme": {"name":"old", "mode":"light"}, "x":true}',
                    '{"x":{"theme":1}, "theme": "old"}',
                    '{/* "theme": "comment" */ "x": "https://example.com"}',
                    '{"x": ",}", "theme": "old",}',
                    '{"x": "escaped \\\" quote", "theme": [1,2,]}']:
            with self.subTest(old=old):
                result = apply.set_jsonc_value(old, 'theme', {'name': 'system', 'mode': 'dark'})
                before, after = parse(old), parse(result)
                self.assertEqual(after.pop('theme'), {'name': 'system', 'mode': 'dark'})
                before.pop('theme', None)
                self.assertEqual(before, after)
                self.assertEqual(result, apply.set_jsonc_value(result, 'theme', {'name': 'system', 'mode': 'dark'}))
                if '// comment' in old:
                    self.assertIn('// comment', result)

    def test_install_in_fresh_home_and_migrate_old_links_idempotently(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            gtk = home / '.config/gtk-4.0'
            gtk.mkdir(parents=True)
            (gtk / 'gtk.css').symlink_to('/missing/old-catppuccin.css')
            code = home / '.config/Code/User/settings.json'
            code.parent.mkdir(parents=True)
            code.write_text('{// retain\n"editor.fontSize":13, "workbench.colorTheme":"old",}\n')
            cli = home / '.config/opencode/cli.json'
            cli.parent.mkdir(parents=True)
            cli.write_text('{"tabs":{"mode":"on"},"theme":{"name":"old"}}')
            (home / '.config/ghostty').mkdir()
            apply.apply(home)
            self.assertTrue((home / '.config/ghostty/themes/Atelier Amber').is_file())
            self.assertTrue((home / '.config/ghostty/atelier.css').is_file())
            self.assertEqual((gtk / 'gtk.css').resolve(), ROOT / 'gtk-4.0/.config/gtk-4.0/gtk.css')
            self.assertEqual(len(list(gtk.glob('gtk.css.pre-atelier.*'))), 1)
            self.assertEqual(parse(code.read_text())['editor.fontSize'], 13)
            self.assertIn('// retain', code.read_text())
            self.assertEqual(parse(cli.read_text())['tabs'], {'mode': 'on'})
            files = set(home.rglob('*'))
            apply.apply(home)
            self.assertEqual(files, set(home.rglob('*')))
            self.assertFalse((home / 'palette.json').exists())
            self.assertFalse((home / 'templates').exists())

    def test_browser_chrome_preserves_existing_customizations_and_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            base = home / '.config/zen'
            profile = base / 'test.default'
            (profile / 'chrome').mkdir(parents=True)
            (base / 'profiles.ini').write_text('[Profile0]\nPath=test.default\nIsRelative=1\n')
            (profile / 'chrome/userChrome.css').write_text('/* custom */\n#custom { color: red; }\n')
            (profile / 'user.js').write_text('user_pref("other", true);\n')
            self.assertEqual(list(apply.browser_profiles(home, home / '.config')), [profile])
            source = ROOT / 'desktop-theme/.local/share/atelier/browser.css'
            apply.browser_theme(profile, source)
            self.assertIn('#custom { color: red; }', (profile / 'chrome/userChrome.css').read_text())
            self.assertIn('user_pref("other", true)', (profile / 'user.js').read_text())
            files = set(home.rglob('*'))
            apply.browser_theme(profile, source)
            self.assertEqual(files, set(home.rglob('*')))

    def test_ghostty_readability_preferences_survive_theme_change(self):
        text = (ROOT / 'ghostty/.config/ghostty/config').read_text()
        self.assertIn('background-opacity = 0.85', text)
        self.assertIn('font-size = 10', text)
        self.assertIn('theme = Atelier Amber', text)
        self.assertIn('gtk-custom-css = atelier.css', text)

    def test_fish_prompt_has_gray_segments_with_amber_text_and_resets_clean_git_colors(self):
        import shutil
        import subprocess
        if not shutil.which('fish') or not shutil.which('git'):
            self.skipTest('fish and git required for prompt integration')
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(['git', 'init', '-q', temp], check=True, capture_output=True)
            script = '''
source $argv[1]/fish/.config/fish/conf.d/00-atelier-palette.fish
source $argv[1]/fish/.config/fish/conf.d/tide_theme.fish
function _tide_print_item
    printf '%s|%s\n' $tide_git_bg_color $tide_git_color
end
printf '%s|%s|%s|%s\n' $tide_user_bg_color $tide_user_color $tide_clock_color $tide_pwd_bg_color
for item in user clock git node python rustc go php java docker
    set -l foreground tide_{$item}_color
    printf '%s\n' $$foreground
end
cd $argv[2]
_tide_item_git
touch dirty
_tide_item_git
rm dirty
_tide_item_git
'''
            result = subprocess.run(['fish', '--no-config', '-c', script, str(ROOT), temp],
                                    text=True, capture_output=True, check=True)
            c = json.loads((ROOT / 'theme/palette.json').read_text())['colors']
            backgrounds = json.loads((ROOT / 'theme/palette.json').read_text())['promptBackgrounds']
            color = lambda role: c[role][1:]
            self.assertEqual(result.stdout.splitlines(), [
                '|'.join([backgrounds['user'][1:], color('accent'), color('accent'), color('accent')]),
                *[color('accent')] * 10,
                '|'.join([backgrounds['git'][1:], color('accent')]),
                '|'.join(color(role) for role in ['selection', 'text']),
                '|'.join([backgrounds['git'][1:], color('accent')]),
            ])

    def test_prompt_gray_roles_are_distinct_with_one_shared_environment_shade(self):
        import itertools
        import shutil
        import subprocess
        if not shutil.which('fish'):
            self.skipTest('fish required for prompt integration')
        items = ['user', 'clock', 'git', 'node', 'python', 'rustc', 'go', 'php', 'java', 'docker']
        script = '''
source $argv[1]/fish/.config/fish/conf.d/00-atelier-palette.fish
source $argv[1]/fish/.config/fish/conf.d/tide_theme.fish
for item in $argv[2..]
    set -l background tide_{$item}_bg_color
    printf '%s\n' $$background
end
'''
        result = subprocess.run(['fish', '--no-config', '-c', script, str(ROOT), *items],
                                capture_output=True, text=True, check=True)
        backgrounds = result.stdout.splitlines()
        self.assertEqual(len(backgrounds), len(items))
        self.assertEqual(len(set(backgrounds[3:])), 1, list(zip(items, backgrounds)))
        roles = backgrounds[:4]  # User, clock, Git, any one environment item.
        self.assertEqual(len(set(roles)), 4, roles)
        palette = json.loads((ROOT / 'theme/palette.json').read_text())['colors']
        self.assertNotIn(palette['accent'][1:], backgrounds)  # Directory neighbors.
        self.assertNotIn(palette['selection'][1:], backgrounds)  # Dirty Git neighbors.
        channels = []
        for background in roles:
            self.assertEqual(background[:2], background[2:4])
            self.assertEqual(background[2:4], background[4:])
            channels.append(int(background[:2], 16))
        # Stronger steps than the old per-language four-channel increments.
        self.assertTrue(all(left - right >= 12 for left, right in zip(channels, channels[1:])), channels)
        # Hidden roles can't merge neighbors or reverse the grayscale ramp.
        for visible in itertools.product([False, True], repeat=len(roles)):
            shades = [shade for shade, shown in zip(channels, visible) if shown]
            self.assertTrue(all(left > right for left, right in zip(shades, shades[1:])), shades)

    def test_every_hyprland_color_reference_is_defined(self):
        common = (ROOT / 'hyprland-common/.config/hypr/common.lua').read_text()
        lua = render.outputs()['hyprland-common/.config/hypr/colors.lua']
        for name in re.findall(r'colors\.(\w+)', common):
            if name == 'lua':
                continue
            self.assertRegex(lua, rf'\b{name} = "[0-9a-f]{{6}}"')

    def test_setup_defaults_include_portable_theme_and_safe_greeter_mode(self):
        import subprocess
        result = subprocess.run(['bash', '-c', 'source ./setup.sh; default_items'],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertIn('theme', result.stdout.splitlines())
        installer = (ROOT / 'install-greetd-regreet.sh').read_text()
        theme_only = installer.split('if [[ "${1:-}" == "--theme-only" ]]; then', 1)[1].split('return', 1)[0]
        self.assertNotIn('systemctl', theme_only)
        self.assertNotIn('PAM_DEST', theme_only)


if __name__ == '__main__':
    unittest.main()
