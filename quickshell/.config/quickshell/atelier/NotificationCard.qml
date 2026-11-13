import QtQuick
import QtQuick.Layouts
import Quickshell

Rectangle {
    id: root
    required property var record
    required property var service
    property bool compact: false
    implicitHeight: body.implicitHeight + 28
    radius: 10
    color: Theme.raised
    border.color: record.critical ? Theme.danger : Theme.line
    ColumnLayout {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        spacing: 8
        RowLayout {
            Image {
                visible: !!root.record.icon
                source: !root.record.icon ? "" : root.record.icon.startsWith("/") || root.record.icon.startsWith("file:") ? root.record.icon : Quickshell.iconPath(root.record.icon)
                sourceSize.width: 18; sourceSize.height: 18
            }
            Label { text: root.record.app || "Notification"; color: Theme.accent; font.pixelSize: 11; Layout.fillWidth: true }
            ActionButton { text: "×"; implicitWidth: 28; implicitHeight: 28; hint: "Dismiss notification"; Accessible.name: "Dismiss notification from " + (root.record.app || "application"); onClicked: root.service.remove(root.record.id) }
        }
        Label { Layout.fillWidth: true; text: root.record.title; font.weight: Font.DemiBold; wrapMode: Text.WordWrap; maximumLineCount: root.compact ? 2 : 6; elide: Text.ElideRight }
        Label { Layout.fillWidth: true; visible: !!root.record.body; text: root.record.body; font.pixelSize: 12; color: Theme.muted; wrapMode: Text.WordWrap; maximumLineCount: root.compact ? 3 : 8; elide: Text.ElideRight }
        Image { visible: !!root.record.image; source: root.record.image; Layout.fillWidth: true; Layout.preferredHeight: visible ? (root.compact ? 80 : 100) : 0; fillMode: Image.PreserveAspectFit }
        Flow {
            Layout.fillWidth: true
            spacing: 4
            Repeater {
                model: root.record.live ? root.record.live.actions : []
                ActionButton { required property var modelData; text: modelData.text; implicitHeight: 28; onClicked: modelData.invoke() }
            }
        }
    }
}
