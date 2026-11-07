import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Greetd

ShellRoot {
    AccessIdentity {
        id: accountInfo; mode: "greeter"
        onReadyChanged: {
            if (ready && users.length && Greetd.available) {
                loginController.selectUser(users[0].user);
                if (users.length === 1) loginController.begin();
            }
        }
    }
    GreeterController { id: loginController; service: Greetd }
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
