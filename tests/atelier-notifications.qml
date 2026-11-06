import QtQuick
import Quickshell
import Quickshell.Io
import "." as Atelier

ShellRoot {
    id: root
    property bool testing: true
    property string panel: ""
    function focusedScreen() { return Quickshell.screens[0]; }
    Atelier.NotificationService { id: notifications; shell: root }
    IpcHandler {
        target: "test"
        function status(): string {
            return JSON.stringify({ count: notifications.history.length,
                live: notifications.history.filter(n => n.live).length,
                toasts: notifications.toastItems.length,
                titles: notifications.history.map(n => n.title),
                timeouts: notifications.history.map(n => n.live ? n.live.expireTimeout : null) });
        }
        function clear(): void { notifications.clear(); }
        function dnd(enabled: bool): void { notifications.dnd = enabled; }
        function invoke(): void {
            const record = notifications.history.find(n => n.live && n.live.actions.length);
            if (record) record.live.actions[0].invoke();
        }
    }
}
