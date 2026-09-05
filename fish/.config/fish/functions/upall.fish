function upall --description 'Update Arch packages via paru and Flatpaks, then refresh Cachy-Update'
    set -l failed

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
    if test (count $failed) -gt 0
        echo "Updates finished with failures: $failed" >&2
        return 1
    end
    echo "All updates complete!"
end

function __upall_sysupgrade --description 'paru -Syu, retrying once past superseded-package conflicts'
    # --noconfirm answers "no" to pacman's ":: X and Y are in conflict. Remove
    # Y?" question, so an upgrade where a package absorbs one we already have
    # dies with "unresolvable package conflicts". Record the run, and if that is
    # what happened, retry with the conflict answered "yes" (--ask=4).
    # script(1) keeps paru on a pty so colours, progress bars and the sudo /
    # fingerprint prompt all still behave.
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

    if not string match -q '*unresolvable package conflicts*' -- $out
        return $ret
    end

    set -l removable
    for line in $out
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
            return $ret
        end
    end

    if test (count $removable) -eq 0
        return $ret
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

function __upall_replaces --description 'Test whether package $argv[1] declares Replaces on $argv[2]'
    set -l replaces (paru -Si $argv[1] 2>/dev/null | string match -rg '^Replaces\s+:\s+(.*)')
    contains -- $argv[2] (string split -n ' ' -- "$replaces")
end
