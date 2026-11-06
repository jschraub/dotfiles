import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "." as Atelier

ShellRoot {
    TestEvent { id: events }
    QtObject {
        id: fakeShell
        property string panel: ""
        property var notificationService: null
        property var state: ({ audio: { percent: 50, muted: false }, battery: [] })
        property int actualVolume: 50
        property var requests: []
        property int rawWheels: 0
        function send(action, extra) {
            requests = requests.concat([{ action: action, args: extra }]);
            if (action === "volume") actualVolume = extra.percent;
            if (action === "volume-step") actualVolume = Math.max(0, Math.min(100, actualVolume + extra.delta));
            // Deliberately do not update state.audio: compositor/backend status
            // refreshes are asynchronous, and rapid wheel events must still add.
        }
        function open(name, output) { panel = name; }
        function close() {}
    }
    PanelWindow {
        id: window
        anchors { bottom: true; left: true; right: true }
        implicitHeight: 300
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "atelier-volume-wheel-test"
        WlrLayershell.layer: WlrLayer.Overlay
        color: Atelier.Theme.panel
        Atelier.BarControls { id: bar; shell: fakeShell; output: window.screen; anchors.right: parent.right }
        Atelier.AudioPanel { id: audio; shell: fakeShell; x: 20; y: 50; width: 400; height: 230 }
        MouseArea { id: probe; x: 500; y: 50; width: 100; height: 100; onWheel: fakeShell.rawWheels++ }
    }
    function find(item, name) {
        if (item.objectName === name || item.toString().indexOf(name) >= 0) return item;
        for (const child of item.children || []) {
            const found = find(child, name);
            if (found) return found;
        }
        return null;
    }
    IpcHandler {
        target: "test"
        function reset(value: int): void {
            fakeShell.actualVolume = value;
            fakeShell.requests = [];
            fakeShell.state = { audio: { percent: value, muted: false }, battery: [] };
            for (const item of [bar, audio]) {
                const area = find(item, "volume-wheel");
                if (area) { area.angleRemainder = 0; area.pixelRemainder = 0; }
            }
        }
        function wheel(source: string, delta: int, count: int): bool {
            const item = source === "probe" ? probe : source === "bar" ? find(bar, "volume-control") : find(audio, "Slider");
            let success = true;
            for (let i = 0; i < count; i++) {
                success = events.mouseWheel(item, item.width / 2, item.height / 2,
                    Qt.NoButton, Qt.NoModifier, 0, delta, 0) && success;
            }
            return success;
        }
        function status(): string {
            const slider = find(audio, "Slider");
            const area = find(slider, "volume-wheel");
            const point = slider.mapToItem(window.contentItem, 0, 0);
            return JSON.stringify({ width: window.width, volume: fakeShell.actualVolume, panel: fakeShell.panel,
                requests: fakeShell.requests, rotation: find(bar, "volume-control").rotation, rawWheels: fakeShell.rawWheels,
                slider: { x: point.x, y: point.y, width: slider.width, height: slider.height,
                    areaWidth: area ? area.width : null, areaHeight: area ? area.height : null, areaEnabled: area ? area.enabled : false } });
        }
        function pixels(source: string, delta: int, count: int): void {
            const area = find(source === "bar" ? bar : audio, "volume-wheel");
            for (let i = 0; i < count; i++) area.consume(0, delta);
        }
        function clickAudio(): bool {
            const item = find(bar, "volume-control");
            return events.mouseClick(item, item.width / 2, item.height / 2, Qt.LeftButton, Qt.NoModifier, 0);
        }
        function dragSlider(): bool {
            const item = find(audio, "Slider");
            const start = item.leftPadding + item.visualPosition * (item.availableWidth - item.handle.width) + item.handle.width / 2;
            const end = item.leftPadding + item.availableWidth * 0.8;
            return events.mousePress(item, start, item.height / 2, Qt.LeftButton, Qt.NoModifier, 0)
                && events.mouseMove(item, end, item.height / 2, 1, Qt.LeftButton, Qt.NoModifier)
                && events.mouseRelease(item, end, item.height / 2, Qt.LeftButton, Qt.NoModifier, 0);
        }
    }
}
