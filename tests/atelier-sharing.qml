import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "." as Atelier

ShellRoot {
    QtObject {
        id: service
        property bool busy: false
        property bool accepted: false
        property string lastAction: ""
        property string message: ""
        property var state: ({ airplayAvailable: true, networkAvailable: true, daemonRunning: false,
            networkRunning: false, devices: [], streams: [], encoder: "auto", resolution: "1920x1080", audio: false, plugins: {} })
        readonly property var streams: state.streams
        readonly property var devices: state.devices
        function send(action, extra) {
            lastAction = action;
            const next = JSON.parse(JSON.stringify(state));
            if (action === "discover") {
                next.daemonRunning = true;
                next.devices = [{ name: "Living room", target: "192.0.2.20", port: 7000, identity: "fixture" }];
            } else if (action === "connect") {
                next.streams = [{ name: "Living room", target: "192.0.2.20", state: "pin_required", credentialKind: "pin" }];
            } else if (action === "stop") {
                next.streams = []; next.daemonRunning = false; next.networkRunning = false;
            } else if (action === "network") next.networkRunning = true;
            else if (action === "check") next.plugins = { nvh264enc: true, x264enc: true };
            state = next;
        }
        function configure(encoder, resolution, audio) {
            const next = JSON.parse(JSON.stringify(state));
            next.encoder = encoder; next.resolution = resolution; next.audio = audio; state = next;
        }
        function respond(target, value) {
            accepted = target === "192.0.2.20" && value === "fixture-secret"; lastAction = "credential";
            const next = JSON.parse(JSON.stringify(state));
            next.streams = [{ name: "Living room", target: target, state: "streaming", encoder: "nvh264enc", hardware: true }];
            state = next;
        }
    }
    QtObject {
        id: fakeShell
        property string panel: "sharing"
        property bool testing: false
        property bool preview: false
        property string message: ""
        property var menuScreen: Quickshell.screens[0]
        property var sharingService: service
        function close() { panel = ""; }
    }
    Atelier.MenuWindow { id: menu; shell: fakeShell }
    Item { parent: menu.contentItem; TestEvent { id: events } }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const result = find(child, name); if (result) return result; }
        return null;
    }
    IpcHandler {
        target: "test"
        function click(name: string): bool {
            const button = find(menu.contentItem, name);
            if (!button || !button.enabled) return false;
            button.clicked(); return true;
        }
        function secret(): void { find(menu.contentItem, "sharing-credential").text = "fixture-secret"; }
        function refresh(): void { service.state = JSON.parse(JSON.stringify(service.state)); }
        function key(name: string): bool { return events.keyClick(Qt["Key_" + name], Qt.NoModifier, 0); }
        function status(): string {
            const field = find(menu.contentItem, "sharing-credential");
            const active = menu.contentItem.Window.activeFocusItem;
            return JSON.stringify({ panel: fakeShell.panel, state: service.state, active: active ? active.objectName : "",
                length: field ? field.text.length : 0, protected: !!field && field.echoMode === TextInput.Password,
                accepted: service.accepted, lastAction: service.lastAction });
        }
    }
}
