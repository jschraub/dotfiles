import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import "Focus.js" as Focus

ColumnLayout {
    id: root
    required property var shell
    implicitHeight: 560
    spacing: 12
    property var target: null
    property var net: shell.state.network
    property var bluetooth: shell.state.bluetooth
    property real panelHeight: Math.min(650, Math.max(320,
        328 + (net && net.wifi ? shell.networks.items.length * 62 : 0)
        + (target ? 150 : 0) + (shell.networks.proton ? 40 : shell.networks.vpns.length * 38)
        + (net && ["portal", "limited"].includes(net.connectivity) ? 38 : 0)))
    function connect(row) {
        if (row.connected || shell.networkBusy) return;
        if (row.security && !row.uuid) { target = row; password.forceActiveFocus(); }
        else submit(row, "");
    }
    function submit(row, secret) {
        shell.networkBusy = true;
        shell.message = "Connecting to " + row.ssid + "…";
        shell.send("connect", { ssid: row.ssid, password: secret });
        password.text = "";
        target = null;
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "Connectivity"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        ActionButton {
            objectName: "wifi-toggle"
            text: root.net && root.net.wifi ? "Wi-Fi on" : "Wi-Fi off"
            selected: !!root.net && root.net.wifi
            accessibleToggle: true
            Accessible.name: "Wi-Fi"
            enabled: !shell.networkBusy && !!root.net
            onClicked: { shell.networkBusy = true; shell.send("wifi", { enabled: !root.net.wifi }); }
        }
    }
    Label { Layout.fillWidth: true; text: root.net ? root.net.label + (root.net.vpn ? "\u2003\u2003VPN protected" : "") : "NetworkManager unavailable"; color: Theme.muted }
    Label { visible: !!root.net && !!root.net.address; Layout.fillWidth: true; text: root.net ? root.net.address : ""; font.family: Theme.mono; font.pixelSize: 11; color: Theme.muted }
    RowLayout {
        ActionButton { text: "↻  Rescan"; enabled: !shell.networkBusy && !!root.net && root.net.wifi; onClicked: { shell.networkBusy = true; shell.send("rescan"); } }
        Item { Layout.fillWidth: true }
        ActionButton { text: "Advanced ↗"; onClicked: { shell.send("open", { target: "network" }); shell.close(); } }
    }
    Label { text: shell.networkBusy ? "WORKING…" : "AVAILABLE NETWORKS"; font.pixelSize: 10; font.letterSpacing: 1.3; color: Theme.accent }
    ListView {
        id: list
        Layout.fillWidth: true; Layout.fillHeight: true
        model: root.net && root.net.wifi ? shell.networks.items : []
        clip: true; spacing: 4
        Controls.ScrollBar.vertical: ScrollHandle {}
        delegate: Controls.AbstractButton {
            id: row
            required property var modelData
            required property int index
            objectName: "network-" + index
            width: list.width; height: 58
            hoverEnabled: true; enabled: !shell.networkBusy
            focusPolicy: Qt.StrongFocus
            Accessible.name: modelData.ssid
            Accessible.description: (modelData.connected ? "Connected" : modelData.security || "Open network") + ", signal " + modelData.signal + " percent"
            Keys.onDownPressed: Focus.row(list, index + 1)
            Keys.onUpPressed: Focus.row(list, index - 1)
            onClicked: root.connect(modelData)
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) root.connect(modelData); }
            Keys.onEnterPressed: event => { if (!event.isAutoRepeat) root.connect(modelData); }
            background: Rectangle {
                radius: 8; color: row.hovered || row.visualFocus || row.modelData.connected ? Theme.raised : "transparent"
                border.width: row.visualFocus ? 2 : 0; border.color: Theme.accent
            }
            contentItem: RowLayout {
                spacing: 12
                Label { Layout.leftMargin: 10; text: "󰤨"; font.pixelSize: 20; color: row.modelData.connected ? Theme.good : Theme.muted }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    Label { text: row.modelData.ssid; Layout.fillWidth: true }
                    Label { text: row.modelData.connected ? "Connected" : (row.modelData.uuid ? "Saved" : row.modelData.security || "Open network"); color: Theme.muted; font.pixelSize: 11 }
                }
                Label { text: row.modelData.signal + "%"; color: Theme.muted; font.pixelSize: 12; Layout.rightMargin: 10 }
            }
        }
        Label { anchors.centerIn: parent; visible: list.count === 0; text: root.net && !root.net.wifi ? "Wi-Fi is turned off" : "No cached networks\nTry Rescan"; horizontalAlignment: Text.AlignHCenter; color: Theme.muted; font.pixelSize: 12 }
    }
    ColumnLayout {
        visible: root.target !== null
        Layout.fillWidth: true; spacing: 8
        Label { Layout.fillWidth: true; text: root.target ? "Password for " + root.target.ssid : ""; color: Theme.accent }
        SearchField { id: password; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: "Wi-Fi password"; onAccepted: if (root.target && text.length) root.submit(root.target, text) }
        RowLayout {
            ActionButton { text: "Cancel"; onClicked: { password.text = ""; root.target = null; } }
            ActionButton { text: "Connect"; selected: true; enabled: password.text.length > 0; onClicked: root.submit(root.target, password.text) }
        }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
    ActionButton {
        objectName: "proton-vpn-action"
        visible: shell.networks.proton
        Layout.fillWidth: true
        text: root.net && root.net.vpn ? "󰒃  " + root.net.vpn + "\u2003Manage in Proton ↗" : "󰒃  Open Proton VPN ↗"
        onClicked: { shell.send("vpn"); shell.close(); }
    }
    Repeater {
        model: shell.networks.proton ? [] : shell.networks.vpns
        ActionButton {
            required property var modelData
            Layout.fillWidth: true; text: "󰒃  " + modelData.name + (root.net && root.net.vpn === modelData.name ? "\u2003Disconnect" : "\u2003Connect")
            enabled: !shell.networkBusy
            onClicked: { shell.networkBusy = true; shell.send("vpn", { uuid: modelData.uuid }); }
        }
    }
    ActionButton { visible: !!root.net && ["portal", "limited"].includes(root.net.connectivity); text: "Sign in to this network ↗"; onClicked: shell.send("portal") }
    ActionButton {
        objectName: "bluetooth-action"
        Layout.fillWidth: true
        text: "󰂯  Bluetooth" + (!root.bluetooth ? "\u2003Unavailable" : root.bluetooth.connected.length
            ? "\u2003" + root.bluetooth.connected.length + " connected" : root.bluetooth.powered ? "\u2003On" : "\u2003Off") + " ›"
        hint: root.bluetooth && root.bluetooth.connected.length ? root.bluetooth.connected.join("\n")
            : root.bluetooth && root.bluetooth.powered ? "Bluetooth on\nNo connected devices" : "Bluetooth off"
        onClicked: shell.open("bluetooth")
    }
    ActionButton {
        objectName: "cast-action"
        Layout.fillWidth: true
        text: "󰤉  Cast display ↗"
        hint: "Launch Miracast using AMD graphics"
        onClicked: { shell.send("open", { target: "cast" }); shell.close(); }
    }
}
