import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

Controls.ScrollView {
    id: root
    required property var devices
    required property var current
    signal picked(var device)
    implicitHeight: Math.min(150, column.implicitHeight)
    contentWidth: availableWidth
    contentHeight: column.implicitHeight
    clip: true
    Controls.ScrollBar.vertical: ScrollHandle {}
    ColumnLayout {
    id: column
    width: root.availableWidth
    spacing: 2
    Repeater {
        model: root.devices
        ActionButton {
            required property var modelData
            objectName: "audio-device-" + modelData.id
            Layout.fillWidth: true
            alignLeft: true
            selected: root.current === modelData
            text: (selected ? "●  " : "○  ") + (modelData.description || modelData.nickname || modelData.name)
            onClicked: root.picked(modelData)
        }
    }
    Label { visible: root.devices.length === 0; text: "No devices available"; color: Theme.muted; font.pixelSize: 12 }
    }
}
