import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "power-panel"
    required property var shell
    readonly property int panelHeight: 340
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
                id: actionButton
                required property var modelData
                required property int index
                objectName: "power-" + modelData.id
                Layout.fillWidth: true; implicitHeight: 50
                text: modelData.text + "  [" + modelData.key + "]"
                contentItem: RowLayout {
                    spacing: 10
                    Item { Layout.fillWidth: true }
                    Label { text: actionButton.modelData.text }
                    Label {
                        objectName: "power-shortcut-" + actionButton.modelData.id
                        text: actionButton.modelData.key
                        font.family: Theme.mono; font.pixelSize: 12; color: Theme.good
                    }
                    Item { Layout.fillWidth: true }
                }
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
                    enabled: root.visible && root.shell.panel === "power"
                    autoRepeat: false
                    onActivated: root.choose(modelData.id)
                }
            }
        }
    }
    Label {
        text: "<font color='" + Theme.good + "'>Arrows / Tab</font> to move&emsp;&emsp;<font color='" + Theme.good
            + "'>Enter</font> to select&emsp;&emsp;<font color='" + Theme.good + "'>Esc</font> to close"
        textFormat: Text.RichText
        font.pixelSize: 11; color: Theme.muted
    }
    function focusAction(index) { if (actions.itemAt(index)) actions.itemAt(index).forceActiveFocus(Qt.TabFocusReason); }
    function focusInitial() { focusAction(0); }
    function move(index, dx, dy) {
        focusAction(((Math.floor(index / 2) + dy + 2) % 2) * 2 + (index % 2 + dx + 2) % 2);
    }
    function choose(id) {
        if (shell.panel !== "power" || !actionsModel.some(action => action.id === id)) return;
        shell.send("power", { choice: id });
        shell.close();
    }
}
