import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "." as Atelier

ShellRoot {
    TextMetrics { id: inkMetrics }
    QtObject {
        id: fakeShell
        property string panel: ""
        property bool networkBusy: false
        property string message: ""
        property string lastAction: ""
        property string lastTarget: ""
        property var networks: ({ items: [], vpns: [], proton: true })
        property var state: ({
            audio: { percent: 1, muted: false },
            network: { kind: "ethernet", label: "Wired connection 1", vpn: "", wifi: false, signal: null, address: "192.0.2.1" },
            bluetooth: { powered: true, connected: [] },
            awake: { class: "deactivated", tooltip: "Allow idle sleep" },
            battery: []
        })
        property QtObject notificationService: QtObject {
            property bool dnd: false
            property var history: []
        }
        function send(action, extra) { lastAction = action; lastTarget = extra ? extra.target || "" : ""; }
        function open(name, output) { panel = name; }
        function close() { panel = ""; }
    }
    PanelWindow {
        id: bar
        anchors { bottom: true; left: true; right: true }
        implicitHeight: 40
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "atelier-controls-test"
        color: Atelier.Theme.background
        Atelier.BarControls {
            id: controls
            shell: fakeShell
            output: bar.screen
            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
            dateTime: new Date(2026, 0, 1, 1, 11)
        }
        Atelier.NetworkPanel { id: connectivity; shell: fakeShell; visible: false; width: 420; height: 650 }
    }
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
        function sample(volume: int, muted: bool, vpnEnabled: bool): void {
            const next = JSON.parse(JSON.stringify(fakeShell.state));
            next.audio = { percent: volume, muted: muted };
            next.network.vpn = vpnEnabled ? "Example VPN" : "";
            next.bluetooth.connected = vpnEnabled ? ["Headphones"] : [];
            fakeShell.state = next;
            controls.dateTime = new Date(2026, 8, 28, 23, 58);
        }
        function status(): string {
            const names = ["volume-control", "network-control", "keep-awake-control",
                           "notifications-control", "clock-control", "power-control"];
            const items = names.map(name => {
                const item = find(controls, name);
                const label = find(item.contentItem, "button-label");
                const point = item.mapToGlobal(0, 0);
                inkMetrics.font = label ? label.font : item.contentItem.font;
                inkMetrics.text = item.text;
                const ink = inkMetrics.tightBoundingRect;
                const renderedPosition = (label || item.contentItem).mapToItem(item, 0, 0);
                const inkLeft = renderedPosition.x + (label ? 0 : (item.contentItem.width - inkMetrics.advanceWidth) / 2) + ink.x;
                return { name: name, x: point.x, width: item.width, text: item.text,
                    selected: item.selected,
                    naturalWidth: item.contentItem.implicitWidth + item.horizontalPadding * 2,
                    leftPadding: item.leftPadding, rightPadding: item.rightPadding,
                    contentX: item.contentItem.x, contentWidth: item.contentItem.width,
                    inkLeft: inkLeft, inkRight: item.width - inkLeft - ink.width,
                    labelLeft: label ? label.x : 0,
                    labelRight: label ? label.x + label.width : item.contentItem.width };
            });
            return JSON.stringify({ viewportWidth: bar.width, items: items, vpn: controls.vpn,
                networkCaption: controls.networkCaption, networkHint: find(controls, "network-control").hint,
                bluetoothOnBar: !!find(controls, "bluetooth-control"),
                bluetoothInMenu: !!find(connectivity, "bluetooth-action"), castInMenu: !!find(connectivity, "cast-action"),
                lastAction: fakeShell.lastAction, lastTarget: fakeShell.lastTarget, panel: fakeShell.panel,
                castOnBar: !!find(controls, "cast-action") });
        }
        function invokeMenu(name: string): void { fakeShell.panel = "network"; find(connectivity, name).clicked(); }
        function notifications(count: int, dnd: bool): void {
            fakeShell.notificationService.history = Array(count).fill({ summary: "Test notification" });
            fakeShell.notificationService.dnd = dnd;
        }
        function transport(kind: string): void {
            const next = JSON.parse(JSON.stringify(fakeShell.state));
            next.network.kind = kind;
            next.network.label = kind === "wifi" ? "Wireless test" : "Wired connection 1";
            fakeShell.state = next;
        }
    }
}
