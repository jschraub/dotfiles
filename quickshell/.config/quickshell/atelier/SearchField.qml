import QtQuick
import QtQuick.Controls as Controls

Controls.TextField {
    id: root
    implicitHeight: Math.max(46, contentHeight + 20)
    font.family: Theme.font
    font.pixelSize: 16
    color: Theme.text
    selectionColor: Theme.accent
    selectedTextColor: Theme.background
    placeholderTextColor: Theme.muted
    leftPadding: 14
    rightPadding: 14
    Accessible.name: placeholderText
    background: Rectangle {
        color: Theme.background
        radius: 9
        border.color: root.activeFocus ? Theme.accent : Theme.line
        border.width: root.visualFocus ? 2 : 1
    }
}
