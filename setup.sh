#!/usr/bin/env bash
#
# setup.sh — interactive bootstrap for this dotfiles repo.
#
# Walks an item registry (each item = some packages to install + some GNU stow
# packages to link, or a delegated installer script), asks which you want, then
# installs and stows them. Safe to re-run: package installs use --needed and
# stow uses -R (restow), so existing correct symlinks are left untouched and
# conflicting real files are backed up rather than clobbered.
#
# Usage:
#   ./setup.sh                 # interactive menu
#   ./setup.sh all             # every item, no prompt
#   ./setup.sh hyprland fish   # named items, no prompt
#   ./setup.sh --list          # print items and exit
#   ./setup.sh --dry-run ...   # show the plan without changing anything
#
# Hyprland is machine-specific: it stows hyprland-common plus exactly one of the
# per-machine profiles. The profile is auto-picked from $HOSTNAME (mini-mecha /
# oki-mecha) or asked for; override with HYPR_MACHINE=mini-mecha ./setup.sh ...

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; exit 1; }
ok()    { printf '\033[1;32m::\033[0m %s\n' "$*"; }

DRY_RUN=0

# ── Item registry ────────────────────────────────────────────────────────────
# ORDER is the canonical list. For each id:
#   LABEL[id]   one-line description shown in the menu
#   PKGS[id]    space-separated packages to install (repo or AUR)
#   STOW[id]    space-separated stow package dirs to link
#   HANDLER[id] optional function name overriding the generic install+stow

ORDER=(hyprland waybar wofi wlogout ghostty fish nautilus backgrounds avatars claude claude-skills greetd)

declare -A LABEL PKGS STOW HANDLER

LABEL[hyprland]="Hyprland compositor + full hypr environment (common + machine profile)"
PKGS[hyprland]="hyprland hyprpaper hypridle hyprlock hyprpicker grimblast-git swaync polkit-gnome gnome-keyring brightnessctl playerctl wireplumber xdg-desktop-portal-hyprland ttf-cascadia-code-nerd"
HANDLER[hyprland]=handle_hyprland

LABEL[waybar]="Waybar status bar"
PKGS[waybar]="waybar"
STOW[waybar]="waybar"

LABEL[wofi]="Wofi application launcher"
PKGS[wofi]="wofi"
STOW[wofi]="wofi"

LABEL[wlogout]="wlogout power menu (+ centered launcher script)"
PKGS[wlogout]="wlogout"
STOW[wlogout]="wlogout"

LABEL[ghostty]="Ghostty terminal"
PKGS[ghostty]="ghostty"
STOW[ghostty]="ghostty"

LABEL[fish]="Fish shell + Tide prompt (fisher plugins, keyring secrets)"
PKGS[fish]="fish fzf fnm libsecret"
STOW[fish]="fish"
HANDLER[fish]=handle_fish

LABEL[nautilus]="Nautilus file manager + GTK4 tweaks (delegates setup-nautilus.sh)"
HANDLER[nautilus]=handle_nautilus

LABEL[backgrounds]="Wallpapers (~/.config/backgrounds)"
STOW[backgrounds]="backgrounds"

LABEL[avatars]="Avatar images (~/.config/avatars)"
STOW[avatars]="avatars"

LABEL[claude]="Claude Code config (~/.claude/settings.json + statusline.sh)"
STOW[claude]="claude"

LABEL[claude-skills]="Claude Code skills plugin (delegates setup-claude-skills.sh)"
HANDLER[claude-skills]=handle_claude_skills

LABEL[greetd]="greetd + ReGreet login manager — system-level (delegates installer)"
HANDLER[greetd]=handle_greetd

# ── Package + stow primitives ────────────────────────────────────────────────
AUR_HELPER=""
for h in paru yay; do command -v "$h" >/dev/null 2>&1 && { AUR_HELPER="$h"; break; }; done

