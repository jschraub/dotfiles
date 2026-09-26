#!/usr/bin/env fish

set -l test_state (mktemp -d)
set -gx XDG_STATE_HOME "$test_state/state"
source (path resolve (path dirname (status filename))/../.config/fish/functions/upall.fish)

function assert --argument-names condition message
    if not eval $condition
        echo "assertion failed: $message" >&2
        rm -rf "$test_state"
        exit 1
    end
end

function paru
    if contains -- -Qua $argv
        printf '%s\n' $test_pending
        return 0
    end
    if contains -- -Si $argv
        if test "$argv[-1]" = replacement
            echo 'Replaces        : legacy'
        else if test "$argv[-1]" = new
            echo 'Replaces        : old'
        else
            echo 'Replaces        : None'
        end
        return 0
    end
    return 0
end

function script
    set -l log $argv[2]
    set -l command $argv[4..-1]
    set -ga test_commands (string join ' ' -- $command)

    if contains -- --repo $command
        if test "$test_case" = repo-replacement; and not contains -- --ask=4 $command
            begin
                echo ':: new-1.0-1 and old are in conflict. Remove old? [y/N]'
                echo 'error: unresolvable package conflicts detected'
            end > "$log"
            return 1
        end
        return 0
    end

    set -l package $command[-1]
    if test "$package" = broken
        echo '==> ERROR: build failed' > "$log"
        set -ga test_failed_logs "$log"
        return 1
    end
    if test "$package" = replacement; and not contains -- --useask $command
        begin
            echo ':: Inner conflicts found:'
            echo '    replacement: legacy'
            echo 'error: can not install conflicting packages with --noconfirm'
        end > "$log"
        return 1
    end
    return 0
end

function flatpak
    set -g test_flatpak_called 1
end

function arch-update
    set -g test_arch_update_called 1
end

set -g test_case deferred-package
set -g test_pending good broken
set -e test_commands
set -e test_failed_logs
set -e test_flatpak_called
set -e test_arch_update_called
upall
assert 'contains -- "paru --repo -Syu --noconfirm --nouseask" $test_commands' 'repository upgrades should run first'
assert 'contains -- "paru --aur -S --needed --noconfirm --nouseask --skipreview good" $test_commands' 'working AUR package should be upgraded'
assert 'contains -- "paru --aur -S --needed --noconfirm --nouseask --skipreview broken" $test_commands' 'broken AUR package should be attempted'
assert 'test -f "$test_failed_logs[1]"' 'failed AUR output should be retained'
assert 'test "$test_flatpak_called" = 1' 'Flatpak updates should continue after an AUR failure'
assert 'test "$test_arch_update_called" = 1' 'Cachy-Update status should be refreshed'

set -g test_case repo-replacement
set -g test_pending replacement
set -e test_commands
upall
assert 'contains -- "paru --repo -Syu --noconfirm --ask=4" $test_commands' 'declared repository replacement should retry automatically'
assert 'contains -- "paru --aur -S --needed --noconfirm --useask --skipreview replacement" $test_commands' 'declared AUR replacement should retry automatically'

rm -rf "$test_state"
