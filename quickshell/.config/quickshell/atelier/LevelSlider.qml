import QtQuick
import QtQuick.Controls as Controls

Controls.Slider {
    id: root
    implicitHeight: 28
    from: 0; to: 100; stepSize: 1
    background: Rectangle {
        implicitHeight: 6
        x: root.leftPadding; y: root.topPadding + root.availableHeight / 2 - 3
        width: root.availableWidth; height: 6; radius: 3; color: Theme.background
        Rectangle { width: root.visualPosition * parent.width; height: parent.height; radius: 3; color: Theme.accent }
    }
    handle: Rectangle {
        implicitWidth: 16; implicitHeight: 16
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: 16; height: 16; radius: 8; color: Theme.text
    }
}
