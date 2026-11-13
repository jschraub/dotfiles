import QtQuick
import Quickshell.Io

QtObject {
    id: root
    // A QML reload discards RAM history; the runtime pause flag is preserved.
    property bool opened: false
    property bool ready: false
    property bool paused: false
    property bool busy: false
    property int count: 0
    property int expirySeconds: 0
    property var items: []
    property string query: ""
    property string message: ""
    property bool started: false
    signal copied()
    function send(action, extra) {
        if (started) worker.write(JSON.stringify(Object.assign({ action: action }, extra || {})) + "\n");
    }
    function search(value) { query = value; if (opened) send("list", { query: query }); }
    function copy(id) { if (started && !busy && id) { busy = true; send("copy", { id: id }); } }
    function remove(id) { if (started && !busy && id) send("delete", { id: id }); }
    function clear() { if (started && !busy) send("clear"); }
    function togglePaused() { if (started) send("pause", { paused: !paused }); }
    function setExpiry(seconds) { if (started && !busy) send("expiry", { seconds: seconds }); }
    function receive(line) {
        try {
            const event = JSON.parse(line), data = event.data;
            ready = !!data.ready; paused = !!data.paused; count = data.count || 0;
            expirySeconds = data.expirySeconds || 0;
            items = opened ? data.items || [] : [];
            message = data.message || "";
            if (event.type === "copied") { busy = false; copied(); }
            if (message) busy = false;
        } catch (error) { message = "Clipboard connection returned invalid data."; }
    }
    onOpenedChanged: {
        query = ""; items = [];
        send(opened ? "list" : "hide", opened ? { query: "" } : {});
    }
    property Process worker: Process {
        command: ["python3", "-B", Qt.resolvedUrl("clipboard.py").toString().replace("file://", ""), "serve"]
        stdinEnabled: true
        running: true
        stdout: SplitParser { onRead: line => root.receive(line) }
        // Never mirror protocol bodies or exception lines into shell logs.
        stderr: SplitParser { onRead: root.message = "Clipboard service encountered an error." }
        onStarted: {
            root.started = true;
            root.send(root.opened ? "list" : "hide", root.opened ? { query: root.query } : {});
        }
        onExited: {
            root.started = false; root.ready = false; root.busy = false;
            root.items = []; root.count = 0;
            root.message = "Clipboard service stopped. History was discarded; reconnecting…";
            restart.restart();
        }
    }
    property Timer restart: Timer { interval: 2000; onTriggered: worker.running = true }
}
