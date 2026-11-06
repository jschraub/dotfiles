import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "." as Atelier

ShellRoot {
    PanelWindow {
        id: bar
        anchors { top: true; left: true; right: true }
        implicitHeight: 40
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "atelier-tooltip-test"
        color: Atelier.Theme.background
        Atelier.ActionButton {
            id: button
            x: 16; y: 3; width: 200; height: 34
            text: "Tooltip anchor test"
            hint: "A hint below its button"
        }
    }
    IpcHandler {
        target: "test"
        function status(): string {
            const buttonPosition = button.mapToGlobal(0, 0);
            const tip = button.data.find(o => o.contentItem &&
                (o.toString().indexOf("ToolTip") >= 0 || o.objectName === "atelier-tooltip"));
            const tipPosition = tip ? tip.contentItem.mapToGlobal(0, 0) : Qt.point(0, 0);
            return JSON.stringify({ hovered: button.hovered, shown: !!tip && tip.visible,
                button: { x: buttonPosition.x, y: buttonPosition.y, width: button.width, height: button.height },
                tooltip: { x: tipPosition.x, y: tipPosition.y },
                objects: button.data.map(o => o.toString()) });
        }
    }
}
