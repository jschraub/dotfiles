import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Greetd

QtObject {
    id: root
    property bool available: false
    property int state: GreetdState.Inactive
    property string user: ""
    signal authMessage(string message, bool error, bool responseRequired, bool echoResponse)
    signal authFailure(string message)
    signal error(string message)
    signal readyToLaunch()
    signal cancelled()
    signal launched()
    function send(value) {
        if (!available || !worker.running) { root.error("Sign-in connection unavailable."); return; }
        worker.write(JSON.stringify(value) + "\n");
    }
    function createSession(name) { send({type: "create", user: name}); }
    function cancelSession() { send({type: "cancel"}); }
    function respond(value) { send({type: "respond", response: value}); }
    function launch(command, environment) { send({type: "launch", command, environment}); }
    property Process worker: Process {
        command: ["/usr/bin/python3", "-B", "-E", "-s", Qt.resolvedUrl("greetd_transport.py").toString().replace(/^file:\/\//, "")]
        running: true
        stdinEnabled: true
        stdout: SplitParser {
            onRead: data => {
                try {
                    const event = JSON.parse(data);
                    if (event.type === "available") root.available = event.value === true;
                    else if (event.type === "state") {
                        root.user = event.user;
                        root.state = ({inactive: GreetdState.Inactive, authenticating: GreetdState.Authenticating,
                            ready: GreetdState.ReadyToLaunch, launching: GreetdState.Launching, launched: GreetdState.Launched})[event.state];
                    } else if (event.type === "message") root.authMessage(event.message, event.error, event.responseRequired, event.echoResponse);
                    else if (event.type === "auth_failure") root.authFailure(event.message);
                    else if (event.type === "error") root.error(event.message);
                    else if (event.type === "cancelled") root.cancelled();
                    else if (event.type === "ready") root.readyToLaunch();
                    else if (event.type === "launched") {
                        root.launched();
                        Quickshell.execDetached(["qs", "kill", "--pid", String(Quickshell.processId)]);
                    }
                } catch (error) { root.error("Invalid sign-in service response."); }
            }
        }
        onExited: (exitCode, exitStatus) => {
            root.available = false; root.state = GreetdState.Inactive;
            root.error("Sign-in connection unavailable. Please try again.");
            reconnect.restart();
        }
    }
    property Timer reconnect: Timer { interval: 2000; onTriggered: worker.running = true }
}
