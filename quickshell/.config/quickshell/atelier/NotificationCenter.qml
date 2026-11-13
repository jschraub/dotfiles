import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import "Focus.js" as Focus

ColumnLayout {
    id: root
    required property var service
    implicitHeight: 480
    spacing: 12
    RowLayout {
        Label { text: "Notifications"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        ActionButton { text: "Clear"; enabled: !!root.service && root.service.history.length > 0; onClicked: root.service.clear() }
    }
    ActionButton { text: root.service && root.service.dnd ? "󰂛  Do not disturb\u2003On" : "󰂚  Do not disturb\u2003Off"; Accessible.name: "Do not disturb"; accessibleToggle: true; selected: !!root.service && root.service.dnd; enabled: !!root.service; onClicked: root.service.dnd = !root.service.dnd }
    ListView {
        id: list
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 8
        model: root.service ? root.service.history : []
        Controls.ScrollBar.vertical: ScrollHandle {}
        delegate: NotificationCard {
            required property var modelData
            required property int index
            width: list.width; record: modelData; service: root.service
            Keys.onDownPressed: Focus.row(list, index + 1)
            Keys.onUpPressed: Focus.row(list, index - 1)
        }
        Label { anchors.centerIn: parent; text: root.service ? "You're all caught up" : "Preview\nNotifications are disabled"; horizontalAlignment: Text.AlignHCenter; color: Theme.muted; visible: list.count === 0; font.pixelSize: 12 }
    }
}
