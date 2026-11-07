import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var shell
    property var service: shell.clipboardService || null
    readonly property var items: service ? service.items : []
    readonly property var selected: list.currentIndex >= 0 ? items[list.currentIndex] || null : null
    readonly property int panelHeight: 620
    spacing: 12
    function focusInitial() { search.forceActiveFocus(Qt.TabFocusReason); }
    function choose() { if (service && selected) service.copy(selected.id); }
    function move(delta) { list.currentIndex = Math.max(0, Math.min(list.count - 1, list.currentIndex + delta)); }
    onItemsChanged: list.currentIndex = items.length ? 0 : -1
    Component.onCompleted: { if (service) service.search(""); Qt.callLater(focusInitial); }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "Clipboard"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        Label { text: "SUPER + V"; color: Theme.good; font.pixelSize: 10; font.letterSpacing: 1.2 }
    }
    RowLayout {
        Layout.fillWidth: true
        ActionButton {
            objectName: "clipboard-pause"
            text: root.service && root.service.paused ? "Resume history" : "Pause history"
            selected: !!root.service && root.service.paused
            enabled: !!root.service && (root.service.ready || !!root.service.started) && !root.service.busy
            onClicked: root.service.togglePaused()
        }
        Item { Layout.fillWidth: true }
        ActionButton {
            objectName: "clipboard-clear"
            text: "Clear history"; dangerous: true
            hint: "Removes remembered items, not the current clipboard"
            enabled: !!root.service && (root.service.ready || !!root.service.started) && root.service.count > 0 && !root.service.busy
            onClicked: root.service.clear()
        }
    }
    SearchField {
        id: search
        objectName: "clipboard-search"
        Layout.fillWidth: true
        placeholderText: "Search copied text or PNG images…"
        maximumLength: 512
        onTextChanged: applySearch.restart()
        Keys.onDownPressed: root.move(1)
        Keys.onUpPressed: root.move(-1)
        onAccepted: root.choose()
    }
    Timer { id: applySearch; interval: 80; onTriggered: if (root.service) root.service.search(search.text) }
    ListView {
        id: list
        objectName: "clipboard-list"
        Layout.fillWidth: true; Layout.fillHeight: true
        model: root.items; spacing: 4; clip: true
        currentIndex: count ? 0 : -1
        boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: ScrollHandle {}
        onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
        delegate: Controls.AbstractButton {
            id: row
            required property var modelData
            required property int index
            objectName: "clipboard-item-" + index
            width: list.width; height: 66
            hoverEnabled: true
            onClicked: if (root.service) root.service.copy(modelData.id)
            onHoveredChanged: if (hovered) list.currentIndex = index
            background: Rectangle {
                radius: 8; color: row.index === list.currentIndex ? Theme.raised : "transparent"
                border.width: row.index === list.currentIndex ? 1 : 0
                border.color: Theme.accent
            }
            contentItem: RowLayout {
                spacing: 12
                Rectangle {
                    Layout.leftMargin: 10; Layout.preferredWidth: 64; Layout.preferredHeight: 44
                    radius: 5; color: Theme.background
                    Image {
                        id: thumbnail
                        anchors.fill: parent
                        visible: row.modelData.kind === "image"
                        source: row.modelData.preview || ""
                        sourceSize.width: 128; sourceSize.height: 88
                        fillMode: Image.PreserveAspectFit; asynchronous: true; cache: false
                    }
                    Label {
                        anchors.centerIn: parent; font.pixelSize: 10; color: Theme.muted
                        text: row.modelData.kind === "image" ? "PNG" : "TEXT"
                        visible: row.modelData.kind !== "image" || thumbnail.status !== Image.Ready
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 5
                    Label {
                        objectName: "clipboard-summary-" + row.index
                        Layout.fillWidth: true
                        text: row.modelData.label.replace(/\r?\n/g, "  ↵  ")
                        font.pixelSize: 13
                    }
                    Label {
                        text: row.modelData.size >= 1024 ? Math.ceil(row.modelData.size / 1024) + " KiB" : row.modelData.size + " B"
                        color: Theme.muted; font.pixelSize: 11
                    }
                }
                Label { text: "↵"; color: Theme.good; visible: row.index === list.currentIndex }
                ActionButton {
                    objectName: "clipboard-delete-" + row.index
                    Layout.rightMargin: 6
                    text: "×"; hint: "Remove from history"
                    enabled: !!root.service && !root.service.busy
                    onClicked: root.service.remove(row.modelData.id)
                }
            }
        }
        Label {
            anchors.centerIn: parent
            visible: list.count === 0
            horizontalAlignment: Text.AlignHCenter
            text: !root.service ? "Clipboard history is unavailable in this preview"
                : !root.service.ready ? "Clipboard capture is unavailable"
                : search.text ? "No matching clipboard items"
                : root.service.paused ? "History is paused\nPreviously copied items stay available"
                : "Nothing remembered yet\nCopy some text or a PNG image"
            color: Theme.muted; font.pixelSize: 12
        }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
    Controls.ScrollView {
        visible: !!root.selected && root.selected.kind === "text"
        Layout.fillWidth: true; Layout.preferredHeight: 90
        contentWidth: availableWidth
        clip: true
        Controls.ScrollBar.vertical: ScrollHandle {}
        Controls.TextArea {
            text: root.selected && root.selected.kind === "text" ? root.selected.text : ""
            readOnly: true; selectByMouse: true; wrapMode: TextEdit.WrapAnywhere
            textFormat: TextEdit.PlainText
            color: Theme.text; font.family: Theme.mono; font.pixelSize: 12
            background: Rectangle { radius: 6; color: Theme.background }
        }
    }
    Label {
        visible: !!root.selected && !!root.selected.truncated
        text: "Preview shortened — copying preserves the full item"
        color: Theme.muted; font.pixelSize: 11
    }
    Label {
        visible: !!root.service && (!!root.service.message || !root.service.ready)
        text: root.service ? root.service.message || "Capture is unavailable; existing history can still be copied." : ""
        Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.danger; font.pixelSize: 11
    }
    RowLayout {
        Layout.fillWidth: true
        Label {
            text: root.items.length + " shown\u2003" + (root.service ? root.service.count : 0) + " stored"
            color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true
        }
        Label { text: "RAM only\u2003No automatic paste"; color: Theme.muted; font.pixelSize: 11 }
    }
    Label {
        text: "<font color='" + Theme.good + "'>↑ ↓</font> Navigate&emsp;<font color='" + Theme.good
            + "'>Enter</font> Copy&emsp;<font color='" + Theme.good
            + "'>Ctrl+Delete</font> Remove&emsp;<font color='" + Theme.good + "'>Esc</font> Close"
        textFormat: Text.RichText; font.pixelSize: 11; color: Theme.muted
    }
    Shortcut {
        sequence: "Ctrl+Delete"
        enabled: root.visible && root.shell.panel === "clipboard"
        onActivated: if (root.service && root.selected) root.service.remove(root.selected.id)
    }
}
