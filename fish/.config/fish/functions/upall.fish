function upall --description 'Update Arch packages via paru and Flatpaks, then refresh Cachy-Update'
    set -l failed
    set -g __upall_deferred

    echo "Starting system and AUR updates..."
    __upall_sysupgrade
    or set -a failed "system/AUR"

    echo "---"

    echo "Starting Flatpak updates..."
    flatpak update -y
    or set -a failed flatpak

    echo "---"

    # paru/flatpak don't touch cachy-update's cached state, so its tray icon and
    # notification keep advertising the pre-update list until the daily timer
    # fires. Re-check here to clear it immediately.
    echo "Refreshing Cachy-Update status..."
    arch-update --check

    echo "---"
    set -l deferred $__upall_deferred
    set -e __upall_deferred
    if test (count $failed) -gt 0
        echo "Updates finished with failures: $failed" >&2
        return 1
    end
    if test (count $deferred) -gt 0
        echo "All updates complete except $deferred -- that needs a conflict settled by hand." >&2
        return 0
    end
    echo "All updates complete!"
end

function __upall_sysupgrade --description 'paru -Syu, retrying once past a conflict --noconfirm cannot answer'
    # --noconfirm cannot answer a conflict prompt, so both pacman and paru abort
    # the whole upgrade over one. Record the run on a pty -- script(1) keeps
    # colours, progress bars and the sudo/fingerprint prompt working -- and if
    # that is why it died, work out whether the conflict is safe to answer.
    set -l log (mktemp -t upall-XXXXXX.log)
    script -qec 'paru -Syu --noconfirm' $log
    set -l ret $status

    if test $ret -eq 0
        rm -f $log
        return 0
    end

    # Strip the pty's escape sequences and carriage returns before matching.
    set -l out (sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g; s/\r//g' $log)
    rm -f $log

    if string match -q '*unresolvable package conflicts*' -- $out
        __upall_fix_pacman_conflict $out
        return $status
    end

    if string match -q '*can not install conflicting packages with --noconfirm*' -- $out
        __upall_fix_paru_conflict $out
        return $status
    end

    return $ret
end

function __upall_fix_pacman_conflict --description 'Retry when a repo package supersedes an installed one'
    # pacman asks ":: X and Y are in conflict. Remove Y?" and --noconfirm says
    # no, leaving "unresolvable package conflicts detected".
    set -l removable
    for line in $argv
        set -l caps (string match -rg '^:: (\S+) and (\S+) are in conflict.*[Rr]emove ([^?]+)\?' -- $line)
        test (count $caps) -eq 3
        or continue

        set -l victim $caps[3]
        # The other side of the pair, minus its -pkgver-pkgrel suffix.
        set -l incoming (string replace -r -- '-[^-]+-[^-]+$' '' $caps[1])
        test $incoming != $victim
        or set incoming (string replace -r -- '-[^-]+-[^-]+$' '' $caps[2])

        # Only auto-answer when the incoming package explicitly Replaces the
        # installed one; a genuine either/or conflict still deserves a human.
        if __upall_replaces $incoming $victim
            set -a removable $victim
        else
            echo "upall: $incoming conflicts with $victim but does not replace it -- resolve by hand." >&2
            return 1
        end
    end

    if test (count $removable) -eq 0
        return 1
    end

    echo
    echo "Conflict blocked the upgrade. These installed packages have been"
    echo "superseded and will be removed by their replacements:"
    for pkg in $removable
        echo "  - $pkg"
    end
    echo "Retrying the upgrade..."
    echo

    # --ask=4 = answer "yes" to conflict removals for this transaction only.
    paru -Syu --noconfirm --ask=4
end

function __upall_fix_paru_conflict --description 'Retry when an AUR target drags in a conflicting package'
    # paru lists its conflicts up front and then refuses outright:
    #   :: Conflicts found:
    #       nodejs-lts-krypton: nodejs
    #   error: can not install conflicting packages with --noconfirm
    # A conflict that is really a replacement is safe to confirm (--useask).
    # Anything else is a genuine either/or -- usually one AUR package's
    # makedepend wanting to evict something already installed -- so drop that
    # one target and let the rest of the upgrade through.
    set -l in_block
    set -l superseding
    set -l culprits
    for line in $argv
        if string match -qr '^:: (Inner c|C)onflicts found:' -- $line
            set in_block 1
            continue
        end
        set -q in_block[1]
        or continue

        set -l caps (string match -rg '^\s+(\S+):\s+(.+?)\s*$' -- $line)
        if test (count $caps) -ne 2
            set -e in_block[1]
            continue
        end

        set -l incoming $caps[1]
        set -l genuine
        for victim in (string split -n ', ' -- $caps[2])
            set victim (string replace -r -- '\s*\(.*\)$' '' $victim)
            __upall_replaces $incoming $victim
            or set genuine 1
        end

        if set -q genuine[1]
            set -a culprits $incoming
        else
            set -a superseding $incoming
        end
    end

    if test (count $culprits) -eq 0 -a (count $superseding) -eq 0
        return 1
    end

    # Every conflict is a replacement: let paru confirm them with pacman's ask.
    if test (count $culprits) -eq 0
        echo
        echo "Conflict blocked the AUR upgrade; all of it is packages replacing"
        echo "what they conflict with ($superseding). Retrying..."
        echo
        paru -Syu --noconfirm --useask
        return $status
    end

    # Otherwise find which pending upgrade wants each culprit and skip it.
    set -l pending (paru -Qua 2>/dev/null | string match -rg '^(\S+) ')
    set -l ignore
    for culprit in $culprits
        set -l target (__upall_aur_target_for $culprit $pending)
        if test -z "$target"
            echo "upall: $culprit conflicts with an installed package and nothing" >&2
            echo "       pending explains why -- resolve by hand." >&2
            return 1
        end
        contains -- $target $ignore
        or set -a ignore $target
    end

    echo
    echo "An AUR upgrade wants a package that would evict something installed:"
    for culprit in $culprits
        echo "  - $culprit"
    end
    echo "Skipping the target(s) that pull it in and upgrading the rest: $ignore"
    echo

    set -a __upall_deferred $ignore
    paru -Syu --noconfirm --ignore (string join , $ignore)
end

function __upall_aur_target_for --description 'Name the pending upgrade in $argv[2..] that depends on $argv[1]'
    # Match on the conflicting package's own name and everything it provides,
    # since the dependency is usually on a virtual name (nodejs-lts).
    set -l names $argv[1]
    for item in (__upall_field $argv[1] Provides)
        set -a names (string replace -r -- '[<>=].*$' '' $item)
    end

    for target in $argv[2..-1]
        for dep in (__upall_field $target 'Depends On' 'Make Deps' 'Check Deps')
            if contains -- (string replace -r -- '[<>=].*$' '' $dep) $names
                echo $target
                return 0
            end
        end
    end
    return 1
end

function __upall_field --description 'Print the space-separated values of paru -Si fields $argv[2..] for $argv[1]'
    set -l pattern '^(?:'(string join '|' $argv[2..-1])')\s+:\s+(.*)'
    for value in (paru -Si $argv[1] 2>/dev/null | string match -rg $pattern | string split -n ' ')
        test $value = None
        or echo $value
    end
end

function __upall_replaces --description 'Test whether package $argv[1] declares Replaces on $argv[2]'
    contains -- $argv[2] (__upall_field $argv[1] Replaces)
end
