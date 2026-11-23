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
        property string message: "Touch the fingerprint reader"
        property int starts: 0
        signal completed(int result)
        signal pamMessage()
        signal error(int error)
        function start() { starts++; active = true; return true; }
        function abort() { active = false; }
    }
    Atelier.LockController {
        id: lockController
        password: passwordFake; fingerprint: fingerprintFake; user: "fixture"
        property int unlocks: 0
        onAuthenticated: unlocks++
    }
    component FakeGreetd: QtObject {
        property bool available: true
        property int state: GreetdState.Inactive
        property string user: ""
        property var creates: []
        property var launches: []
        property int responses: 0
        property var methodResponses: []
        property int cancellations: 0
        signal authMessage(string message, bool error, bool responseRequired, bool echoResponse)
        signal authFailure(string message)
        signal readyToLaunch()
        signal error(string error)
        signal cancelled()
        function createSession(name) { user = name; creates = creates.concat([name]); state = GreetdState.Authenticating; }
        function cancelSession() { cancellations++; state = GreetdState.Inactive; cancelled(); }
        function respond(value) { responses++; if (["fingerprint", "password"].includes(value)) methodResponses = methodResponses.concat([value]); }
        function launch(command, environment) { launches = launches.concat([command]); state = GreetdState.Launched; }
    }
    FakeGreetd { id: greetdFake }
    FakeGreetd { id: methodService }
    FakeGreetd { id: readerlessService }
    Atelier.GreeterController { id: loginController; service: greetdFake; hardwareReady: true }
    Atelier.GreeterController {
        id: methodController
        service: methodService
        property var sleepAcknowledgements: []
        onFingerprintStoppedForSleep: generation => {
            sleepAcknowledgements = sleepAcknowledgements.concat([generation]);
        }
    }
    Atelier.GreeterController { id: readerlessController; service: readerlessService }
    QtObject { id: accountInfo; property var users: [{ user: "fixture", name: "Fixture User", avatar: "" }]; property string background: "" }
    FloatingWindow {
        id: window
        title: "Atelier access test"
        implicitWidth: 800; implicitHeight: 700
        property int testMode: 0
        property var testController: testMode === 2 ? readerlessController : methodController
        Atelier.AccessScene {
            anchors.fill: parent
            controller: window.testMode ? window.testController : lockController
            identity: accountInfo
            login: window.testMode !== 0
        }
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
        function fingerprintAllowed(allowed: bool): void { lockController.fingerprintAllowed = allowed; }
        function fingerprintFailure(): void { fingerprintFake.active = false; fingerprintFake.completed(PamResult.Failed); }
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
        function methodBegin(): void { window.testMode = 1; methodController.selectUser("fixture"); methodController.begin(); }
        function hardware(present: bool, allowed: bool, ready: bool): void { methodController.updateHardware(present, allowed, ready, allowed ? "" : "Fingerprint paused while the lid is closed"); }
        function methodPrompt(): void { methodService.authMessage("Atelier authentication method:", false, true, false); }
        function methodPassword(): void { methodService.authMessage("Password:", false, true, false); }
        function methodSleep(): void {
            methodController.sleeping = true;
            methodController.updateHardware(true, false, true, "Fingerprint paused for sleep/resume");
            methodController.prepareForSleep(7);
        }
        function methodWake(): void {
            methodController.updateHardware(true, true, true, "");
            methodController.sleeping = false;
        }
        function methodFailure(): void { methodService.authFailure("expired"); methodService.state = GreetdState.Inactive; }
        function toggle(): void {
            const control = find(window.contentItem, "access-method-toggle");
            control.checked = !control.checked; control.toggled();
            methodService.state = GreetdState.ReadyToLaunch; methodService.readyToLaunch();
            methodService.state = GreetdState.Inactive;
        }
        function methodLaunch(): void { methodService.state = GreetdState.ReadyToLaunch; methodService.readyToLaunch(); }
        function readerless(): void {
            window.testMode = 2;
            readerlessController.updateHardware(false, false, true, "");
            readerlessController.selectUser("fixture"); readerlessController.begin();
            readerlessService.authMessage("Atelier authentication method:", false, true, false);
        }
        function status(): string {
            const input = find(window.contentItem, "access-response");
            const message = find(window.contentItem, "access-message");
            const toggle = find(window.contentItem, "access-method-toggle");
            const submit = find(window.contentItem, "access-submit");
            return JSON.stringify({ unlocks: lockController.unlocks, starts: passwordFake.starts, responses: passwordFake.responses,
                entrypointsReady: nativeLock.status === Component.Ready && nativeGreeter.status === Component.Ready,
                responseLength: input ? input.text.length : -1, masked: input && input.echoMode === TextInput.Password,
                placeholder: input ? input.placeholderText : "", messageShown: message && message.visible,
                creates: greetdFake.creates, launches: greetdFake.launches, loginResponses: greetdFake.responses,
                needsResponse: loginController.responseRequired, error: lockController.error,
                fingerprintStarts: fingerprintFake.starts, fingerprintActive: fingerprintFake.active,
                fingerprintMessage: lockController.fingerprintMessage,
                method: methodController.method, methodCreates: methodService.creates.length,
                methodResponses: methodService.methodResponses, methodLaunches: methodService.launches,
                methodExpired: methodController.fingerprintExpired, methodCancellations: methodService.cancellations,
                sleepAcknowledgements: methodController.sleepAcknowledgements,
                inputVisible: input && input.visible, toggleVisible: toggle && toggle.visible,
                toggleEnabled: toggle && toggle.enabled, submitText: submit ? submit.text : "",
                readerlessMethod: readerlessController.method, readerlessResponses: readerlessService.methodResponses });
        }
    }
}
