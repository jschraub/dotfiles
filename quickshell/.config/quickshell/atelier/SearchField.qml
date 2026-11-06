import QtQuick
import QtQuick.Controls as Controls

Controls.TextField {
    id: root
    implicitHeight: 46
    font.family: Theme.font
    font.pixelSize: 16
    color: Theme.text
    selectionColor: Theme.accent
    selectedTextColor: Theme.background
    placeholderTextColor: Theme.muted
    leftPadding: 14
    rightPadding: 14
    background: Rectangle {
        color: Theme.background
        radius: 9
        border.color: root.activeFocus ? Theme.accent : Theme.line
    }
}
