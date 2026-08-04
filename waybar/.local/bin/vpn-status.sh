#!/bin/bash
# vpn-status.sh -- feeds waybar's custom/vpn module.
#
# Requires: networkmanager jq  (installed by setup.sh's waybar package)
#
# Usage: vpn-status.sh          (the "exec" of the custom/vpn waybar module)
#
# Prints one JSON object. When no VPN is up the text is empty, which is what
# makes waybar hide the module altogether -- the design is that the glyph's mere
# presence means "protected", and its absence means "not". There is deliberately
# no dimmed/off state; the control for it lives in the network menu popup.
#
# The pango <span> is emitted here rather than set as the module's "format" so
# that an inactive VPN yields a genuinely empty label. A format wrapper would
# always produce at least the markup, and waybar would keep showing an empty box.

set -u

readonly GLYPH=$'\U000f0582'   # nf-md-vpn

name=""
while IFS=: read -r type conn; do
    [[ $type == wireguard || $type == vpn ]] || continue
    # nmcli -t escapes ':' as '\:' and '\' as '\\'
    name=$(printf '%s' "$conn" | sed -e 's/\\:/:/g' -e 's/\\\\/\\/g')
    break
done < <(nmcli -t -f TYPE,NAME connection show --active 2>/dev/null)

if [[ -z $name ]]; then
    printf '{"text":""}\n'
    exit 0
fi

jq -cn --arg t "<span size='13000'>$GLYPH </span>" --arg n "$name" \
    '{text: $t, tooltip: ("VPN: " + $n), class: "connected"}'
