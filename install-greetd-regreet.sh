#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREETD_SRC="$SCRIPT_DIR/greetd-setup/etc/greetd"
GREETD_DEST="/etc/greetd"
PAM_SRC="$SCRIPT_DIR/greetd-setup/etc/pam.d/greetd-greeter"
PAM_DEST="/etc/pam.d/greetd-greeter"
BG_SRC="$SCRIPT_DIR/backgrounds/.config/backgrounds/tolkien/balrog.jpg"
BG_DEST="/usr/share/backgrounds/greeter-tolkien.jpg"
AVATAR_SRC="$SCRIPT_DIR/greetd-setup/greeter-avatar.png"
AVATAR_DEST="/usr/share/backgrounds/greeter-avatar.png"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*"; exit 1; }

# ── Dependency check ──
check_deps() {
    local missing=()
    command -v greetd >/dev/null 2>&1   || missing+=("greetd")
    command -v regreet >/dev/null 2>&1   || missing+=("greetd-regreet")
    command -v start-hyprland >/dev/null 2>&1 || missing+=("hyprland")
    command -v Hyprland >/dev/null 2>&1 || missing+=("hyprland")
    command -v dbus-run-session >/dev/null 2>&1 || missing+=("dbus")

    local fonts
    fonts="$(fc-list : family)"
    if ! echo "$fonts" | grep -qi "CaskaydiaCove"; then
        missing+=("ttf-cascadia-code-nerd")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Missing dependencies: ${missing[*]}"
        read -rp "Install missing packages with pacman? [Y/n] " ans
        if [[ "${ans,,}" != "n" ]]; then
            sudo pacman -S --needed "${missing[@]}"
        else
            error "Cannot continue without dependencies"
        fi
    fi
    info "All dependencies satisfied"
}

# Validate before overwriting a working greeter. File existence alone does not
# catch an old hyprlang config being fed to Hyprland's Lua parser.
validate_source_config() {
    grep -Fxq 'command = "dbus-run-session start-hyprland -- -c /etc/greetd/hyprland.lua"' \
        "$GREETD_SRC/config.toml" || error "greetd must launch /etc/greetd/hyprland.lua"
    Hyprland --verify-config -c "$GREETD_SRC/hyprland.lua" \
        || error "Greeter Lua config failed validation; existing configuration was not changed"
}

# ── Install greeter configs ──
install_configs() {
    info "Installing greetd + ReGreet configuration..."

    # Preserve local settings, and install the launch command LAST so it cannot
    # point at a Lua file that has not yet been copied. Back up only changed files.
    # Secure the directory BEFORE touching files: a greeter-writable directory
    # permits replacement of root-owned config.toml regardless of its file mode.
    sudo install -d -o root -g root -m 755 "$GREETD_DEST"
    local file mode stamp
    stamp="$(date +%Y%m%d%H%M%S%N)"
    for file in hyprland.lua regreet.toml regreet.css config.toml; do
        if sudo test -e "$GREETD_DEST/$file" && \
            ! sudo cmp -s "$GREETD_SRC/$file" "$GREETD_DEST/$file"; then
            sudo cp -a "$GREETD_DEST/$file" "$GREETD_DEST/$file.pre-lua.$stamp"
        fi
        mode=644
        [[ "$file" != config.toml ]] || mode=640
        sudo install -o root -g root -m "$mode" "$GREETD_SRC/$file" "$GREETD_DEST/$file"
    done
    if [[ -f "$GREETD_DEST/hyprland.conf" ]]; then
        warn "Legacy hyprland.conf is unused; leaving it in place for recovery"
    fi
    info "Config files installed to $GREETD_DEST"

    # PAM config for greeter session (required — without this PAM denies the greeter)
    if [[ ! -f "$PAM_DEST" ]]; then
        sudo cp "$PAM_SRC" "$PAM_DEST"
        sudo chmod 644 "$PAM_DEST"
        info "PAM config installed to $PAM_DEST"
    else
        info "PAM config already exists at $PAM_DEST — skipping"
    fi

    # Background image
    if [[ -f "$BG_SRC" ]]; then
        sudo mkdir -p "$(dirname "$BG_DEST")"
        sudo cp "$BG_SRC" "$BG_DEST"
        sudo chmod 644 "$BG_DEST"
        info "Background image installed to $BG_DEST"
    else
        warn "Background image not found at $BG_SRC"
        warn "You can manually place a background at $BG_DEST"
    fi

    # User avatar (regreet.css paints it onto the login form — ReGreet has no
    # avatar widget, so we ship a pre-rendered circular image and CSS it in).
    # Must live on a system path: the greeter runs as 'greeter' and can't read
    # your home directory.
    if [[ -f "$AVATAR_SRC" ]]; then
        sudo mkdir -p "$(dirname "$AVATAR_DEST")"
        sudo cp "$AVATAR_SRC" "$AVATAR_DEST"
        sudo chmod 644 "$AVATAR_DEST"
        info "Avatar image installed to $AVATAR_DEST"
    else
        warn "Avatar image not found at $AVATAR_SRC"
    fi
}

