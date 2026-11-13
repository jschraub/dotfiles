import QtQuick
import Quickshell
import Quickshell.Io
import "." as Atelier

ShellRoot {
    TextMetrics { id: metrics }
    QtObject {
        id: fakeShell
        property var output: Quickshell.screens[0]
        property bool preview: true
        property string panel: ""
        property var notificationService: null
        property var state: ({
            monitors: [{ name: output.name, activeWorkspace: { id: 1 } }],
            workspaces: [{ id: 11, monitor: output.name, windows: 2 },
                         { id: 101, monitor: output.name, windows: 0 },
                         { id: 3, monitor: "another-output", windows: 4 }],
            window: { title: "Workspace geometry test" },
            audio: { percent: 50, muted: false }, battery: [],
            awake: { class: "deactivated", tooltip: "Allow idle sleep" }
        })
        function send(action, extra) {}
        function open(name, output) {}
    }
    Atelier.Bar { id: bar; screen: fakeShell.output; shell: fakeShell }
    function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) {
            const found = find(child, name);
            if (found) return found;
        }
        return null;
    }
    IpcHandler {
        target: "test"
        function sample(current: int, windows: int): void {
            const next = JSON.parse(JSON.stringify(fakeShell.state));
            next.monitors[0].activeWorkspace.id = current;
            next.workspaces[0].windows = windows;
            fakeShell.state = next;
        }
        function preview(enabled: bool): void { fakeShell.preview = enabled; }
        function status(): string {
            const applications = find(bar.contentItem, "applications-control");
            const combined = find(applications.contentItem, "button-label");
            const icon = find(applications.contentItem, "applications-icon") || combined;
            const caption = find(applications.contentItem, "applications-caption") || combined;
            function inkCenter(label, text) {
                metrics.font = label.font; metrics.text = text;
                const ink = metrics.tightBoundingRect;
                return label.mapToItem(applications, 0, 0).y + label.baselineOffset + ink.y + ink.height / 2;
            }
            const applicationGeometry = { height: applications.height, iconCenter: inkCenter(icon, "▦"),
                captionCenter: inkCenter(caption, fakeShell.preview ? "Atelier\u2003Preview" : "Applications"),
                leftPadding: applications.leftPadding, rightPadding: applications.rightPadding };
            metrics.font = icon.font; metrics.text = "▦";
            const iconBounds = { x: metrics.tightBoundingRect.x, width: metrics.tightBoundingRect.width };
            const iconPosition = icon.mapToItem(applications, 0, 0);
            applicationGeometry.inkLeft = iconPosition.x + iconBounds.x;
            metrics.font = caption.font; metrics.text = caption.text;
            const captionBounds = metrics.tightBoundingRect;
            const captionPosition = caption.mapToItem(applications, 0, 0);
            applicationGeometry.inkRight = applications.width - captionPosition.x - captionBounds.x - captionBounds.width;
            applicationGeometry.gap = captionPosition.x + captionBounds.x - iconPosition.x - iconBounds.x - iconBounds.width;
            const entries = [1, 2, 3, 4, 5, 11, 101].map(number => {
                const button = find(bar.contentItem, "workspace-" + number);
                const label = find(button.contentItem, "button-label");
                metrics.font = label.font;
                metrics.text = button.text;
                const position = label.mapToItem(button, 0, 0);
                const left = position.x + metrics.tightBoundingRect.x;
                return { number: number, width: button.width, contentWidth: button.contentItem.width,
                    selected: button.selected, textColor: label.color.toString(),
                    background: button.background.color.toString(), outline: button.background.border.width,
                    hovered: button.hovered, visualFocus: button.visualFocus,
                    requiredContentWidth: button.contentItem.implicitWidth, labelWidth: label.width,
                    advance: metrics.advanceWidth, inkLeft: left,
                    inkRight: button.width - left - metrics.tightBoundingRect.width };
            });
            return JSON.stringify({ width: bar.width, entries: entries, applications: applicationGeometry,
                accent: Atelier.Theme.accent.toString(), muted: Atelier.Theme.muted.toString(), raised: Atelier.Theme.raised.toString() });
        }
    }
}
