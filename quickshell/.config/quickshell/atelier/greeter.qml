import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Greetd

ShellRoot {
    AccessIdentity {
        id: accountInfo; mode: "greeter"
        onReadyChanged: {
            if (ready && users.length) {
                loginController.selectUser(users[0].user);
                if (users.length === 1) loginController.begin();
            }
        }
    }
    GreetdTransport { id: signInService }
    GreeterController { id: loginController; service: signInService }
    FingerprintPolicy {
        id: fingerprintPolicy
        active: true
        greeter: true
        function update() { loginController.updateHardware(present, allowed, ready, message); }
        onPresentChanged: update()
        onAllowedChanged: update()
        onReadyChanged: update()
        onMessageChanged: update()
    }
    Variants {
        model: Quickshell.screens
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
            exclusionMode: ExclusionMode.Ignore
            color: Theme.background
            AccessScene { anchors.fill: parent; controller: loginController; identity: accountInfo; login: true }
        }
    }
}
