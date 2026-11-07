import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "." as Atelier

ShellRoot {
    QtObject {
        id: fakeService
        property bool ready: true
        property bool paused: false
        property bool busy: false
        property string message: ""
        property var original: [
            { id: "first", kind: "text", label: "<b>First text</b>", text: "<b>First text</b>\nSecond line", size: 33, truncated: false },
            { id: "image", kind: "image", label: "PNG image 1×1", text: "", size: 70,
              preview: Qt.resolvedUrl("clipboard.png").toString(), width: 1, height: 1, truncated: false }
        ]
        property var allItems: original.slice()
        property var items: allItems
        property int count: allItems.length
        property var copies: []
        signal copied()
        function search(query) { items = allItems.filter(item => item.label.toLowerCase().includes(query.toLowerCase())); }
        function copy(id) { copies = copies.concat([id]); copied(); }
        function remove(id) { allItems = allItems.filter(item => item.id !== id); items = allItems; }
        function clear() { allItems = []; items = []; }
        function togglePaused() { paused = !paused; }
        function reset() { allItems = original.slice(); items = allItems; copies = []; paused = false; }
        onCopied: fakeShell.close()
    }
    QtObject {
        id: fakeShell
        property string panel: "clipboard"
        property bool testing: false
        property bool preview: false
        property string message: ""
        property var menuScreen: Quickshell.screens[0]
        property var clipboardService: fakeService
        function close() { panel = ""; }
    }
    Atelier.MenuWindow { id: menu; shell: fakeShell }
    Item { parent: menu.contentItem; TestEvent { id: events } }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    IpcHandler {
        target: "test"
        function open(): void { fakeService.reset(); fakeShell.panel = "clipboard"; }
        function search(text: string): void { find(menu.contentItem, "clipboard-search").text = text; }
        function key(name: string): bool { return events.keyClick(Qt["Key_" + name], Qt.NoModifier, 0); }
        function removeKey(): bool { return events.keyClick(Qt.Key_Delete, Qt.ControlModifier, 0); }
        function click(name: string): bool {
            const button = find(menu.contentItem, name);
            if (!button || !button.enabled) return false;
            button.clicked(); return true;
        }
        function status(): string {
            const list = find(menu.contentItem, "clipboard-list");
            const summary = find(menu.contentItem, "clipboard-summary-0");
            return JSON.stringify({ panel: fakeShell.panel, count: fakeService.count, matches: fakeService.items.length,
                index: list ? list.currentIndex : -1, paused: fakeService.paused, copies: fakeService.copies,
                plainText: !summary || summary.textFormat === Text.PlainText });
        }
    }
}
