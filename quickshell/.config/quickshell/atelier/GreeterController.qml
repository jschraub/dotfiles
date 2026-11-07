import QtQuick
import Quickshell.Services.Greetd
import Quickshell.Io

QtObject {
    id: root
    required property var service
    property string user: ""
    property bool requested: false
    property string message: ""
    property bool error: false
    property bool responseRequired: false
    property bool responseVisible: false
    property bool powerPending: false
    property string powerAction: ""
    readonly property bool busy: requested || powerPending || service.state !== GreetdState.Inactive
    signal clearResponse()
    function selectUser(name) {
        if (busy) return;
        clearResponse(); responseRequired = false; error = false; message = "";
        user = name;
    }
    function begin() {
        if (!user || busy) return;
        if (!service.available) { error = true; message = "Sign-in service unavailable."; return; }
        clearResponse(); error = false; message = ""; requested = true;
        service.createSession(user);
    }
    function respond(value) {
        if (!responseRequired || service.state !== GreetdState.Authenticating) return;
        responseRequired = false; clearResponse(); service.respond(value);
    }
    function power(action) {
        if (!["reboot", "poweroff"].includes(action) || powerPending) return;
        powerPending = true; requested = false; responseRequired = false; clearResponse();
        service.cancelSession(); powerAction = action; systemPower.running = true;
    }
    property Process systemPower: Process {
        command: ["/usr/bin/systemctl", root.powerAction]
        onExited: (exitCode, exitStatus) => {
            root.powerPending = false;
            if (exitCode !== 0) { root.error = true; root.message = "Power action was not permitted."; }
        }
    }
    property Connections events: Connections {
        target: root.service
        // Never auto-create from Inactive: cancel-session acknowledgement is a
        // separate greetd message. Account selection precedes a new conversation.
        function onStateChanged() { if (root.service.state === GreetdState.Inactive) root.requested = false; }
        function onAuthMessage(message, error, responseRequired, echoResponse) {
            root.clearResponse(); root.message = message; root.error = error;
            root.responseVisible = echoResponse; root.responseRequired = responseRequired;
        }
        function onAuthFailure(message) {
            root.clearResponse(); root.responseRequired = false; root.requested = false; root.error = true;
            root.message = "Authentication failed. Please try again.";
        }
        function onError(error) {
            root.clearResponse(); root.responseRequired = false; root.requested = false; root.error = true;
            root.message = "Sign-in service unavailable. Please try again.";
            if (root.service.available && root.service.state !== GreetdState.Inactive)
                root.service.cancelSession();
        }
        function onReadyToLaunch() {
            root.clearResponse(); root.responseRequired = false;
            // Fixed argv, never text from the user or a shell-interpreted command.
            if (root.requested && !root.powerPending && root.service.user === root.user
                    && root.service.state === GreetdState.ReadyToLaunch)
                root.service.launch(["/usr/bin/start-hyprland"], ["XDG_SESSION_TYPE=wayland", "XDG_CURRENT_DESKTOP=Hyprland", "XDG_SESSION_DESKTOP=Hyprland"]);
        }
    }
}
