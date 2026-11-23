import QtQuick
import Quickshell.Services.Pam

QtObject {
    id: root
    required property var password
    property var fingerprint: null
    property bool fingerprintAllowed: true
    property string fingerprintPolicyMessage: ""
    property string fingerprintFeedback: ""
    required property string user
    property bool secure: false
    property bool unlocked: false
    property bool submitted: false
    property string message: ""
    property bool error: false
    readonly property bool responseRequired: secure && !unlocked && !submitted && password.active && password.responseRequired
    readonly property bool responseVisible: password.responseVisible
    readonly property bool busy: password.active
    readonly property bool fingerprintAvailable: canFingerprint()
    readonly property string fingerprintMessage: fingerprintAvailable
        ? (fingerprintFeedback || "Fingerprint ready — touch the sensor or enter your password")
        : fingerprintPolicyMessage
    signal clearResponse()
    signal authenticated()
    onSecureChanged: if (secure && !unlocked) { begin(); startFingerprint(); }
    onFingerprintAllowedChanged: {
        fingerprintRetry.stop(); fingerprintFeedback = "";
        if (fingerprintAllowed) startFingerprint();
        else if (fingerprint) fingerprint.abort();
    }
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
            if (!root.canFingerprint()) return;
            if (result === PamResult.Success) root.finish(result);
            else root.retryFingerprint();
        }
        function onPamMessage() { root.fingerprintFeedback = root.fingerprint.message; }
        function onError(error) { root.retryFingerprint(); }
    }
    property Timer fingerprintRetry: Timer { interval: 2000; onTriggered: root.startFingerprint() }
    // Evaluate authoritative properties directly inside transition handlers;
    // a derived QML binding may still hold its previous value in that handler.
    function canFingerprint() { return secure && !unlocked && fingerprintAllowed && fingerprint !== null; }
    function retryFingerprint() {
        if (!canFingerprint()) return;
        fingerprintFeedback = "Fingerprint unavailable; retrying — password is still available";
        fingerprintRetry.restart();
    }
    function startFingerprint() {
        if (canFingerprint() && !fingerprint.active) {
            fingerprintFeedback = "Starting fingerprint reader…";
            if (!fingerprint.start()) retryFingerprint();
        }
    }
}
