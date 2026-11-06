import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "power-panel"
    required property var shell
    property string choice: ""
    readonly property int panelHeight: choice ? 430 : 340
    readonly property var actionsModel: [
        { id: "lock", text: "󰌾  Lock", key: "L" }, { id: "logout", text: "󰍃  Log out", key: "E" },
        { id: "reboot", text: "󰜉  Restart", key: "R" }, { id: "shutdown", text: "⏻  Shut down", key: "S" }
    ]
    implicitHeight: 260
    spacing: 12
    Label { text: "Session & power"; font.pixelSize: 22; font.weight: Font.DemiBold }
    Label { text: "Take a break, or call it a day."; color: Theme.muted }
    GridLayout {
        Layout.fillWidth: true; columns: 2; rowSpacing: 8; columnSpacing: 8
        Repeater {
            id: actions
            model: root.actionsModel
            ActionButton {
                required property var modelData
                required property int index
                objectName: "power-" + modelData.id
                Layout.fillWidth: true; implicitHeight: 50
                text: modelData.text + "  [" + modelData.key + "]"; selected: root.choice === modelData.id
                onClicked: root.choose(modelData.id)
                Keys.onLeftPressed: root.move(index, -1, 0)
                Keys.onRightPressed: root.move(index, 1, 0)
                Keys.onUpPressed: root.move(index, 0, -1)
                Keys.onDownPressed: root.move(index, 0, 1)
                Keys.onTabPressed: root.focusAction((index + 1) % 4)
                Keys.onBacktabPressed: root.focusAction((index + 3) % 4)
                Keys.onReturnPressed: event => { if (!event.isAutoRepeat) root.choose(modelData.id); }
                Keys.onEnterPressed: event => { if (!event.isAutoRepeat) root.choose(modelData.id); }
                Shortcut {
                    sequence: modelData.key
                    enabled: root.visible && root.shell.panel === "power" && !root.choice
                    autoRepeat: false
                    onActivated: root.choose(modelData.id)
                }
            }
        }
    }
    Label { text: "Arrows / Tab to move · Enter to select · Esc to close"; font.pixelSize: 11; color: Theme.muted }
    Label { visible: !!root.choice; text: "Confirm " + root.choice + "?"; color: Theme.accent }
    RowLayout {
        visible: !!root.choice
        ActionButton {
            id: cancelButton
            objectName: "power-cancel"
            text: "Cancel"
            onClicked: root.cancelChoice()
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) root.cancelChoice(); }
            Keys.onEnterPressed: event => { if (!event.isAutoRepeat) root.cancelChoice(); }
            KeyNavigation.left: confirmButton
            KeyNavigation.right: confirmButton
            KeyNavigation.up: confirmButton
            KeyNavigation.down: confirmButton
            KeyNavigation.tab: confirmButton
            KeyNavigation.backtab: confirmButton
        }
        Item { Layout.fillWidth: true }
        ActionButton {
            id: confirmButton
            objectName: "power-confirm"
            text: "Confirm"; dangerous: true
            onClicked: root.confirmChoice()
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) root.confirmChoice(); }
            Keys.onEnterPressed: event => { if (!event.isAutoRepeat) root.confirmChoice(); }
            KeyNavigation.left: cancelButton
            KeyNavigation.right: cancelButton
            KeyNavigation.up: cancelButton
            KeyNavigation.down: cancelButton
            KeyNavigation.tab: cancelButton
            KeyNavigation.backtab: cancelButton
        }
    }
    function focusAction(index) { if (actions.itemAt(index)) actions.itemAt(index).forceActiveFocus(Qt.TabFocusReason); }
    function focusInitial() { choice = ""; focusAction(0); }
    function move(index, dx, dy) {
        focusAction(((Math.floor(index / 2) + dy + 2) % 2) * 2 + (index % 2 + dx + 2) % 2);
    }
    function choose(id) {
        if (id === "lock") { shell.send("power", { choice: id }); shell.close(); }
        else {
            choice = id;
            // Destructive choices always start on Cancel, never Confirm.
            Qt.callLater(function() { if (root.choice) cancelButton.forceActiveFocus(Qt.TabFocusReason); });
        }
    }
    function cancelChoice() {
        const index = actionsModel.findIndex(action => action.id === choice);
        choice = "";
        focusAction(Math.max(0, index));
    }
    function confirmChoice() {
        if (!["logout", "reboot", "shutdown"].includes(choice)) return;
        shell.send("power", { choice: choice });
        shell.close();
    }
}
