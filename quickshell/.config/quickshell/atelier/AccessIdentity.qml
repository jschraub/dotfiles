import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    required property string mode
    property bool preview: false
    property var users: []
    property string background: ""
    property bool ready: false
    property Process reader: Process {
        command: ["/usr/bin/python3", "-B", Qt.resolvedUrl("access_identity.py").toString().replace("file://", ""), root.mode].concat(root.preview ? ["--preview"] : [])
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text);
                    root.users = data.users; root.background = data.background; root.ready = true;
                } catch (error) { root.ready = false; }
            }
        }
    }
}
