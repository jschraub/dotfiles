import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell
import "Focus.js" as Focus

ColumnLayout {
    id: root
    required property var shell
    implicitHeight: 480
    spacing: 14
    property var filtered: shell.apps.filter(a => (a.name + " " + a.description + " " + a.keywords).toLowerCase().includes(search.text.toLowerCase()))
    function launch(app) { if (app) shell.send("launch", { id: app.id }); }
    function focusInitial() { search.forceActiveFocus(Qt.TabFocusReason); }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "Applications"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        Label { text: "SUPER + SPACE"; font.pixelSize: 10; font.letterSpacing: 1.2; color: Theme.good }
    }
    SearchField {
        id: search
        Layout.fillWidth: true
        placeholderText: "Search applications…"
        focus: true
        Component.onCompleted: forceActiveFocus()
        onTextChanged: list.currentIndex = 0
        Keys.onDownPressed: list.currentIndex = Math.min(list.count - 1, list.currentIndex + 1)
        Keys.onUpPressed: list.currentIndex = Math.max(0, list.currentIndex - 1)
        onAccepted: root.launch(root.filtered[list.currentIndex])
    }
    ListView {
        id: list
        Layout.fillWidth: true; Layout.fillHeight: true
        clip: true; spacing: 4
        model: root.filtered
        currentIndex: 0
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: ScrollHandle {}
        onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
        delegate: Controls.AbstractButton {
            id: row
            required property var modelData
            required property int index
            objectName: "application-" + index
            focusPolicy: Qt.StrongFocus
            Accessible.name: modelData.name
            Accessible.description: modelData.description
            Accessible.selected: index === list.currentIndex
            onActiveFocusChanged: if (activeFocus) list.currentIndex = index
            width: list.width; height: 60
            hoverEnabled: true
            onClicked: root.launch(modelData)
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) root.launch(modelData); }
            Keys.onEnterPressed: event => { if (!event.isAutoRepeat) root.launch(modelData); }
            onHoveredChanged: if (hovered) list.currentIndex = index
            Keys.onDownPressed: Focus.row(list, index + 1)
            Keys.onUpPressed: Focus.row(list, index - 1)
            background: Rectangle {
                radius: 9; color: row.index === list.currentIndex ? Theme.raised : "transparent"
                border.width: row.visualFocus ? 2 : 0; border.color: Theme.accent
            }
            contentItem: RowLayout {
                spacing: 14
                Image { source: Quickshell.iconPath(row.modelData.icon.split(" ")[0]); sourceSize.width: 32; sourceSize.height: 32; Layout.leftMargin: 12 }
                ColumnLayout {
                    spacing: 3; Layout.fillWidth: true
                    Label { text: row.modelData.name; font.weight: Font.Medium; Layout.fillWidth: true }
                    Label { text: row.modelData.description; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
                }
                Label { text: "↵"; color: Theme.good; visible: row.index === list.currentIndex; Layout.rightMargin: 14 }
            }
        }
        Label { anchors.centerIn: parent; visible: list.count === 0; text: "No applications found"; color: Theme.muted }
    }
    RowLayout {
        Label { text: root.filtered.length + " applications"; font.pixelSize: 11; color: Theme.muted; Layout.fillWidth: true }
        ActionButton { text: "Keyboard shortcuts ↗"; implicitHeight: 24; onClicked: shell.open("bindings", shell.menuScreen) }
        Label {
            text: "<font color='" + Theme.good + "'>↑ ↓</font>  Navigate     <font color='" + Theme.good
                + "'>↵</font>  Open     <font color='" + Theme.good + "'>Esc</font>  Close"
            textFormat: Text.RichText
            font.pixelSize: 11; color: Theme.muted
        }
    }
}
