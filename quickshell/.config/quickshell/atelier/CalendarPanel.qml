import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    implicitHeight: 350
    spacing: 12
    property date today: new Date()
    property date month: new Date(today.getFullYear(), today.getMonth(), 1)
    property date selected: today
    function focusDate(date) {
        root.selected = date;
        root.month = new Date(date.getFullYear(), date.getMonth(), 1);
        Qt.callLater(function() {
            for (let i = 0; i < dates.count; i++) {
                const button = dates.itemAt(i);
                if (button && button.modelData.toDateString() === date.toDateString()) {
                    button.forceActiveFocus(Qt.TabFocusReason); break;
                }
            }
        });
    }
    function moveDate(date, offset) { focusDate(new Date(date.getFullYear(), date.getMonth(), date.getDate() + offset)); }
    property var days: {
        const offset = (month.getDay() + 6) % 7;
        return Array.from({ length: 42 }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i - offset + 1));
    }
    Label { text: Qt.formatDate(root.today, "dddd, d MMMM"); color: Theme.accent; font.pixelSize: 12 }
    RowLayout {
        Label { text: Qt.formatDate(root.month, "MMMM yyyy"); font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        ActionButton { text: "‹"; Accessible.name: "Previous month"; hint: "Previous month"; onClicked: root.month = new Date(root.month.getFullYear(), root.month.getMonth() - 1, 1) }
        ActionButton { text: "›"; Accessible.name: "Next month"; hint: "Next month"; onClicked: root.month = new Date(root.month.getFullYear(), root.month.getMonth() + 1, 1) }
    }
    GridLayout {
        Layout.fillWidth: true; Layout.fillHeight: true
        columns: 7; columnSpacing: 2; rowSpacing: 2
        Repeater {
            model: ["M", "T", "W", "T", "F", "S", "S"]
            Label { required property var modelData; text: modelData; color: Theme.muted; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
        }
        Repeater {
            id: dates
            model: root.days
            ActionButton {
                required property var modelData
                objectName: "calendar-date-" + Qt.formatDate(modelData, "yyyy-MM-dd")
                Layout.fillWidth: true; Layout.fillHeight: true
                text: modelData.getDate()
                selected: modelData.toDateString() === root.selected.toDateString()
                // Keep adjacent-month dates readable; distinguish them without
                // compositing the whole control below text contrast thresholds.
                textColor: modelData.getMonth() === root.month.getMonth() ? Theme.text : Theme.muted
                Accessible.name: Qt.formatDate(modelData, "dddd, d MMMM yyyy")
                Accessible.selected: selected
                hint: Qt.formatDate(modelData, "dddd, d MMMM yyyy")
                onClicked: root.selected = modelData
                Keys.onLeftPressed: root.moveDate(modelData, -1)
                Keys.onRightPressed: root.moveDate(modelData, 1)
                Keys.onUpPressed: root.moveDate(modelData, -7)
                Keys.onDownPressed: root.moveDate(modelData, 7)
                Rectangle { anchors { bottom: parent.bottom; bottomMargin: 2; horizontalCenter: parent.horizontalCenter } width: 3; height: 3; radius: 2; color: Theme.accent; visible: modelData.toDateString() === root.today.toDateString() }
            }
        }
    }
    RowLayout {
        Label { Layout.fillWidth: true; text: Qt.formatDate(root.selected, "d MMMM yyyy"); color: Theme.muted; font.pixelSize: 12 }
        ActionButton { text: "Today"; onClicked: { root.today = new Date(); root.selected = root.today; root.month = new Date(root.today.getFullYear(), root.today.getMonth(), 1); } }
    }
}
