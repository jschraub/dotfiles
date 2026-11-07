import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Polkit
import Quickshell.Hyprland
import "." as Atelier

ShellRoot {
    id: root
    property var authScreen: Quickshell.screens[0] || null
    PolkitAgent {
        id: agent; path: "/org/atelier/PolkitAgent"
        onAuthenticationRequestStarted: root.authScreen = Quickshell.screens.find(s => Hyprland.focusedMonitor && s.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0] || null
    }
    IpcHandler {
        target: "auth"
        function health(): string { return agent.isRegistered ? "ready" : "unregistered"; }
        function active(): bool { return agent.isActive; }
        function cancel(): void { if (agent.flow) agent.flow.cancelAuthenticationRequest(); }
        // Intentionally no response/password IPC, logs or status serialization.
    }
    PanelWindow {
        id: window
        screen: Quickshell.screens.indexOf(root.authScreen) >= 0 ? root.authScreen : Quickshell.screens[0] || null
        visible: agent.isActive && !!agent.flow && !agent.flow.isCompleted && Quickshell.screens.length > 0
        anchors { top: true; bottom: true; left: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "atelier-authentication"
        WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
        color: "#66000000"
        Rectangle {
            width: Math.min(500, parent.width - 40)
            height: Math.min(dialog.implicitHeight + 40, parent.height - 40)
            anchors.centerIn: parent
            radius: Atelier.Theme.radius; color: Atelier.Theme.panel; border.color: Atelier.Theme.accent
            Flickable {
                id: scroll
                anchors { fill: parent; margins: 20 }
                contentWidth: width; contentHeight: dialog.implicitHeight; clip: true
                Atelier.AuthDialog {
                    id: dialog
                    width: scroll.width
                    flow: agent.flow
                    onFocusResponse: (y, height) => scroll.contentY = Math.max(0, Math.min(y - (scroll.height - height) / 2, scroll.contentHeight - scroll.height))
                }
            }
        }
        Shortcut { sequence: "Escape"; enabled: window.visible; onActivated: if (agent.flow) agent.flow.cancelAuthenticationRequest() }
    }
}
