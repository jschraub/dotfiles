import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "." as Atelier

ShellRoot {
    Atelier.DesktopServices { id: services }
    QtObject {
        id: fakeShell
        property var desktopServices: services
        property string panel: "media"
        function close() { panel = ""; }
    }
    PanelWindow {
        id: window
        anchors { bottom: true; right: true }
        implicitWidth: 500; implicitHeight: 500
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        color: Atelier.Theme.panel
        Loader {
            id: contents; x: 20; y: 20; width: 460; height: 460
            sourceComponent: fakeShell.panel === "media" ? media : fakeShell.panel === "tray" ? tray : null
        }
    }
    Component { id: media; Atelier.MediaPanel { shell: fakeShell } }
    Component { id: tray; Atelier.TrayPanel { shell: fakeShell } }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    IpcHandler {
        target: "test"
        function page(name: string): void { fakeShell.panel = name; }
        function click(name: string): bool {
            const button = find(contents.item, name);
            if (!button || !button.enabled) return false;
            button.clicked(); return true;
        }
        function status(): string {
            return JSON.stringify({ players: services.players.length, tray: services.trayItems.length,
                playing: services.players.length ? services.players[0].isPlaying : false,
                canToggle: services.players.length ? services.players[0].canControl && services.players[0].canTogglePlaying : false,
                menuCount: contents.item && contents.item.menuEntries ? contents.item.menuEntries.length : 0,
                menuLabels: contents.item && contents.item.menuEntries ? contents.item.menuEntries.map(e => ({ text: e.text, children: e.hasChildren })) : [] });
        }
    }
}
