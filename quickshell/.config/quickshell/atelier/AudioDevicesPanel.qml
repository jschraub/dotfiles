import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var shell
    property var service: shell.desktopServices || null
    property var microphone: shell.state.microphone || null
    readonly property int panelHeight: 570
    spacing: 10
    Label { text: "Audio devices"; font.pixelSize: 22; font.weight: Font.DemiBold }
    Label { text: "OUTPUT"; color: Theme.accent; font.pixelSize: 11 }
    DevicePicker {
        Layout.fillWidth: true
        devices: root.service ? root.service.outputs : []
        current: root.service ? root.service.defaultOutput : null
        onPicked: device => root.service.setDefault(device, false)
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "MICROPHONE"; color: Theme.accent; font.pixelSize: 11; Layout.fillWidth: true }
        ActionButton {
            objectName: "microphone-mute"
            text: root.microphone && root.microphone.muted ? "Unmute" : "Mute"
            enabled: !!root.microphone
            onClicked: shell.send("mic-mute")
        }
    }
    DevicePicker {
        Layout.fillWidth: true
        devices: root.service ? root.service.inputs : []
        current: root.service ? root.service.defaultInput : null
        onPicked: device => root.service.setDefault(device, true)
    }
    Label {
        text: root.microphone ? (root.microphone.muted ? "Muted\u2003" : "Input level\u2003") + root.microphone.percent + "%" : "Microphone unavailable"
        color: Theme.muted
    }
    LevelSlider {
        id: level; Layout.fillWidth: true
        enabled: !!root.microphone
        Accessible.name: "Microphone volume"
        Binding { target: level; property: "value"; value: root.microphone ? root.microphone.percent : 0; when: !level.pressed && !apply.running }
        onMoved: apply.restart()
    }
    Timer { id: apply; interval: 80; onTriggered: shell.send("mic-volume", { percent: level.value }) }
    Item { Layout.fillHeight: true }
    Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Default-device changes affect new streams. Use Advanced for per-app routing, profiles and ports."; font.pixelSize: 11; color: Theme.muted }
    RowLayout {
        ActionButton { text: "‹  Sound"; onClicked: shell.open("audio") }
        Item { Layout.fillWidth: true }
        ActionButton { text: "Advanced ↗"; onClicked: { shell.send("open", { target: "audio" }); shell.close(); } }
    }
}
