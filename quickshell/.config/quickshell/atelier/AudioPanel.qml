import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var shell
    property var audio: shell.state.audio
    implicitHeight: 210
    spacing: 16
    Label { text: "Sound"; font.pixelSize: 22; font.weight: Font.DemiBold }
    RowLayout {
        Layout.fillWidth: true
        Label { text: root.audio && root.audio.muted ? "Output muted" : "Default output"; color: Theme.muted; Layout.fillWidth: true }
        Label { text: root.audio ? root.audio.percent + "%" : "Unavailable"; font.pixelSize: 26; color: Theme.accent }
    }
    LevelSlider {
        id: volume
        objectName: "volume-slider"
        Layout.fillWidth: true
        enabled: !!root.audio
        Accessible.name: "Output volume"
        Binding { target: volume; property: "value"; value: root.audio ? root.audio.percent : 0; when: !volume.pressed && !apply.running }
        onMoved: apply.restart()
        VolumeWheel { shell: root.shell }
    }
    Timer { id: apply; interval: 80; onTriggered: shell.send("volume", { percent: volume.value }) }
    RowLayout {
        Layout.fillWidth: true
        ActionButton { text: root.audio && root.audio.muted ? "󰕾  Unmute" : "󰝟  Mute"; enabled: !!root.audio; onClicked: shell.send("mute") }
        Item { Layout.fillWidth: true }
        ActionButton { text: "Devices & mic"; onClicked: shell.open("audioDevices") }
        ActionButton { text: "Advanced settings ↗"; onClicked: { shell.send("open", { target: "audio" }); shell.close(); } }
    }
    Label { text: "Scroll the slider or audio button for 5% steps."; font.pixelSize: 11; color: Theme.muted }
}
