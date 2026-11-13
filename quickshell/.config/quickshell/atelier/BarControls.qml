import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    required property var shell
    required property var output
    property bool compact: false
    property date dateTime: new Date()
    readonly property var audio: shell.state.audio
    readonly property var network: shell.state.network
    readonly property var battery: (shell.state.battery || [])[0] || null
    readonly property bool awake: !!shell.state.awake && shell.state.awake.class === "activated"
    readonly property bool vpn: !!network && !!network.vpn
    readonly property bool dnd: !!shell.notificationService && shell.notificationService.dnd
    readonly property int notificationCount: shell.notificationService ? shell.notificationService.history.length : 0
    readonly property var services: shell.desktopServices || null
    readonly property string networkCaption: !network ? "Offline" : network.kind === "ethernet" ? "Wired" : network.label
    readonly property string networkIcon: vpn ? "󰒃" : !network || network.kind === "offline" ? "󰤭"
        : network.kind === "wifi" ? "󰤨" : network.kind === "ethernet" ? "󰈀" : "󰛳"
    spacing: 4

    ActionButton {
        objectName: "media-control"
        visible: !!root.services && root.services.players.length > 0
        horizontalPadding: Theme.barButtonPadding
        text: "󰎆"
        Accessible.name: "Media controls"
        hintShortcut: "Super+Ctrl+M"
        hint: root.services ? root.services.players.map(p => (p.trackTitle || p.identity) + (p.trackArtist ? "\n" + p.trackArtist : "")).join("\n\n") : "Media"
        selected: shell.panel === "media"
        onClicked: shell.open("media", root.output)
    }
    ActionButton {
        objectName: "tray-control"
        visible: !!root.services && root.services.trayItems.length > 0
        horizontalPadding: Theme.barButtonPadding
        text: "󰀻"
        Accessible.name: "System tray"
        hintShortcut: "Super+Ctrl+T"
        hint: "System\u00a0tray"
        selected: shell.panel === "tray"
        onClicked: shell.open("tray", root.output)
    }

    RowLayout {
        objectName: "energy-group"
        spacing: root.spacing
        ActionButton {
            objectName: "keep-awake-control"
            horizontalPadding: Theme.barButtonPadding
            text: !shell.state.awake || shell.state.awake.class === "error" ? "!" : root.awake ? "󰅶" : "󰛊"
            textColor: Theme.muted
            selected: root.awake
            accessibleToggle: true
            Accessible.name: "Keep awake"
            hint: shell.state.awake ? shell.state.awake.tooltip : "Keep\u00a0awake\nStatus\u00a0unavailable"
            enabled: !!shell.state.awake && shell.state.awake.class !== "error"
            onClicked: shell.send("awake")
        }
        Label {
            objectName: "battery-status"
            visible: !!root.battery
            text: root.battery ? (root.battery.status === "Charging" ? "󰂄 " : "󰁹 ") + root.battery.percent + "%" : ""
            font.features: ({ "tnum": 1 })
            color: !root.battery ? Theme.muted : root.battery.percent <= 15 ? Theme.danger
                : root.battery.percent <= 30 ? Theme.accent : root.battery.status === "Charging" ? Theme.good : Theme.muted
            Layout.leftMargin: Theme.barButtonPadding
            Layout.rightMargin: Theme.barButtonPadding
        }
    }

    RowLayout {
        objectName: "connectivity-group"
        spacing: 2
        ActionButton {
            id: networkButton
            objectName: "network-control"
            horizontalPadding: Theme.barButtonPadding
            text: root.networkIcon
            textColor: root.vpn ? Theme.good : root.network && root.network.kind !== "offline" ? Theme.text : Theme.muted
            hint: root.network ? root.network.label
                + (root.network.signal !== null ? "\n" + root.network.signal + "%\u00a0signal" : "")
                + (root.network.address ? "\n" + root.network.address : "")
                + (root.vpn ? "\nVPN\u00a0protected\n" + root.network.vpn : "\nVPN not\u00a0connected")
                + "\nOpen connectivity\u00a0settings" : "Network\u00a0unavailable\nOpen connectivity\u00a0settings"
            selected: shell.panel === "network"
            Accessible.name: "Network: " + root.networkCaption + (root.vpn ? ", VPN protected" : ", VPN not connected")
            hintShortcut: "Super+Ctrl+N"
            onClicked: shell.open("network", root.output)
        }
    }
    RowLayout {
        objectName: "sound-group"
        spacing: 2
        ActionButton {
            objectName: "volume-control"
            horizontalPadding: Theme.barButtonPadding
            tabularDigits: true
            Accessible.name: root.audio ? (root.audio.muted ? "Output muted" : "Output volume " + root.audio.percent + " percent") : "Audio unavailable"
            text: root.audio ? (root.audio.muted ? "󰝟  Muted" : "󰕾  " + root.audio.percent + "%") : "󰕾  —"
            hint: "Volume\nScroll to adjust\nRight-click for audio\u00a0settings"
            hintShortcut: "Super+Ctrl+A"
            selected: shell.panel === "audio"
            textColor: root.audio && root.audio.muted ? Theme.muted : Theme.text
            onClicked: shell.open("audio", root.output)
            TapHandler { acceptedButtons: Qt.RightButton; onTapped: shell.send("open", { target: "audio" }) }
            VolumeWheel { shell: root.shell }
        }
    }
    ActionButton {
        objectName: "clock-control"
        horizontalPadding: Theme.barButtonPadding
        tabularDigits: true
        text: Qt.formatDateTime(root.dateTime, root.compact ? "HH:mm" : "ddd d MMM\u2003\u2003HH:mm")
        hint: "Calendar"
        Accessible.name: "Calendar, " + Qt.formatDateTime(root.dateTime, "dddd d MMMM HH:mm")
        hintShortcut: "Super+Ctrl+C"
        selected: shell.panel === "calendar"
        onClicked: shell.open("calendar", root.output)
    }
    ActionButton {
        objectName: "notifications-control"
        horizontalPadding: Theme.barButtonPadding
        text: root.dnd ? "󰂛" : root.notificationCount > 0 ? "󰂚" : "󰂜"
        textColor: Theme.muted
        Accessible.name: "Notifications" + (root.notificationCount ? ", " + root.notificationCount + " in history" : "")
        hint: "Notifications"
            + (root.notificationCount ? "\n" + root.notificationCount + "\u00a0in history" : "\nAll caught\u00a0up")
            + "\nDo\u00a0not\u00a0disturb: " + (root.dnd ? "on" : "off")
            + "\nRight-click to turn " + (root.dnd ? "off" : "on")
        selected: shell.panel === "notifications" || root.dnd || root.notificationCount > 0
        hintShortcut: "Super+Ctrl+H"
        onClicked: shell.open("notifications", root.output)
        TapHandler {
            acceptedButtons: Qt.RightButton
            onTapped: if (shell.notificationService) shell.notificationService.dnd = !shell.notificationService.dnd
        }
    }
    Rectangle { width: 1; height: 16; color: Theme.line; Layout.leftMargin: 2; Layout.rightMargin: 2 }
    ActionButton {
        objectName: "power-control"
        horizontalPadding: Theme.barButtonPadding
        text: "⏻"
        Accessible.name: "Session and power"
        textColor: Theme.muted
        hint: "Session\u00a0&\u00a0power"
        hintShortcut: "Super+Delete"
        selected: shell.panel === "power"
        onClicked: shell.open("power", root.output)
    }
}