# ── Set up greeter user and directories ──
setup_greeter_user() {
    info "Setting up greeter user and directories..."

    # Ensure the greeter user exists (greetd package usually creates it)
    if ! id -u greeter &>/dev/null; then
        warn "'greeter' user not found — creating it"
        sudo useradd -r -s /usr/bin/nologin -d / greeter
    fi

    # Static configuration stays root-owned. Only state and logs are writable
    # by greeter; never recursively chown /etc/greetd to the service user.
    sudo install -d -o root -g root -m 755 "$GREETD_DEST"

    # ReGreet state/log directories (systemd-tmpfiles usually handles this)
    sudo mkdir -p /var/lib/regreet /var/log/regreet
    sudo chown greeter:greeter /var/lib/regreet /var/log/regreet
    sudo chmod 750 /var/lib/regreet /var/log/regreet
    info "Greeter user and directories configured"
}

# ── Enable greetd service, disable previous DM ──
enable_greetd() {
    if ! systemctl list-unit-files greetd.service 2>/dev/null | grep -q greetd; then
        error "greetd.service not found — is the greetd package installed?"
    fi

    if systemctl is-enabled --quiet greetd 2>/dev/null; then
        info "greetd is already enabled"
        return
    fi

    local dm_symlink="/etc/systemd/system/display-manager.service"
    if [[ -L "$dm_symlink" ]]; then
        local current_dm_target current_dm
        current_dm_target="$(readlink "$dm_symlink")"
        current_dm="$(basename "$current_dm_target" .service)"

        if [[ "$current_dm" == "greetd" ]] || [[ "$current_dm_target" == *"greetd"* ]]; then
            info "greetd is already the active display manager"
            return
        fi

        # Save previous DM for recovery
        echo "$current_dm" | sudo tee "$GREETD_DEST/.previous-dm" >/dev/null

        warn "Current display manager: $current_dm"
        echo ""
        warn "╔══════════════════════════════════════════════════════════════╗"
        warn "║  RECOVERY: if you get a blank screen after reboot:         ║"
        warn "║  1. Press Ctrl+Alt+F2 to switch to a TTY                   ║"
        warn "║  2. Log in with your username and password                  ║"
        warn "║  3. Run:                                                    ║"
        warn "║     sudo systemctl disable greetd                           ║"
        warn "║     sudo systemctl enable $current_dm$(printf '%*s' $((26 - ${#current_dm})) '')║"
        warn "║     sudo reboot                                            ║"
        warn "╚══════════════════════════════════════════════════════════════╝"
        echo ""

        read -rp "Disable $current_dm and enable greetd instead? [Y/n] " ans
        if [[ "${ans,,}" != "n" ]]; then
            info "Disabling $current_dm..."
            sudo systemctl disable "$current_dm"
            info "Enabling greetd..."
            sudo systemctl enable greetd
        else
            warn "Skipping — greetd will not be enabled"
        fi
    else
        info "No display manager currently enabled"
        info "Enabling greetd service..."
        sudo systemctl enable greetd
    fi
}

# ── Verify configuration ──
verify_config() {
    info "Verifying greetd + ReGreet configuration..."
    local ok=true

    [[ "$(stat -c '%u:%g:%a' "$GREETD_DEST")" == '0:0:755' ]] \
        || error "greetd configuration directory must be root:root 755"

    if [[ ! -f "$GREETD_DEST/config.toml" ]]; then
        warn "greetd config not found at $GREETD_DEST/config.toml"
        ok=false
    fi

    if [[ ! -f "$GREETD_DEST/regreet.toml" ]]; then
        warn "ReGreet config not found at $GREETD_DEST/regreet.toml"
        ok=false
    fi

    if [[ ! -f "$GREETD_DEST/regreet.css" ]]; then
        warn "ReGreet CSS not found at $GREETD_DEST/regreet.css"
        ok=false
    fi

    if [[ ! -f "$GREETD_DEST/hyprland.lua" ]]; then
        warn "Hyprland greeter config not found at $GREETD_DEST/hyprland.lua"
        ok=false
    fi

    if ! sudo grep -Fxq 'command = "dbus-run-session start-hyprland -- -c /etc/greetd/hyprland.lua"' \
        "$GREETD_DEST/config.toml"; then
        error "Installed greetd command does not use the Lua greeter config; greetd will not be enabled"
    fi
    if ! Hyprland --verify-config -c "$GREETD_DEST/hyprland.lua"; then
        error "Installed Hyprland greeter config failed validation; greetd will not be enabled"
    fi

    if [[ ! -f "$PAM_DEST" ]]; then
        warn "PAM config for greetd-greeter not found at $PAM_DEST"
        ok=false
    fi

    if [[ ! -f "$BG_DEST" ]]; then
        warn "Background image not found at $BG_DEST"
        ok=false
    fi

    if [[ ! -f "$AVATAR_DEST" ]]; then
        warn "Avatar image not found at $AVATAR_DEST"
        ok=false
    fi

    if $ok; then
        info "Configuration looks good"
    else
        warn "There may be issues — check warnings above"
    fi
}

# ── Main ──
main() {
    info "Catppuccin Tolkien — greetd + ReGreet Installer"
    echo ""
    check_deps
    validate_source_config
    install_configs
    setup_greeter_user
    verify_config
    enable_greetd
    echo ""
    info "Done! greetd + ReGreet is configured."
    if [[ -f "$GREETD_DEST/.previous-dm" ]]; then
        local prev_dm
        prev_dm="$(cat "$GREETD_DEST/.previous-dm")"
        info "Previous DM saved. To revert: sudo systemctl disable greetd && sudo systemctl enable $prev_dm && sudo reboot"
    fi
    info "Reboot to see your new greeter."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
