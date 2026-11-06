#!/usr/bin/env fish

set -g test_state (mktemp -d)
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
        if test "$test_case" = no-aur-updates
            return 1
        else if test "$test_case" = aur-query-error
            echo 'error: could not contact AUR' >&2
            return 1
        else if test "$test_case" = aur-query-unexpected-status
            return 2
        end
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
assert 'contains -- "paru --pacman /usr/local/libexec/upall-pacman --repo -Syu --noconfirm --nouseask" $test_commands' 'repository upgrades should run first'
assert 'contains -- "paru --pacman /usr/local/libexec/upall-pacman --aur -S --needed --noconfirm --nouseask --skipreview good" $test_commands' 'working AUR package should be upgraded'
assert 'contains -- "paru --pacman /usr/local/libexec/upall-pacman --aur -S --needed --noconfirm --nouseask --skipreview broken" $test_commands' 'broken AUR package should be attempted'
assert 'test -f "$test_failed_logs[1]"' 'failed AUR output should be retained'
assert 'test "$test_flatpak_called" = 1' 'Flatpak updates should continue after an AUR failure'
assert 'test "$test_arch_update_called" = 1' 'Cachy-Update status should be refreshed'

set -g test_case repo-replacement
set -g test_pending replacement
set -e test_commands
upall
assert 'contains -- "paru --pacman /usr/local/libexec/upall-pacman --repo -Syu --noconfirm --ask=4" $test_commands' 'declared repository replacement should retry automatically'
assert 'contains -- "paru --pacman /usr/local/libexec/upall-pacman --aur -S --needed --noconfirm --useask --skipreview replacement" $test_commands' 'declared AUR replacement should retry automatically'

set -g test_case optional-refresh
set -g test_pending good
functions -e arch-update
upall >"$test_state/missing-refresh.log" 2>&1
set -g missing_status $status
assert 'test $missing_status -eq 0' 'missing optional Cachy-Update should not fail updates'
assert 'not grep -q "Unknown command" "$test_state/missing-refresh.log"' 'missing optional command should not be executed'
assert 'grep -q "skipping status refresh" "$test_state/missing-refresh.log"' 'missing optional updater should be explained'

function arch-update
    return 1
end
upall >"$test_state/failed-refresh.log" 2>&1
set -g refresh_status $status
assert 'test $refresh_status -eq 1' 'installed updater refresh failure should be reported'
assert 'grep -q "Updates finished with failures: Cachy-Update" "$test_state/failed-refresh.log"' 'failed refresh should not report complete success'

functions -e arch-update
set -g test_case no-aur-updates
upall >"$test_state/no-aur-updates.log" 2>&1
set -g no_updates_status $status
assert 'test $no_updates_status -eq 0' 'empty Paru query with status 1 means no updates, not failure'
assert 'grep -q "No AUR updates available" "$test_state/no-aur-updates.log"' 'empty AUR result should be explained'

set -g test_case aur-query-error
upall >"$test_state/aur-query-error.log" 2>&1
set -g query_error_status $status
assert 'test $query_error_status -eq 1' 'AUR query errors must still fail'
assert 'grep -q "could not contact AUR" "$test_state/aur-query-error.log"' 'query diagnostics must be preserved'

set -g test_case aur-query-unexpected-status
upall >"$test_state/aur-query-status.log" 2>&1
set -g query_status $status
assert 'test $query_status -eq 1' 'unexpected query exit codes must still fail even without diagnostics'

rm -rf "$test_state"
