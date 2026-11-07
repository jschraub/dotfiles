import QtQuick
import QtQuick.Controls as Controls
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
    Controls.Slider {
        id: volume
        objectName: "volume-slider"
        implicitHeight: 28
        Layout.fillWidth: true
        from: 0; to: 100; stepSize: 1
        enabled: !!root.audio
        Accessible.name: "Output volume"
        Binding { target: volume; property: "value"; value: root.audio ? root.audio.percent : 0; when: !volume.pressed && !apply.running }
        onMoved: apply.restart()
        VolumeWheel { shell: root.shell }
        background: Rectangle {
            implicitHeight: 6
            x: volume.leftPadding; y: volume.topPadding + volume.availableHeight / 2 - 3
            width: volume.availableWidth; height: 6; radius: 3; color: Theme.background
            Rectangle { width: volume.visualPosition * parent.width; height: parent.height; radius: 3; color: Theme.accent }
        }
        handle: Rectangle {
            implicitWidth: 16; implicitHeight: 16
            x: volume.leftPadding + volume.visualPosition * (volume.availableWidth - width)
            y: volume.topPadding + volume.availableHeight / 2 - height / 2
            width: 16; height: 16; radius: 8; color: Theme.text
        }
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
