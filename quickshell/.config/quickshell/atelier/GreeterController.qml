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
    property bool hardwareReady: false
    property bool readerPresent: false
    property bool fingerprintAllowed: false
    property string fingerprintPolicyMessage: ""
    property string method: "password"
    property string attemptMethod: "password"
    property bool defaultChosen: false
    property bool selectionSupported: false
    property bool choiceSent: false
    property bool fingerprintExpired: false
    property bool switching: false
    property bool restartQueued: false
    property bool pendingBegin: false
    property bool launching: false
    property bool powerPending: false
    property string powerAction: ""
    readonly property bool busy: switching || requested || powerPending || service.state !== GreetdState.Inactive
    readonly property bool canSwitchMethod: selectionSupported && hardwareReady && !switching && !powerPending && !launching
    readonly property bool canRestartFingerprint: selectionSupported && method === "fingerprint" && fingerprintExpired && fingerprintAllowed && !switching && !powerPending && !launching
    signal clearResponse()
    function selectUser(name) {
        if (busy) return;
        clearResponse(); responseRequired = false; error = false; message = "";
        user = name;
    }
    function begin() {
        if (!user || switching || powerPending || launching) return;
        if (!hardwareReady || !service.available) { pendingBegin = true; return; }
        if (requested || service.state !== GreetdState.Inactive) return;
        pendingBegin = false;
        if (method === "fingerprint" && !fingerprintAllowed) method = "password";
        attemptMethod = method; selectionSupported = false; choiceSent = false; fingerprintExpired = false;
        clearResponse(); error = false; message = ""; requested = true;
        service.createSession(user);
    }
    function updateHardware(present, allowed, ready, status) {
        readerPresent = present; fingerprintAllowed = allowed; hardwareReady = ready;
        fingerprintPolicyMessage = status;
        if (!ready) return;
        if (!defaultChosen) {
            defaultChosen = true;
            method = present && allowed ? "fingerprint" : "password";
        } else if (method === "fingerprint" && !allowed) {
            chooseMethod("password");
        }
        if (pendingBegin) Qt.callLater(root.begin);
    }
    function chooseMethod(value) {
        if (!["password", "fingerprint"].includes(value) || powerPending || launching) return;
        if (value === "fingerprint" && !fingerprintAllowed) return;
        if (method === value && !fingerprintExpired) return;
        method = value;
        restartConversation();
    }
    function restartFingerprint() {
        if (!canRestartFingerprint) return;
        restartConversation();
    }
    function restartConversation() {
        if (switching) return;
        requested = false; pendingBegin = false; responseRequired = false;
        choiceSent = false; fingerprintExpired = false; switching = true; clearResponse();
        if (service.available && service.state !== GreetdState.Inactive) service.cancelSession();
        else queueRestart();
    }
    function queueRestart() {
        if (!restartQueued) { restartQueued = true; Qt.callLater(root.finishSwitch); }
    }
    function finishSwitch() {
        // Only a confirmed cancellation (or an already idle connection) reaches here.
        restartQueued = false; switching = false;
        if (!powerPending && !launching) begin();
    }
    function respond(value) {
        if (!requested || switching || !responseRequired || service.state !== GreetdState.Authenticating) return;
        if (selectionSupported && (!choiceSent || attemptMethod !== "password")) return;
        responseRequired = false; clearResponse(); service.respond(value);
    }
    function power(action) {
        if (!["reboot", "poweroff"].includes(action) || powerPending) return;
        powerPending = true; requested = false; pendingBegin = false; responseRequired = false; clearResponse();
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
        function onAvailableChanged() { if (root.service.available && root.pendingBegin) Qt.callLater(root.begin); }
        function onCancelled() { if (root.switching) root.queueRestart(); }
        function onAuthMessage(message, error, responseRequired, echoResponse) {
            if (!root.requested || root.switching || root.powerPending || root.launching) return;
            if (responseRequired && message === "Atelier authentication method:") {
                root.selectionSupported = true;
                root.choiceSent = true;
                root.responseRequired = false; root.clearResponse();
                root.message = root.attemptMethod === "fingerprint" ? "Starting fingerprint reader…" : "";
                root.service.respond(root.attemptMethod);
                return;
            }
            root.clearResponse(); root.message = message; root.error = error;
            root.responseVisible = echoResponse; root.responseRequired = responseRequired;
        }
        function onAuthFailure(message) {
            if (root.switching || root.powerPending) return;
            root.launching = false;
            root.clearResponse(); root.responseRequired = false; root.requested = false; root.error = true;
            root.fingerprintExpired = root.selectionSupported && root.attemptMethod === "fingerprint";
            root.message = root.fingerprintExpired ? "Fingerprint scanning ended. Restart scanning or use your password."
                : "Authentication failed. Please try again.";
        }
        function onError(error) {
            if (root.powerPending) return;
            root.launching = false;
            root.switching = false; root.pendingBegin = false;
            root.clearResponse(); root.responseRequired = false; root.requested = false; root.error = true;
            root.message = "Sign-in service unavailable. Please try again.";
            if (root.service.available && root.service.state !== GreetdState.Inactive)
                root.service.cancelSession();
        }
        function onReadyToLaunch() {
            root.clearResponse(); root.responseRequired = false;
            // Fixed argv, never text from the user or a shell-interpreted command.
            if (root.requested && !root.switching && !root.powerPending && !root.launching && root.service.user === root.user
                    && (!root.selectionSupported || root.choiceSent)
                    && (!root.selectionSupported || root.attemptMethod !== "fingerprint" || root.fingerprintAllowed)
                    && root.service.state === GreetdState.ReadyToLaunch) {
                root.launching = true;
                root.service.launch(["/usr/bin/start-hyprland"], ["XDG_SESSION_TYPE=wayland", "XDG_CURRENT_DESKTOP=Hyprland", "XDG_SESSION_DESKTOP=Hyprland"]);
            }
        }
    }
}