pkg_install() {
    [[ $# -eq 0 ]] && return 0
    local missing=()
    for p in "$@"; do
        pacman -Qi "$p" &>/dev/null || missing+=("$p")
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        info "packages already installed: $*"
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        info "[dry-run] would install: ${missing[*]}"
        return 0
    fi
    info "installing: ${missing[*]}"
    if [[ -n "$AUR_HELPER" ]]; then
        "$AUR_HELPER" -S --needed "${missing[@]}"
    else
        warn "no AUR helper (paru/yay) found — using pacman; AUR packages will fail"
        sudo pacman -S --needed "${missing[@]}"
    fi
}

# Stow a package, backing up any genuinely-foreign REAL files that would
# conflict. A file is foreign only if it is not a symlink AND does not already
# resolve back into this repo — the second check is critical: when a package is
# already stowed via stow's directory folding, $HOME/.../file is a real file
# reached THROUGH a parent dir symlink into the repo, and moving it would
# corrupt the repo. Such files resolve under $SCRIPT_DIR and are left alone.
safe_stow() {
    local pkg="$1"
    [[ -d "$SCRIPT_DIR/$pkg" ]] || { warn "no stow package '$pkg' — skipping"; return; }
    if [[ $DRY_RUN -eq 1 ]]; then
        info "[dry-run] would stow: $pkg"
        return 0
    fi
    local f rel target bak
    while IFS= read -r f; do
        rel="${f#"$SCRIPT_DIR/$pkg/"}"
        target="$HOME/$rel"
        [[ -e "$target" && ! -L "$target" ]] || continue
        # Already owned by this repo (folded symlink in an ancestor)? Leave it.
        case "$(readlink -f "$target")" in "$SCRIPT_DIR"/*) continue ;; esac
        bak="$target.pre-stow.$(date +%Y%m%d%H%M%S)"
        warn "backing up existing $target -> $bak"
        mkdir -p "$(dirname "$bak")"
        mv "$target" "$bak"
    done < <(find "$SCRIPT_DIR/$pkg" -type f)
    if stow -R -t "$HOME" -d "$SCRIPT_DIR" "$pkg"; then
        ok "stowed $pkg"
    else
        warn "stow reported a conflict for '$pkg' — resolve the file(s) above and re-run"
    fi
}

delegate() {
    local script="$1"
    [[ -x "$SCRIPT_DIR/$script" ]] || { warn "$script not found/executable — skipping"; return; }
    if [[ $DRY_RUN -eq 1 ]]; then
        info "[dry-run] would run: ./$script"
        return 0
    fi
    info "running ./$script ..."
    "$SCRIPT_DIR/$script"
}

# ── Per-item handlers ────────────────────────────────────────────────────────
handle_generic() {
    local id="$1"
    pkg_install ${PKGS[$id]:-}
    local s
    for s in ${STOW[$id]:-}; do safe_stow "$s"; done
}

handle_hyprland() {
    pkg_install ${PKGS[hyprland]}
    safe_stow hyprland-common

    local machine="${HYPR_MACHINE:-}"
    if [[ -z "$machine" ]]; then
        case "$(hostnamectl --static 2>/dev/null || hostname 2>/dev/null)" in
            *mini-mecha*) machine="mini-mecha" ;;
            *oki-mecha*)  machine="oki-mecha" ;;
        esac
    fi
    if [[ -z "$machine" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            info "[dry-run] would prompt for machine profile (mini-mecha/oki-mecha)"
            return
        fi
        echo "Which machine profile?"
        select machine in mini-mecha oki-mecha; do [[ -n "$machine" ]] && break; done
    fi
    info "machine profile: $machine"
    safe_stow "hyprland-$machine"
}

handle_fish() {
    handle_generic fish
    command -v fish >/dev/null 2>&1 || { warn "fish missing — skipping plugin bootstrap"; return; }
    if [[ $DRY_RUN -eq 1 ]]; then
        info "[dry-run] would bootstrap fisher + 'fisher update' (Tide, nvm)"
        return
    fi
    info "bootstrapping fisher + plugins from fish_plugins (Tide, nvm)..."
    fish -c 'functions -q fisher; or curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source; and fisher install jorgebucaran/fisher' \
        || warn "fisher bootstrap hiccup"
    fish -c 'fisher update' \
        || warn "fisher update hiccup — run 'fisher update' in fish manually (Tide may ask config questions once)"
}

handle_nautilus()      { delegate setup-nautilus.sh; }
handle_claude_skills() { delegate setup-claude-skills.sh; }
handle_greetd()        { delegate install-greetd-regreet.sh; }

run_item() {
    local id="$1"
    printf '\n\033[1;35m==>\033[0m %s — %s\n' "$id" "${LABEL[$id]}"
    if [[ -n "${HANDLER[$id]:-}" ]]; then
        "${HANDLER[$id]}"
    else
        handle_generic "$id"
    fi
}

# ── Menu / selection ─────────────────────────────────────────────────────────
print_list() {
    local i=1 id
    for id in "${ORDER[@]}"; do
        printf '  \033[1m%2d\033[0m  %-14s %s\n' "$i" "$id" "${LABEL[$id]}"
        ((i++))
    done
}

# Resolve a token (number or id) to an item id; echoes "" if invalid.
resolve_token() {
    local tok="$1" id
    if [[ "$tok" =~ ^[0-9]+$ ]]; then
        (( tok >= 1 && tok <= ${#ORDER[@]} )) && echo "${ORDER[tok-1]}"
        return
    fi
    for id in "${ORDER[@]}"; do [[ "$id" == "$tok" ]] && { echo "$id"; return; }; done
}

main() {
    command -v pacman >/dev/null 2>&1 || error "this script targets Arch-based distros (pacman not found)"

    # Parse flags.
    local args=()
    for a in "$@"; do
        case "$a" in
            --dry-run) DRY_RUN=1 ;;
            --list)    print_list; exit 0 ;;
            -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
            *)         args+=("$a") ;;
        esac
    done

    # Prerequisite: stow itself.
    command -v stow >/dev/null 2>&1 || pkg_install stow

    # Build the selection.
    local selected=() id tok
    if [[ ${#args[@]} -gt 0 ]]; then
        if [[ "${args[0]}" == "all" ]]; then
            selected=("${ORDER[@]}")
        else
            for tok in "${args[@]}"; do
                id="$(resolve_token "$tok")"
                [[ -n "$id" ]] && selected+=("$id") || warn "unknown item: $tok"
            done
        fi
    else
        echo "This dotfiles repo provides:"
        print_list
        echo
        read -rp "Select items (numbers/names, space-separated, or 'all'): " line
        if [[ "$line" == "all" ]]; then
            selected=("${ORDER[@]}")
        else
            for tok in $line; do
                id="$(resolve_token "$tok")"
                [[ -n "$id" ]] && selected+=("$id") || warn "unknown item: $tok"
            done
        fi
    fi

    [[ ${#selected[@]} -eq 0 ]] && error "nothing selected"

    # Dedup while preserving order.
    local uniq=() seen=" "
    for id in "${selected[@]}"; do
        [[ "$seen" == *" $id "* ]] || { uniq+=("$id"); seen+="$id "; }
    done
    selected=("${uniq[@]}")

    echo
    [[ $DRY_RUN -eq 1 ]] && warn "DRY RUN — no changes will be made"
    info "will set up: ${selected[*]}"
    if [[ $DRY_RUN -eq 0 ]]; then
        read -rp "Proceed? [Y/n] " ans
        [[ "${ans,,}" == "n" ]] && error "aborted"
    fi

    for id in "${selected[@]}"; do run_item "$id"; done

    echo
    ok "done: ${selected[*]}"
    if [[ " ${selected[*]} " == *" hyprland "* ]]; then
        warn "reload Hyprland (hyprctl reload) or re-login to apply compositor changes"
    fi
    return 0
}

main "$@"
