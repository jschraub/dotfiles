import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam
import Quickshell.Services.Greetd
import "." as Atelier

ShellRoot {
    // Compile production entrypoints without creating them: no PAM session,
    // greetd connection object, or real Wayland lock is instantiated here.
    property var nativeLock: Qt.createComponent(Qt.resolvedUrl("lock.qml"))
    property var nativeGreeter: Qt.createComponent(Qt.resolvedUrl("greeter.qml"))
    QtObject {
        id: passwordFake
        property bool active: false
        property bool responseRequired: false
        property bool responseVisible: false
        property string message: "Password:"
        property bool messageIsError: false
        property int starts: 0
        property int responses: 0
        signal completed(int result)
        signal pamMessage()
        signal error(int error)
        function start() { starts++; active = true; responseRequired = true; return true; }
        function abort() { active = false; responseRequired = false; }
        function respond(value) { responses++; }
    }
    QtObject {
        id: fingerprintFake
        property bool active: false
        signal completed(int result)
        function start() { active = true; }
        function abort() { active = false; }
    }
    Atelier.LockController {
        id: lockController
        password: passwordFake; fingerprint: fingerprintFake; user: "fixture"
        property int unlocks: 0
        onAuthenticated: unlocks++
    }
    QtObject {
        id: greetdFake
        property bool available: true
        property int state: GreetdState.Inactive
        property string user: ""
        property var creates: []
        property var launches: []
        property int responses: 0
        signal authMessage(string message, bool error, bool responseRequired, bool echoResponse)
        signal authFailure(string message)
        signal readyToLaunch()
        signal error(string error)
        function createSession(name) { user = name; creates = creates.concat([name]); state = GreetdState.Authenticating; }
        function cancelSession() { state = GreetdState.Inactive; }
        function respond(value) { responses++; }
        function launch(command, environment) { launches = launches.concat([command]); state = GreetdState.Launched; }
    }
    Atelier.GreeterController { id: loginController; service: greetdFake }
    QtObject { id: accountInfo; property var users: [{ user: "fixture", name: "Fixture User", avatar: "" }]; property string background: "" }
    FloatingWindow {
        id: window
        title: "Atelier access test"
        implicitWidth: 800; implicitHeight: 700
        Atelier.AccessScene { anchors.fill: parent; controller: lockController; identity: accountInfo }
    }
    function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    IpcHandler {
        target: "test"
        function secure(): void { lockController.secure = true; }
        function result(success: bool): void { passwordFake.active = false; passwordFake.completed(success ? PamResult.Success : PamResult.Failed); }
        function fingerprint(): void { fingerprintFake.completed(PamResult.Success); }
        function retry(): void { lockController.begin(); }
        function answer(): void { find(window.contentItem, "access-response").text = "fixture-only-access-secret"; }
        function passwordPrompt(): void { passwordFake.message = "Password:"; passwordFake.pamMessage(); }
        function codePrompt(): void { passwordFake.message = "Verification code:"; passwordFake.pamMessage(); }
        function submit(): void { find(window.contentItem, "access-submit").clicked(); }
        function select(user: string): void { loginController.selectUser(user); }
        function beginLogin(): void { loginController.begin(); }
        function prompt(): void { greetdFake.authMessage("Password:", false, true, false); }
        function respond(): void { loginController.respond("fixture-only-access-secret"); }
        function launch(ready: bool): void { if (ready) greetdFake.state = GreetdState.ReadyToLaunch; greetdFake.readyToLaunch(); }
        function failure(): void { greetdFake.state = GreetdState.Inactive; greetdFake.authFailure("wrong"); }
        function status(): string {
            const input = find(window.contentItem, "access-response");
            const message = find(window.contentItem, "access-message");
            return JSON.stringify({ unlocks: lockController.unlocks, starts: passwordFake.starts, responses: passwordFake.responses,
                entrypointsReady: nativeLock.status === Component.Ready && nativeGreeter.status === Component.Ready,
                responseLength: input ? input.text.length : -1, masked: input && input.echoMode === TextInput.Password,
                placeholder: input ? input.placeholderText : "", messageShown: message && message.visible,
                creates: greetdFake.creates, launches: greetdFake.launches, loginResponses: greetdFake.responses,
                needsResponse: loginController.responseRequired, error: lockController.error });
        }
    }
}
