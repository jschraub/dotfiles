import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "." as Atelier
import "Focus.js" as Focus

ShellRoot {
    QtObject {
        id: service
        property var outputs: Array.from({ length: 40 }, (_, i) => ({ id: i, description: "Output device " + i }))
        property var inputs: [{ id: 100, description: "Microphone" }]
        property var defaultOutput: outputs[0]
        property var defaultInput: inputs[0]
        property var players: []
        property var trayItems: []
        function setDefault(device, input) { if (input) defaultInput = device; else defaultOutput = device; }
    }
    QtObject {
        id: fakeShell
        property string panel: "audio"
        property bool preview: false
        property bool testing: false
        property string message: ""
        property bool networkBusy: false
        property var menuScreen: Quickshell.screens[0]
        property var desktopServices: service
        property var notificationService: null
        property var clipboardService: null
        property var bindings: []
        property var apps: Array.from({ length: 50 }, (_, i) => ({
            id: "app-" + i, name: "Application " + i, description: "Fixture application", keywords: "fixture", icon: "application-x-executable"
        }))
        property var networks: ({ items: Array.from({ length: 40 }, (_, i) => ({
            ssid: "Network " + i, security: "WPA2", signal: 80, connected: i === 0, uuid: "network-" + i
        })), vpns: [], proton: false })
        property var state: ({ audio: { percent: 40, muted: false }, microphone: { percent: 50, muted: false },
            network: { wifi: true, kind: "wifi", label: "Network 0", signal: 80, vpn: "", address: "192.0.2.1" },
            awake: { class: "deactivated", tooltip: "Keep awake: off" }, bluetooth: null })
        function open(name, screen) { panel = name; }
        function close() { panel = ""; }
        function send(action, extra) {
            if (action === "volume") {
                const next = JSON.parse(JSON.stringify(state)); next.audio.percent = extra.percent; state = next;
            }
        }
    }
    Atelier.MenuWindow { id: menu; shell: fakeShell; anchors.bottom: false; implicitHeight: 760 }
    Item {
        parent: menu.contentItem
        TestEvent { id: events }
        Atelier.ActionButton {
            id: probe
            objectName: "probe"
            x: 8; y: 8
            text: "Delete"; dangerous: true
            property int activations: 0
            hint: "Destructive action description"
            onClicked: activations++
        }
        Atelier.BarControls { id: bar; visible: false; shell: fakeShell; output: menu.screen }
    }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    function label(item) { return item ? item.objectName || item.Accessible.name || item.text || "unnamed" : "none"; }
    function fullyVisible(item) {
        if (!item) return false;
        for (let parent = item.parent; parent; parent = parent.parent) {
            if (typeof parent.contentY !== "number" || !parent.contentItem) continue;
            const point = item.mapToItem(parent.contentItem, 0, 0);
            if (point.y < parent.contentY - 1 || point.y + item.height > parent.contentY + parent.height + 1) return false;
        }
        return true;
    }
    IpcHandler {
        target: "test"
        function open(name: string, height: int): void { fakeShell.panel = name; menu.implicitHeight = height + 80; }
        function key(name: string, shift: bool): bool { return events.keyClick(Qt["Key_" + name], shift ? Qt.ShiftModifier : Qt.NoModifier, 0); }
        function focus(name: string, keyboard: bool): bool {
            const item = name === "probe" ? probe : find(menu.contentItem, name);
            if (!item) return false;
            item.forceActiveFocus(keyboard ? Qt.TabFocusReason : Qt.MouseFocusReason); return true;
        }
        function status(): string {
            const active = menu.contentItem.Window.activeFocusItem;
            const card = find(menu.contentItem, "menu-card");
            const viewport = find(menu.contentItem, "menu-viewport");
            const tip = probe.data.find(o => o.objectName === "atelier-tooltip");
            const ring = find(menu.contentItem, "slider-focus-ring");
            return JSON.stringify({ panel: fakeShell.panel, active: label(active), visible: fullyVisible(active),
                focusNames: Focus.controls(card).map(label), visualFocus: active ? !!active.visualFocus : false,
                border: active && active.background ? active.background.border.width : 0,
                tooltip: !!tip && tip.visible, reducedMotion: Atelier.Theme.reducedMotion,
                activations: probe.activations, sliderRing: !!ring && ring.visible,
                danger: String(Atelier.Theme.dangerText), surfaces: [Atelier.Theme.background, Atelier.Theme.panel, Atelier.Theme.raised, Atelier.Theme.hover].map(String),
                names: ["keep-awake-control", "power-control", "notifications-control", "clock-control"].map(name => find(bar, name).Accessible.name),
                viewportHeight: viewport.height, contentHeight: viewport.contentHeight,
                devicePixelRatio: menu.screen.devicePixelRatio });
        }
    }
}
