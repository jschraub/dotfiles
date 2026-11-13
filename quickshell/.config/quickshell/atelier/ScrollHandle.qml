import QtQuick
import QtQuick.Controls as Controls

Controls.ScrollBar {
    id: root
    policy: Controls.ScrollBar.AsNeeded
    padding: 1
    contentItem: Rectangle {
        implicitWidth: 4
        implicitHeight: 24
        radius: 2
        color: root.pressed ? Theme.accent : root.hovered ? Theme.muted : Theme.line
        opacity: root.active || root.hovered ? 1 : 0
        Behavior on opacity { enabled: !Theme.reducedMotion; NumberAnimation { duration: 120 } }
    }
    background: Item {}
}
