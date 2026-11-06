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
    readonly property string networkCaption: !network ? "Offline" : network.kind === "ethernet" ? "Wired" : network.label
    readonly property string networkIcon: vpn ? "󰒃" : !network || network.kind === "offline" ? "󰤭"
        : network.kind === "wifi" ? "󰤨" : network.kind === "ethernet" ? "󰈀" : "󰛳"
    spacing: 4

    RowLayout {
        objectName: "sound-group"
        spacing: 2
        ActionButton {
            objectName: "volume-control"
            horizontalPadding: Theme.barButtonPadding
            tabularDigits: true
            text: root.audio ? (root.audio.muted ? "󰝟  Muted" : "󰕾  " + root.audio.percent + "%") : "󰕾  —"
            hint: "Volume · scroll to adjust, right-click for advanced settings"
            selected: shell.panel === "audio"
            textColor: root.audio && root.audio.muted ? Theme.muted : Theme.text
            onClicked: shell.open("audio", root.output)
            TapHandler { acceptedButtons: Qt.RightButton; onTapped: shell.send("open", { target: "audio" }) }
            VolumeWheel { shell: root.shell }
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
                + (root.network.signal !== null ? " · " + root.network.signal + "% signal" : "")
                + (root.network.address ? "\n" + root.network.address : "")
                + (root.vpn ? "\nVPN protected · " + root.network.vpn : "\nVPN not connected")
                + "\nOpen connectivity settings" : "Network unavailable · open connectivity settings"
            selected: shell.panel === "network"
            Accessible.name: "Network: " + root.networkCaption + (root.vpn ? ", VPN protected" : ", VPN not connected")
            onClicked: shell.open("network", root.output)
        }
    }

    RowLayout {
        objectName: "energy-group"
        spacing: 2
        ActionButton {
            objectName: "keep-awake-control"
            horizontalPadding: Theme.barButtonPadding
            text: !shell.state.awake || shell.state.awake.class === "error" ? "!" : root.awake ? "󰅶" : "󰛊"
            textColor: Theme.muted
            selected: root.awake
            hint: shell.state.awake ? shell.state.awake.tooltip : "Keep-awake status unavailable"
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
            Layout.leftMargin: 2
            Layout.rightMargin: 2
        }
    }

    ActionButton {
        objectName: "notifications-control"
        horizontalPadding: Theme.barButtonPadding
        text: root.dnd ? "󰂛" : root.notificationCount > 0 ? "󰂚" : "󰂜"
        textColor: Theme.muted
        hint: (root.dnd ? "Do not disturb is on" : "Notifications")
            + (root.notificationCount ? " · " + root.notificationCount + " in history" : " · All caught up")
            + "\nRight-click to toggle do not disturb"
        selected: shell.panel === "notifications" || root.dnd || root.notificationCount > 0
        onClicked: shell.open("notifications", root.output)
        TapHandler {
            acceptedButtons: Qt.RightButton
            onTapped: if (shell.notificationService) shell.notificationService.dnd = !shell.notificationService.dnd
        }
    }
    ActionButton {
        objectName: "clock-control"
        horizontalPadding: Theme.barButtonPadding
        tabularDigits: true
        text: Qt.formatDateTime(root.dateTime, root.compact ? "HH:mm" : "ddd d MMM  ·  HH:mm")
        hint: "Calendar"
        selected: shell.panel === "calendar"
        onClicked: shell.open("calendar", root.output)
    }
    Rectangle { width: 1; height: 16; color: Theme.line; Layout.leftMargin: 2; Layout.rightMargin: 2 }
    ActionButton {
        objectName: "power-control"
        horizontalPadding: Theme.barButtonPadding
        text: "⏻"
        textColor: Theme.muted
        hint: "Session & power · Super+Delete"
        selected: shell.panel === "power"
        onClicked: shell.open("power", root.output)
    }
}
