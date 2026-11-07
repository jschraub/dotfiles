import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: root
    required property var shell
    property string kind: ""
    property int percent: 0
    property bool muted: false
    screen: shell.focusedScreen()
    visible: !!kind && !shell.preview && !shell.testing
    anchors.bottom: true
    margins.bottom: 80
    implicitWidth: 300; implicitHeight: 88
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "atelier-osd"
    mask: Region {}
    color: "transparent"
    function show(type, value, isMuted) {
        if (!["volume", "microphone", "brightness"].includes(type)) return;
        kind = type; percent = Math.round(Math.max(0, Math.min(100, value))); muted = isMuted;
        hide.restart();
    }
    Timer { id: hide; interval: 1400; onTriggered: root.kind = "" }
    Rectangle {
        anchors.fill: parent; color: Theme.panel; radius: Theme.radius; border.color: Theme.line
        ColumnLayout {
            anchors { fill: parent; margins: 16 }
            spacing: 12
            RowLayout {
                Label { text: root.kind === "brightness" ? "󰃠  Brightness" : root.kind === "microphone" ? "󰍬  Microphone" : "󰕾  Volume"; Layout.fillWidth: true }
                Label { text: root.muted ? "Muted" : root.percent + "%"; color: root.muted ? Theme.muted : Theme.accent }
            }
            Rectangle {
                Layout.fillWidth: true; height: 5; radius: 3; color: Theme.background
                Rectangle { width: parent.width * root.percent / 100; height: parent.height; radius: 3; color: root.muted ? Theme.muted : Theme.accent }
            }
        }
    }
}
