import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import "Focus.js" as Focus

ColumnLayout {
    id: root
    required property var shell
    implicitHeight: 540
    spacing: 10
    property string tabId: "desktop"
    property string scope: "workspace"
    property string toolId: "auto"
    property string category: "All shortcuts"
    property var context: shell.bindingContext || { tabs: [], tools: [], selected: "desktop" }
    property var scopedTabs: scope === "installed" ? (context.library || []) : context.tabs
    property var tabs: scopedTabs.length ? scopedTabs : [{ id: "desktop", label: "Desktop",
        rows: shell.bindings, note: "Loading shortcut references…", terminal: false }]
    property var currentTab: tabs.find(t => t.id === tabId) || tabs[0]
    property var tools: [{ id: "auto", label: "Detected tools" }, { id: "none", label: "Terminal only" }]
        .concat(context.tools.filter(t => (currentTab.toolIds || []).includes(t.id)))
    property var chosenTool: context.tools.find(t => t.id === toolId)
    property var currentRows: currentTab.terminal && toolId !== "auto"
        ? (currentTab.baseRows || []).concat(chosenTool ? chosenTool.rows : []) : currentTab.rows
    property string note: currentTab.terminal && chosenTool
        ? "Manually selected " + chosenTool.label + ". " + chosenTool.note : currentTab.note
    property var categories: ["All shortcuts"].concat(Array.from(new Set(currentRows.map(b => b.category))))
    property var filtered: currentRows.filter(b => (category === "All shortcuts" || b.category === category)
        && (b.key + " " + b.description + " " + b.category + " " + b.context + " " + (b.source || "")).toLowerCase().includes(search.text.toLowerCase()))
    ListModel { id: entries }
    function focusInitial() { search.forceActiveFocus(); }
    function desktopTab() { selectTab("desktop"); }
    function numberedTab(index) { if (index < tabs.length) selectTab(tabs[index].id); }
    function selectTool(index) {
        if (!currentTab.terminal || index >= tools.length) return;
        toolId = tools[index].id; category = "All shortcuts"; list.contentY = 0;
        toolList.positionViewAtIndex(index, ListView.Contain);
    }
    function selectScope(value) {
        scope = value;
        selectTab(scope === "installed" ? "installed" : (context.selected || "desktop"));
    }
    function selectTab(id) {
        tabId = id; toolId = "auto"; category = "All shortcuts"; list.contentY = 0;
        Qt.callLater(() => {
            const index = tabs.findIndex(t => t.id === tabId);
            if (index >= 0) tabList.positionViewAtIndex(index, ListView.Contain);
        });
    }
    function cycleTab(delta) {
        const index = tabs.findIndex(t => t.id === tabId);
        selectTab(tabs[(index + delta + tabs.length) % tabs.length].id);
        tabList.positionViewAtIndex((index + delta + tabs.length) % tabs.length, ListView.Contain);
    }
    onContextChanged: {
        selectScope(scope);
    }
    onCategoriesChanged: if (!categories.includes(category)) category = "All shortcuts"
    function rebuild() {
        entries.clear();
        filtered.forEach(row => entries.append(Object.assign({ source: "" }, row)));
    }
    onFilteredChanged: rebuild()
    Component.onCompleted: { selectTab(context.selected || "desktop"); rebuild(); }
    RowLayout {
        Label { text: "Keyboard shortcuts"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        ActionButton {
            text: "This workspace"; selected: root.scope === "workspace"; Accessible.selected: selected
            showShortcut: true; hintShortcut: "Alt+W"
            onClicked: root.selectScope("workspace")
        }
        ActionButton {
            text: "All installed"; selected: root.scope === "installed"; Accessible.selected: selected
            showShortcut: true; hintShortcut: "Alt+A"
            onClicked: root.selectScope("installed")
        }
        ActionButton {
            text: "Refresh"; hint: "Refresh this workspace's shortcut reference"
            showShortcut: true; hintShortcut: "Alt+R"
            onClicked: shell.refreshBindings()
        }
        Label { text: "SUPER + F1"; color: Theme.good; font.pixelSize: 10; font.letterSpacing: 1.2 }
    }
    ListView {
        id: tabList
        objectName: "shortcut-tabs"
        Layout.fillWidth: true; Layout.preferredHeight: 38
        orientation: ListView.Horizontal; spacing: 6; clip: true
        model: root.tabs
        delegate: ActionButton {
            required property var modelData
            required property int index
            objectName: "shortcut-tab-" + modelData.id
            text: modelData.label
            showShortcut: true
            hintShortcut: modelData.id === "desktop" ? "Alt+D" : index < 9 ? "Alt+" + (index + 1) : ""
            selected: root.currentTab.id === modelData.id
            Accessible.name: modelData.label + " shortcuts tab"
            Accessible.selected: selected
            onClicked: root.selectTab(modelData.id)
            Keys.onRightPressed: Focus.row(tabList, index + 1)
            Keys.onLeftPressed: Focus.row(tabList, index - 1)
        }
    }
    RowLayout {
        visible: root.currentTab.terminal
        Layout.fillWidth: true
        Label { text: "Terminal tools"; font.pixelSize: 11; color: Theme.muted }
        ListView {
            id: toolList
            Layout.fillWidth: true; Layout.preferredHeight: 34
            orientation: ListView.Horizontal; spacing: 4; clip: true
            model: root.tools
            delegate: ActionButton {
                required property var modelData
                required property int index
                text: modelData.label; implicitHeight: 30
                showShortcut: true; hintShortcut: index < 9 ? "Alt+Shift+" + (index + 1) : ""
                selected: root.toolId === modelData.id
                Accessible.selected: selected
                onClicked: root.selectTool(index)
                Keys.onRightPressed: Focus.row(toolList, index + 1)
                Keys.onLeftPressed: Focus.row(toolList, index - 1)
            }
        }
    }
    Label {
        Layout.fillWidth: true
        text: root.note; wrapMode: Text.WordWrap; elide: Text.ElideNone
        font.pixelSize: 11; color: Theme.muted
    }
    RowLayout {
        Layout.fillWidth: true
        SearchField {
            id: search; Layout.fillWidth: true; placeholderText: "Search shortcuts, actions or categories…"; focus: true
            objectName: "shortcut-search"
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
        Label { text: "Alt+S"; color: Theme.good; font.family: Theme.mono; font.pixelSize: 10 }
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
            objectName: "shortcut-rows"
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
                required property string source
                width: list.width; height: Math.max(44, keyText.implicitHeight + 16, rowDetails.implicitHeight + 12); spacing: 16
                Rectangle {
                    Layout.preferredWidth: 240; Layout.preferredHeight: keyText.implicitHeight + 12
                    radius: 6; color: Theme.background
                    Label {
                        id: keyText
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10; topMargin: 6; bottomMargin: 6 }
                        text: bindingRow.key; font.family: Theme.mono; font.pixelSize: 12; color: Theme.good
                        wrapMode: Text.Wrap; elide: Text.ElideNone
                    }
                }
                ColumnLayout {
                    id: rowDetails
                    Layout.fillWidth: true; spacing: 3
                    Label { Layout.fillWidth: true; text: bindingRow.description; font.pixelSize: 13; wrapMode: Text.WordWrap; elide: Text.ElideNone }
                    Label {
                        Layout.fillWidth: true; visible: !!text
                        text: [bindingRow.context, bindingRow.source].filter(s => !!s).join("\u2003")
                        color: Theme.muted; font.pixelSize: 10; wrapMode: Text.Wrap; elide: Text.ElideNone
                    }
                }
            }
            Label { anchors.centerIn: parent; visible: list.count === 0; text: "No matching shortcuts"; color: Theme.muted }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: root.filtered.length + " shortcuts\u2003\u2003Reference only"; font.pixelSize: 11; color: Theme.muted; Layout.fillWidth: true }
        Label { text: "Ctrl+Tab / Ctrl+Shift+Tab   Cycle tabs"; font.pixelSize: 10; color: Theme.good }
    }
    Shortcut { sequence: "Ctrl+Tab"; onActivated: root.cycleTab(1) }
    Shortcut { sequence: "Ctrl+Shift+Tab"; onActivated: root.cycleTab(-1) }
    Shortcut { sequence: "Alt+D"; onActivated: root.desktopTab() }
    Shortcut { sequence: "Alt+W"; onActivated: root.selectScope("workspace") }
    Shortcut { sequence: "Alt+A"; onActivated: root.selectScope("installed") }
    Shortcut { sequence: "Alt+S"; onActivated: root.focusInitial() }
    Shortcut { sequence: "Alt+R"; autoRepeat: false; onActivated: shell.refreshBindings() }
    Repeater {
        model: 9
        delegate: Item {
            required property int index
            visible: false
            Shortcut { sequence: "Alt+" + (index + 1); enabled: index < root.tabs.length; onActivated: root.numberedTab(index) }
            Shortcut {
                sequence: "Alt+Shift+" + (index + 1)
                enabled: root.currentTab.terminal && index < root.tools.length
                onActivated: root.selectTool(index)
            }
        }
    }
}
