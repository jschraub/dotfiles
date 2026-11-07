import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: window
    required property var shell
    screen: shell.menuScreen
    visible: shell.panel !== "" && !shell.testing && shell.menuScreen !== null
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "atelier-menu"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    color: "transparent"
    property bool centered: ["launcher", "bindings", "power"].includes(shell.panel)
    property real preferredWidth: shell.panel === "bindings" ? 940 : shell.panel === "launcher" ? 680 : shell.panel === "power" ? 460 : 420
    property real preferredHeight: ({ bindings: 600, launcher: 530, audio: 270, network: 650,
                                      calendar: 430, power: 340, notifications: 570, audioDevices: 570,
                                      bluetooth: 570, media: 430, tray: 470 })[shell.panel] || 300
    readonly property rect cardGeometry: Qt.rect(card.x, card.y, card.width, card.height)
    Rectangle { anchors.fill: parent; color: window.centered ? "#55000000" : "#10000000" }
    MouseArea { anchors.fill: parent; onClicked: shell.close() }
    Rectangle {
        id: card
        width: Math.min(window.preferredWidth, window.width - 32)
        height: Math.min(contents.item && contents.item.panelHeight !== undefined ? contents.item.panelHeight : window.preferredHeight,
                         window.height - Theme.barHeight - 40)
        x: window.centered ? (window.width - width) / 2 : window.width - width - 12
        y: window.centered ? Math.max(Theme.barHeight + 16, (window.height - height) * 0.32) : Theme.barHeight + 12
        color: Theme.panel
        radius: Theme.radius
        border.color: Theme.line
        // Consume the card background, without turning headers into menu entries.
        MouseArea { anchors.fill: parent; onClicked: mouse => mouse.accepted = true }
        ColumnLayout {
            id: body
            anchors { fill: parent; margins: 20 }
            spacing: 12
            Loader {
                id: contents
                Layout.fillWidth: true
                Layout.fillHeight: true
                onLoaded: Qt.callLater(function() {
                    if (contents.item && typeof contents.item.focusInitial === "function") contents.item.focusInitial();
                })
                sourceComponent: {
                    switch (shell.panel) {
                    case "launcher": return launcher;
                    case "bindings": return bindings;
                    case "audio": return audio;
                    case "audioDevices": return audioDevices;
                    case "bluetooth": return bluetooth;
                    case "media": return media;
                    case "tray": return tray;
                    case "network": return network;
                    case "calendar": return calendar;
                    case "power": return power;
                    case "notifications": return notificationCenter;
                    default: return null;
                    }
                }
            }
            Label {
                visible: shell.message.length > 0
                text: shell.message
                color: Theme.danger
                wrapMode: Text.WordWrap
                elide: Text.ElideNone
                Layout.fillWidth: true
            }
        }
    }
    Shortcut { sequence: "Escape"; enabled: window.visible; onActivated: shell.close() }
    Component { id: launcher; Launcher { shell: window.shell } }
    Component { id: bindings; Bindings { shell: window.shell } }
    Component { id: audio; AudioPanel { shell: window.shell } }
    Component { id: audioDevices; AudioDevicesPanel { shell: window.shell } }
    Component { id: bluetooth; BluetoothPanel { shell: window.shell } }
    Component { id: media; MediaPanel { shell: window.shell } }
    Component { id: tray; TrayPanel { shell: window.shell } }
    Component { id: network; NetworkPanel { shell: window.shell } }
    Component { id: calendar; CalendarPanel {} }
    Component { id: power; PowerPanel { shell: window.shell } }
    Component { id: notificationCenter; NotificationCenter { service: window.shell.notificationService } }
}
