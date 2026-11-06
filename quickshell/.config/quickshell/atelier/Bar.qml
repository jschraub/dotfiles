import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: bar
    required property var shell
    anchors { left: true; right: true; top: !shell.preview; bottom: shell.preview }
    implicitHeight: Theme.barHeight
    exclusiveZone: shell.preview ? 0 : Theme.barHeight
    color: Theme.background
    WlrLayershell.namespace: "atelier-bar"
    property var monitor: (shell.state.monitors || []).find(m => m.name === screen.name) || ({})
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
    RowLayout {
        id: left
        anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
        spacing: 10
        ActionButton {
            text: shell.preview ? "▦  Atelier · preview" : "▦  Applications"
            selected: shell.panel === "launcher"
            hint: "Applications · Super+Space"
            onClicked: shell.open("launcher", bar.screen)
        }
        Rectangle { width: 1; height: 16; color: Theme.line }
        Row {
            spacing: 3
            Repeater {
                model: {
                    const occupied = (shell.state.workspaces || []).filter(w => w.id > 0 && w.monitor === bar.screen.name).map(w => w.id);
                    const current = bar.monitor.activeWorkspace ? bar.monitor.activeWorkspace.id : 1;
                    return Array.from(new Set([1, 2, 3, 4, 5].concat(occupied, [current]))).sort((a, b) => a - b);
                }
                ActionButton {
                    id: workspaceButton
                    required property var modelData
                    readonly property var workspace: (shell.state.workspaces || []).find(
                        w => w.id === modelData && w.monitor === bar.screen.name)
                    readonly property int windowCount: workspace ? (workspace.windows || 0) : 0
                    objectName: "workspace-" + modelData
                    horizontalPadding: 4
                    implicitWidth: Math.max(28, contentItem.implicitWidth + horizontalPadding * 2)
                    implicitHeight: 28
                    selected: !!bar.monitor.activeWorkspace && bar.monitor.activeWorkspace.id === modelData
                    textColor: windowCount > 0 ? Theme.accent : Theme.muted
                    text: String(modelData)
                    hint: "Workspace " + modelData + " · " + (windowCount === 0 ? "Empty"
                        : windowCount + (windowCount === 1 ? " window" : " windows"))
                    background: Rectangle {
                        radius: 7
                        color: workspaceButton.down ? Theme.hover
                            : workspaceButton.selected || workspaceButton.hovered || workspaceButton.visualFocus ? Theme.raised : "transparent"
                        // Selected workspace is outlined even without button focus.
                        // Keyboard focus remains visible; mouse focus alone doesn't
                        // leave a stale outline on a previously selected workspace.
                        border.width: workspaceButton.selected || workspaceButton.visualFocus ? 1 : 0
                        border.color: Theme.accent
                    }
                    onClicked: shell.send("workspace", { number: modelData })
                }
            }
        }
    }
    Label {
        anchors { left: left.right; right: right.left; leftMargin: 24; rightMargin: 24; verticalCenter: parent.verticalCenter }
        horizontalAlignment: Text.AlignHCenter
        font.pixelSize: 12
        color: Theme.muted
        text: shell.state.window ? (shell.state.window.title || "Atelier") : "Connecting…"
    }
    BarControls {
        id: right
        anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
        shell: bar.shell
        output: bar.screen
        compact: bar.width < 1400
        dateTime: clock.date
    }
    SystemClock { id: clock; precision: SystemClock.Minutes }
}
