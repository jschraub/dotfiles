import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "." as Atelier

ShellRoot {
    QtObject {
        id: fakeShell
        property string panel: "power"
        property bool testing: false
        property var menuScreen: Quickshell.screens[0]
        property string message: ""
        property var requests: []
        function send(action, extra) { requests = requests.concat([{ action: action, choice: extra.choice }]); }
        function close() { panel = ""; }
    }
    Atelier.MenuWindow { id: menu; shell: fakeShell }
    Item {
        parent: menu.contentItem
        TestEvent { id: events }
    }
    function find(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) {
            const found = find(child, name);
            if (found) return found;
        }
        return null;
    }
    IpcHandler {
        target: "test"
        function open(): void { fakeShell.requests = []; fakeShell.panel = "power"; }
        function key(name: string): bool { return events.keyClick(Qt["Key_" + name], Qt.NoModifier, 0); }
        function status(): string {
            const nativeWindow = menu.contentItem.Window.window;
            const active = nativeWindow ? nativeWindow.activeFocusItem : null;
            const panel = find(menu.contentItem, "power-panel");
            return JSON.stringify({ width: menu.width, panel: fakeShell.panel,
                focus: active ? active.objectName : "", choice: panel ? panel.choice : "",
                requests: fakeShell.requests });
        }
    }
}
