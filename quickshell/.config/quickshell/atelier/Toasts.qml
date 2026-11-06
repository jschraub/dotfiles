import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: root
    required property var shell
    required property var service
    screen: shell.focusedScreen()
    anchors { top: true; right: true }
    margins { top: Theme.barHeight + 12; right: 12 }
    implicitWidth: 380
    property int maximumToasts: Math.max(1, Math.floor(((screen ? screen.height : 800) - Theme.barHeight - 24) / 280))
    implicitHeight: stack.implicitHeight
    visible: !shell.testing && service.toastItems.length > 0 && shell.panel !== "notifications"
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.namespace: "atelier-notifications"
    WlrLayershell.layer: WlrLayer.Overlay
    ColumnLayout {
        id: stack
        width: parent.width; spacing: 8
        Repeater { model: root.service.toastItems.slice(0, root.maximumToasts); NotificationCard { required property var modelData; Layout.fillWidth: true; record: modelData; service: root.service; compact: true } }
    }
}
