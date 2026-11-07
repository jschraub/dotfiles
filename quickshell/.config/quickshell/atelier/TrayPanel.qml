import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell

ColumnLayout {
    id: root
    required property var shell
    property var service: shell.desktopServices || null
    property var currentMenu: null
    property var breadcrumbs: []
    readonly property var menuEntries: opener.children.values
    readonly property int panelHeight: 470
    spacing: 10
    QsMenuOpener { id: opener; menu: root.currentMenu }
    // Menu entries belong to their parent's opener. Keep every ancestor open
    // while drilling down, or switching openers can destroy the submenu handle.
    Item {
        visible: false
        Repeater {
            model: root.breadcrumbs
            Item {
                required property var modelData
                QsMenuOpener { menu: modelData }
            }
        }
    }
    Label { text: "System tray"; font.pixelSize: 22; font.weight: Font.DemiBold }
    ActionButton {
        visible: !!root.currentMenu
        text: "‹  Back"
        onClicked: { root.currentMenu = root.breadcrumbs.length ? root.breadcrumbs[root.breadcrumbs.length - 1] : null; root.breadcrumbs = root.breadcrumbs.slice(0, -1); }
    }
    ListView {
        id: list; Layout.fillWidth: true; Layout.fillHeight: true
        model: root.currentMenu ? [] : (root.service ? root.service.trayItems : [])
        visible: !root.currentMenu; spacing: 6; clip: true
        Controls.ScrollBar.vertical: ScrollHandle {}
        delegate: RowLayout {
            required property var modelData
            width: list.width; height: 44
            Image { source: modelData.icon; sourceSize.width: 22; sourceSize.height: 22; width: 22; height: 22; fillMode: Image.PreserveAspectFit }
            ActionButton {
                objectName: "tray-activate-" + modelData.id
                Layout.fillWidth: true; alignLeft: true
                text: modelData.title || modelData.id
                hint: modelData.tooltipTitle + (modelData.tooltipDescription ? "\n" + modelData.tooltipDescription : "")
                onClicked: {
                    if (modelData.onlyMenu && modelData.hasMenu) root.currentMenu = modelData.menu;
                    else { modelData.activate(); shell.close(); }
                }
            }
            ActionButton { objectName: "tray-menu-" + modelData.id; text: "⋯"; visible: modelData.hasMenu; hint: "Application menu"; onClicked: root.currentMenu = modelData.menu }
        }
        Label { anchors.centerIn: parent; visible: list.count === 0; text: "No tray applications"; color: Theme.muted }
    }
    ListView {
        id: entries; Layout.fillWidth: true; Layout.fillHeight: true
        visible: !!root.currentMenu; model: opener.children; spacing: 4; clip: true
        Controls.ScrollBar.vertical: ScrollHandle {}
        delegate: Column {
            required property var modelData
            required property int index
            width: entries.width
            Rectangle { visible: modelData.isSeparator; width: parent.width; height: 1; color: Theme.line }
            ActionButton {
                objectName: "tray-entry-" + index
                width: parent.width; visible: !modelData.isSeparator; enabled: modelData.enabled; alignLeft: true
                text: (modelData.checkState === Qt.Checked ? "✓  " : "") + modelData.text.replace(/&/g, "") + (modelData.hasChildren ? "  ›" : "")
                onClicked: {
                    if (modelData.hasChildren) { root.breadcrumbs = root.breadcrumbs.concat([root.currentMenu]); root.currentMenu = modelData; }
                    else { modelData.triggered(); shell.close(); }
                }
            }
        }
    }
}
