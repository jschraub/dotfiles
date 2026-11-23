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
    onActiveChanged: if (!active) { allowed = false; present = false; ready = false; message = ""; }
    property Process monitor: Process {
        command: ["/usr/bin/python3", "-B", "-E", "-s", Qt.resolvedUrl("fingerprint_monitor.py").toString().replace(/^file:\/\//, "")].concat(root.greeter ? ["--greeter"] : [])
        running: root.active
        stdout: SplitParser {
            onRead: data => {
                try {
                    const state = JSON.parse(data);
                    root.allowed = state.allowed === true;
                    root.present = state.present === true;
                    root.ready = state.ready === true;
                    root.message = typeof state.message === "string" ? state.message : "";
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
