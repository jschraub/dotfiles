function upall --description 'Update repository packages, AUR packages, Flatpaks, and Cachy-Update'
    set -l failed
    set -g __upall_deferred
    set -e __upall_last_log

    echo "Starting repository updates..."
    __upall_repo_upgrade
    or set -a failed repository

    if test (count $failed) -eq 0
        echo "---"
        echo "Starting AUR updates..."
        __upall_aur_upgrade
        or set -a failed AUR
    end

    echo "---"
    echo "Starting Flatpak updates..."
    flatpak update -y
    or set -a failed flatpak

    echo "---"
    # paru and Flatpak do not update Cachy-Update's cached state, so refresh it
    # now rather than leaving its notification stale until the daily check.
    echo "Refreshing Cachy-Update status..."
    arch-update --check

    set -l deferred $__upall_deferred
    set -e __upall_deferred
    set -e __upall_last_log

    echo "---"
    if test (count $failed) -gt 0
        echo "Updates finished with failures: $failed" >&2
        return 1
    end
    if test (count $deferred) -gt 0
        echo "All possible updates complete. Deferred AUR packages (retried next run): $deferred" >&2
        return 0
    end
    echo "All updates complete!"
end

function __upall_repo_upgrade --description 'Upgrade repository packages and retry known safe replacements'
    __upall_run repo paru --repo -Syu --noconfirm --nouseask
    and return 0

    set -l log $__upall_last_log
    if __upall_only_replacement_conflicts "$log"
        echo "Repository replacements blocked the upgrade. Retrying..."
        rm -f "$log"
        __upall_run repo-retry paru --repo -Syu --noconfirm --ask=4
        and return 0
    end

    __upall_report_failure repository "$log"
    return 1
end

function __upall_aur_upgrade --description 'Upgrade AUR packages individually so one failure does not block the rest'
    set -l pending (paru --aur -Qua --quiet)
    or begin
        echo "upall: could not determine pending AUR updates." >&2
        return 1
    end

    for package in $pending
        __upall_aur_package "$package"
        or set -a __upall_deferred "$package"
    end
    return 0
end

function __upall_aur_package --description 'Upgrade one AUR package and defer it if it cannot be updated safely'
    __upall_run "aur-$argv[1]" paru --aur -S --needed --noconfirm --nouseask --skipreview "$argv[1]"
    and return 0

    set -l log $__upall_last_log
    if __upall_only_replacement_conflicts "$log"
        echo "AUR package $argv[1] needs a declared replacement. Retrying..."
        rm -f "$log"
        __upall_run "aur-$argv[1]-retry" paru --aur -S --needed --noconfirm --useask --skipreview "$argv[1]"
        and return 0
        set log $__upall_last_log
    end

    __upall_report_failure "AUR package $argv[1] (deferred)" "$log"
    return 1
end

function __upall_run --description 'Run a package command on a pty and retain its transcript only when it fails'
    set -l label $argv[1]
    set -e argv[1]
    set -l state_home "$XDG_STATE_HOME"
    test -n "$state_home"
    or set state_home "$HOME/.local/state"
    set -l log_dir "$state_home/upall"

    mkdir -p "$log_dir"
    or begin
        echo "upall: cannot create log directory: $log_dir" >&2
        return 1
    end
    set -l log (mktemp "$log_dir/$label-XXXXXX.log")
    or begin
        echo "upall: cannot create an update log in: $log_dir" >&2
        return 1
    end

    script -qef "$log" -- $argv
    set -l result $status
    if test $result -eq 0
        rm -f "$log"
        return 0
    end

    set -g __upall_last_log "$log"
    return $result
end

function __upall_report_failure --description 'Point to the retained output for a failed updater command'
    if test -n "$argv[2]"
        echo "upall: $argv[1] failed; full output retained at $argv[2]" >&2
    else
        echo "upall: $argv[1] failed." >&2
    end
end

function __upall_only_replacement_conflicts --description 'Test whether every reported conflict is a declared package replacement'
    test -r "$argv[1]"
    or return 1

    set -l in_aur_block
    set -l found
    # Strip pty control sequences before parsing pacman and paru conflict lines.
    for line in (sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g; s/\r//g' "$argv[1]")
        set -l pacman_conflict (string match -rg '^:: (\S+) and (\S+) are in conflict.*[Rr]emove ([^?]+)\?' -- $line)
        if test (count $pacman_conflict) -eq 3
            set -l victim $pacman_conflict[3]
            set -l incoming (string replace -r -- '-[^-]+-[^-]+$' '' $pacman_conflict[1])
            test "$incoming" != "$victim"
            or set incoming (string replace -r -- '-[^-]+-[^-]+$' '' $pacman_conflict[2])
            __upall_replaces "$incoming" "$victim"
            or return 1
            set found 1
            continue
        end

        if string match -qr '^:: (Inner c|C)onflicts found:' -- $line
            set in_aur_block 1
            continue
        end
        set -q in_aur_block[1]
        or continue

        set -l aur_conflict (string match -rg '^\s+(\S+):\s+(.+?)\s*$' -- $line)
        if test (count $aur_conflict) -ne 2
            set -e in_aur_block[1]
            continue
        end

        for victim in (string split -n ', ' -- $aur_conflict[2])
            set victim (string replace -r -- '\s*\(.*\)$' '' $victim)
            __upall_replaces "$aur_conflict[1]" "$victim"
            or return 1
        end
        set found 1
    end

    set -q found[1]
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
