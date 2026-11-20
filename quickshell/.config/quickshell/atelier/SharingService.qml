import QtQuick
import Quickshell.Io

QtObject {
    id: root
    property var state: ({ devices: [], streams: [], plugins: {} })
    property bool started: false
    property bool busy: false
    property string message: ""
    readonly property var streams: state.streams || []
    readonly property var devices: state.devices || []
    readonly property bool active: streams.length > 0 || !!state.daemonRunning || !!state.networkRunning
    readonly property bool streaming: state.statusKnown !== false && streams.some(s => s.state === "streaming")
    readonly property string label: state.statusKnown === false ? "Sharing status unavailable"
        : streaming ? "AirPlay streaming" : streams.length ? "AirPlay setup" : state.daemonRunning ? "AirPlay discovery" : "Sharing app open"
    function send(action, extra) {
        if (!started) return;
        busy = true;
        worker.write(JSON.stringify(Object.assign({ action: action }, extra || {})) + "\n");
    }
    function configure(encoder, resolution, audio) { send("configure", { encoder: encoder, resolution: resolution, audio: audio }); }
    function respond(target, value) { send("credential", { target: target, value: value }); }
    property Process worker: Process {
        command: ["python3", "-B", Qt.resolvedUrl("sharing.py").toString().replace("file://", ""), "serve"]
        stdinEnabled: true
        running: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const next = JSON.parse(line);
                    // Stable lists preserve keyboard focus during status polling.
                    for (const key of ["devices", "streams"]) {
                        if (JSON.stringify(next[key] || []) === JSON.stringify(root.state[key] || []))
                            next[key] = root.state[key] || [];
                    }
                    root.state = next;
                    root.message = root.state.message || "";
                    root.busy = false;
                } catch (error) { root.message = "Invalid sharing response."; root.busy = false; }
            }
        }
        stderr: SplitParser { onRead: root.message = "Sharing helper failed. No diagnostic payloads are logged." }
        onStarted: root.started = true
        onExited: {
            root.started = false; root.busy = false;
            root.state = ({ devices: [], streams: [], plugins: {} });
            root.message = "Sharing helper stopped. Streams are not automatically reconnected.";
            restart.restart();
        }
    }
    property Timer restart: Timer { interval: 2000; onTriggered: worker.running = true }
}
