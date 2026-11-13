import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell.Bluetooth
import "Focus.js" as Focus

ColumnLayout {
    id: root
    required property var shell
    property var service: shell.desktopServices || null
    property var adapter: service && service.adapters.length ? service.adapters[0] : null
    property var ownedScan: null
    property var pendingDevice: null
    property bool pendingConnected: false
    readonly property var devices: adapter ? adapter.devices.values : []
    readonly property int panelHeight: 570
    spacing: 10
    function stopScan() {
        try { if (ownedScan) ownedScan.discovering = false; } catch (error) { /* Adapter was removed. */ }
        ownedScan = null;
        scanTimeout.stop();
    }
    Component.onDestruction: stopScan()
    onAdapterChanged: stopScan()
    Timer { id: scanTimeout; interval: 20000; onTriggered: root.stopScan() }
    Timer {
        id: connectionTimeout; interval: 15000
        onTriggered: {
            if (root.pendingDevice && root.pendingDevice.connected !== root.pendingConnected)
                shell.message = "Bluetooth change did not finish. Try again or use Advanced for details.";
            root.pendingDevice = null;
        }
    }
    Connections {
        target: root.pendingDevice
        function onConnectedChanged() {
            if (root.pendingDevice && root.pendingDevice.connected === root.pendingConnected) {
                shell.message = ""; root.pendingDevice = null; connectionTimeout.stop();
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "Bluetooth"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        ActionButton { text: root.adapter && root.adapter.enabled ? "On" : "Off"; Accessible.name: "Bluetooth"; accessibleToggle: true; selected: !!root.adapter && root.adapter.enabled; enabled: !!root.adapter; onClicked: root.adapter.enabled = !root.adapter.enabled }
    }
    RowLayout {
        Repeater {
            model: root.service ? root.service.adapters : []
            ActionButton { required property var modelData; visible: root.service.adapters.length > 1; text: modelData.name; selected: root.adapter === modelData; onClicked: root.adapter = modelData }
        }
    }
    Label { text: root.adapter ? root.adapter.name : "No Bluetooth adapter available"; color: Theme.muted }
    RowLayout {
        ActionButton {
            objectName: "bluetooth-scan"
            text: root.ownedScan ? "Stop scan" : root.adapter && root.adapter.discovering ? "Scanning…" : "Scan for devices"
            enabled: !!root.adapter && root.adapter.enabled && (!root.adapter.discovering || !!root.ownedScan)
            onClicked: {
                if (root.ownedScan) root.stopScan();
                else if (!root.adapter.discovering) { root.ownedScan = root.adapter; root.adapter.discovering = true; scanTimeout.restart(); }
            }
        }
        Item { Layout.fillWidth: true }
        ActionButton { text: "Advanced / Pair ↗"; onClicked: { shell.send("open", { target: "bluetooth" }); shell.close(); } }
    }
    ListView {
        id: list; Layout.fillWidth: true; Layout.fillHeight: true
        model: root.devices
        spacing: 6; clip: true
        Controls.ScrollBar.vertical: ScrollHandle {}
        delegate: RowLayout {
            required property var modelData
            required property int index
            Keys.onDownPressed: Focus.row(list, index + 1)
            Keys.onUpPressed: Focus.row(list, index - 1)
            width: list.width; height: 62; spacing: 8
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                Label { text: modelData.name || modelData.address; Layout.fillWidth: true }
                Label {
                    Layout.fillWidth: true; font.pixelSize: 11; color: modelData.connected ? Theme.good : Theme.muted
                    text: BluetoothDeviceState.toString(modelData.state)
                        + (modelData.batteryAvailable ? "\u2003" + Math.round(modelData.battery * 100) + "% battery" : "")
                        + (!modelData.paired ? "\u2003Pair in Advanced" : "")
                }
            }
            ActionButton {
                objectName: "bluetooth-device-" + modelData.address
                text: modelData.connected ? "Disconnect" : "Connect"
                Accessible.name: (modelData.connected ? "Disconnect " : "Connect ") + (modelData.name || modelData.address)
                enabled: !!root.adapter && root.adapter.enabled && modelData.paired && !modelData.blocked
                    && !root.pendingDevice
                    && modelData.state !== BluetoothDeviceState.Connecting && modelData.state !== BluetoothDeviceState.Disconnecting
                onClicked: {
                    root.pendingConnected = !modelData.connected;
                    root.pendingDevice = modelData;
                    shell.message = root.pendingConnected ? "Connecting Bluetooth device…" : "Disconnecting Bluetooth device…";
                    connectionTimeout.restart();
                    modelData.connected = root.pendingConnected;
                }
            }
        }
        Label { anchors.centerIn: parent; visible: list.count === 0; text: root.adapter && !root.adapter.enabled ? "Bluetooth is off" : "No devices\nTry Scan"; horizontalAlignment: Text.AlignHCenter; color: Theme.muted }
    }
    Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11; color: Theme.muted; text: "Known devices connect here. Pairing/PIN confirmation stays in Blueman; devices are never automatically trusted or paired." }
    ActionButton { text: "‹  Connectivity"; onClicked: shell.open("network") }
}
