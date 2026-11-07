import QtQuick
import Quickshell.Services.Pam

QtObject {
    id: root
    required property var password
    property var fingerprint: null
    required property string user
    property bool secure: false
    property bool unlocked: false
    property bool submitted: false
    property string message: ""
    property bool error: false
    readonly property bool responseRequired: secure && !unlocked && !submitted && password.active && password.responseRequired
    readonly property bool responseVisible: password.responseVisible
    readonly property bool busy: password.active
    readonly property bool fingerprintAvailable: secure && !unlocked && fingerprint !== null
    signal clearResponse()
    signal authenticated()
    onSecureChanged: if (secure && !unlocked) { begin(); startFingerprint(); }
    function begin() {
        if (!secure || unlocked || password.active) return;
        error = false; message = ""; submitted = false; clearResponse();
        if (!password.start()) { error = true; message = "Authentication could not start. Session remains locked."; }
    }
    function respond(value) {
        clearResponse();
        if (responseRequired) { submitted = true; password.respond(value); }
    }
    function finish(result) {
        clearResponse();
        submitted = false;
        if (!secure || unlocked) return;
        if (result === PamResult.Success) {
            unlocked = true;
            password.abort();
            if (fingerprint) fingerprint.abort();
            authenticated();
        } else {
            error = true; message = "Authentication failed. Please try again.";
        }
    }
    property Connections passwordEvents: Connections {
        target: root.password
        function onCompleted(result) { root.finish(result); }
        function onPamMessage() { root.submitted = false; root.message = root.password.message; root.error = root.password.messageIsError; }
        function onError(error) { root.clearResponse(); root.error = true; root.message = "Authentication unavailable. Session remains locked."; }
    }
    property Connections fingerprintEvents: Connections {
        target: root.fingerprint
        function onCompleted(result) {
            if (result === PamResult.Success) root.finish(result);
            else if (root.secure && !root.unlocked) fingerprintRetry.restart();
        }
    }
    property Timer fingerprintRetry: Timer { interval: 2000; onTriggered: root.startFingerprint() }
    function startFingerprint() { if (secure && !unlocked && fingerprint && !fingerprint.active) fingerprint.start(); }
}
