import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root
    readonly property bool preview: Quickshell.env("ATELIER_PREVIEW") === "1"
    readonly property bool testing: Quickshell.env("ATELIER_TEST") === "1"
    property var state: ({})
    property var apps: []
    property var bindings: []
    property var networks: ({ items: [], vpns: [], proton: false })
    property string panel: ""
    property string message: ""
    property bool networkBusy: false
    property var chosenScreen: null
    property var menuScreen: chosenScreen && Quickshell.screens.indexOf(chosenScreen) >= 0
                             ? chosenScreen : focusedScreen()
    property var notificationService: notifications.item
    property bool ready: false
    property var pending: []

    function focusedScreen() {
        const monitors = state.monitors || [];
        const monitor = monitors.find(m => m.focused);
        return Quickshell.screens.find(s => monitor && s.name === monitor.name) || Quickshell.screens[0] || null;
    }
    function send(action, extra) {
        const request = Object.assign({ action: action }, extra || {});
        if (backend.running) backend.write(JSON.stringify(request) + "\n");
        else pending = pending.concat([request]);
    }
    function open(name, output) {
        chosenScreen = output || focusedScreen();
        panel = panel === name ? "" : name;
        message = "";
        if (panel === "launcher") send("apps");
        if (panel === "bindings") send("bindings");
        if (panel === "network") send("networks");
    }
    function close() { panel = ""; message = ""; }
    function receive(line) {
        try {
            const event = JSON.parse(line);
            switch (event.type) {
            case "state": state = event.data; ready = true; break;
            case "apps": apps = event.data; break;
            case "bindings": bindings = event.data; break;
            case "networks": networks = event.data; break;
            case "notice": message = event.data; break;
            case "result":
                if (["connect", "rescan", "wifi", "vpn"].includes(event.data.action)) networkBusy = false;
                if (!event.data.ok) message = event.data.message;
                else {
                    if (["connect", "rescan", "wifi", "vpn"].includes(event.data.action)) message = "";
                    if (event.data.action === "wifi") send("networks");
                    if (event.data.action === "launch") close();
                }
                break;
            }
        } catch (error) { console.warn("Atelier received invalid backend data"); }
    }
    IpcHandler {
        target: "shell"
        function toggle(name: string): void {
            if (["launcher", "bindings", "audio", "network", "calendar", "notifications", "power"].includes(name)) root.open(name);
        }
        function close(): void { root.close(); }
        function health(): string { return root.ready ? "ready" : "starting"; }
        function status(): string {
            const rect = menu.cardGeometry;
            return JSON.stringify({ panel: root.panel, ready: root.ready, preview: root.preview,
                monitor: root.menuScreen ? root.menuScreen.name : "", geometry: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } });
        }
    }
    Process {
        id: backend
        command: ["python3", "-B", Qt.resolvedUrl("backend.py").toString().replace("file://", "")]
        stdinEnabled: true
        running: true
        stdout: SplitParser { onRead: line => root.receive(line) }
        stderr: SplitParser { onRead: line => console.warn("Atelier backend: " + line) }
        onStarted: {
            root.pending.forEach(request => backend.write(JSON.stringify(request) + "\n"));
            root.pending = [];
        }
        onExited: {
            root.ready = false;
            root.message = "System connection interrupted. Retrying…";
            restartBackend.restart();
        }
    }
    Timer { id: restartBackend; interval: 2000; onTriggered: backend.running = true }
    Variants {
        model: root.testing ? [] : Quickshell.screens
        Bar {
            required property var modelData
            screen: modelData
            shell: root
        }
    }
    MenuWindow { id: menu; shell: root }
    Loader {
        id: notifications
        active: !root.preview && !root.testing
        sourceComponent: Component { NotificationService { shell: root } }
    }
}
