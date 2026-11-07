import QtQuick
import Quickshell

Item {
    id: root
    required property var controller
    required property var identity
    property bool login: false
    property bool preview: false
    property date now: new Date()
    Timer { interval: 1000; repeat: true; running: true; onTriggered: root.now = new Date() }
    Rectangle { anchors.fill: parent; color: Theme.background }
    Image {
        anchors.fill: parent
        source: root.identity.background ? "file://" + root.identity.background : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }
    Rectangle { anchors.fill: parent; color: "#44000000" }
    Column {
        anchors { top: parent.top; right: parent.right; margins: Math.max(24, parent.width * 0.025) }
        spacing: 6
        Label { anchors.right: parent.right; text: Qt.formatDateTime(root.now, "HH:mm"); font.pixelSize: Math.min(76, root.width / 12); color: Theme.text }
        Label { anchors.right: parent.right; text: Qt.formatDateTime(root.now, "dddd, d MMMM yyyy"); font.pixelSize: 18; color: Theme.text }
    }
    Rectangle {
        width: Math.min(420, parent.width - 40)
        height: Math.min(card.implicitHeight + 48, parent.height - 40)
        anchors.centerIn: parent
        color: Qt.rgba(Theme.panel.r, Theme.panel.g, Theme.panel.b, 0.93)
        radius: Theme.radius; border.color: Theme.line
        Flickable {
            anchors { fill: parent; margins: 24 }
            contentWidth: width; contentHeight: card.implicitHeight; clip: true
            AccessCard {
                id: card; width: parent.width
                controller: root.controller; users: root.identity.users
                login: root.login; preview: root.preview
                onResponse: value => root.controller.respond(value)
                onBegin: root.controller.begin()
                onSelectUser: user => root.controller.selectUser(user)
            }
        }
    }
    Row {
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 24 }
        visible: root.login
        spacing: 16
        ActionButton { text: "Restart"; enabled: !root.preview && !root.controller.powerPending; onClicked: root.controller.power("reboot") }
        ActionButton { text: "Shut down"; enabled: !root.preview && !root.controller.powerPending; onClicked: root.controller.power("poweroff") }
    }
}
