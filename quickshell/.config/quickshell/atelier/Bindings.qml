import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import "Focus.js" as Focus

ColumnLayout {
    id: root
    required property var shell
    implicitHeight: 540
    spacing: 14
    property string category: "All shortcuts"
    property var categories: ["All shortcuts"].concat(Array.from(new Set(shell.bindings.map(b => b.category))))
    property var filtered: shell.bindings.filter(b => (category === "All shortcuts" || b.category === category)
        && (b.key + " " + b.description + " " + b.category + " " + b.context).toLowerCase().includes(search.text.toLowerCase()))
    ListModel { id: entries }
    function rebuild() {
        entries.clear();
        filtered.forEach(row => entries.append(row));
    }
    onFilteredChanged: rebuild()
    Component.onCompleted: rebuild()
    RowLayout {
        Label { text: "Keyboard shortcuts"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        Label { text: "SUPER + F1"; color: Theme.good; font.pixelSize: 10; font.letterSpacing: 1.2 }
    }
    SearchField {
        id: search; Layout.fillWidth: true; placeholderText: "Search shortcuts, actions or categories…"; focus: true
        Component.onCompleted: forceActiveFocus()
        Keys.onDownPressed: list.contentY = Math.min(Math.max(0, list.contentHeight - list.height), list.contentY + 40)
        Keys.onUpPressed: list.contentY = Math.max(0, list.contentY - 40)
        Keys.onPressed: event => {
            if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
                list.contentY = Math.max(0, Math.min(Math.max(0, list.contentHeight - list.height), list.contentY + (event.key === Qt.Key_PageDown ? 1 : -1) * list.height));
                event.accepted = true;
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
        ListView {
            id: categoryList
            Layout.preferredWidth: 170; Layout.fillHeight: true
            model: root.categories; clip: true; spacing: 4
            delegate: ActionButton {
                required property var modelData
                required property int index
                width: categoryList.width
                text: modelData
                hint: modelData
                Accessible.selected: selected
                Keys.onDownPressed: Focus.row(categoryList, index + 1)
                Keys.onUpPressed: Focus.row(categoryList, index - 1)
                alignLeft: true
                selected: root.category === modelData
                onClicked: root.category = modelData
            }
        }
        Rectangle { Layout.fillHeight: true; width: 1; color: Theme.line }
        ListView {
            id: list
            Layout.fillWidth: true; Layout.fillHeight: true
            model: entries; clip: true; spacing: 4
            boundsBehavior: Flickable.StopAtBounds
            Controls.ScrollBar.vertical: ScrollHandle {}
            section.property: "category"
            section.delegate: Item {
                required property string section
                width: list.width; height: 42
                Label { anchors { left: parent.left; bottom: parent.bottom; bottomMargin: 8 } text: section.toUpperCase(); color: Theme.accent; font.pixelSize: 10; font.letterSpacing: 1.5; font.weight: Font.DemiBold }
            }
            delegate: RowLayout {
                id: bindingRow
                required property string key
                required property string description
                required property string context
                width: list.width; height: context ? 58 : 40; spacing: 16
                Rectangle {
                    Layout.preferredWidth: 226; Layout.preferredHeight: 30
                    radius: 6; color: Theme.background
                    Label { anchors { fill: parent; leftMargin: 10; rightMargin: 10 } text: bindingRow.key; font.family: Theme.mono; font.pixelSize: 12; color: Theme.good }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 3
                    Label { Layout.fillWidth: true; text: bindingRow.description; font.pixelSize: 13 }
                    Label { Layout.fillWidth: true; visible: !!bindingRow.context; text: bindingRow.context; color: Theme.muted; font.pixelSize: 10 }
                }
            }
            Label { anchors.centerIn: parent; visible: list.count === 0; text: "No matching shortcuts"; color: Theme.muted }
        }
    }
    Label { text: root.filtered.length + " shortcuts\u2003\u2003Reference only — actions never execute here"; font.pixelSize: 11; color: Theme.muted }
}
