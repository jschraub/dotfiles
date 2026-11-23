import QtQuick
import Quickshell.Io

QtObject {
    id: root
    property bool active: false
    property bool greeter: false
    property bool allowed: false
    property bool present: false
    property bool ready: false
    property string message: ""
    property int sleepGeneration: 0
    property bool sleeping: false
    signal sleepRequested(int generation)
    function acknowledgeSleep(generation) {
        if (generation > 0 && generation === sleepGeneration && monitor.running)
            monitor.write(JSON.stringify({type: "fingerprint-stopped", generation: generation}) + "\n");
    }
    onActiveChanged: if (!active) { allowed = false; present = false; ready = false; message = ""; }
    property Process monitor: Process {
        command: ["/usr/bin/python3", "-B", "-E", "-s", Qt.resolvedUrl("fingerprint_monitor.py").toString().replace(/^file:\/\//, "")].concat(root.greeter ? ["--greeter"] : [])
        running: root.active
        stdinEnabled: true
        stdout: SplitParser {
            onRead: data => {
                try {
                    const state = JSON.parse(data);
                    root.sleeping = state.sleeping === true;
                    root.allowed = state.allowed === true;
                    root.present = state.present === true;
                    root.ready = state.ready === true;
                    root.message = typeof state.message === "string" ? state.message : "";
                    const generation = Number.isInteger(state.sleepGeneration) ? state.sleepGeneration : 0;
                    if (generation !== root.sleepGeneration) {
                        root.sleepGeneration = generation;
                        if (generation > 0) root.sleepRequested(generation);
                    }
                } catch (error) {
                    root.allowed = false;
                    root.ready = true;
                    root.message = "Fingerprint unavailable — enter your password";
                }
            }
        }
        onExited: (exitCode, exitStatus) => {
            root.allowed = false;
            root.ready = true;
            if (root.active) root.message = "Fingerprint unavailable — enter your password";
        }
    }
}
