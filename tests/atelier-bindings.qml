import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import "." as Atelier

ShellRoot {
    QtObject {
        id: fake
        property var bindings: [{ key: "Super + F1", description: "Keyboard help", category: "Desktop", context: "" }]
        property int refreshes: 0
        function refreshBindings() { refreshes++; }
        property var bindingContext: ({
            selected: "app:ghostty",
            tools: [{ id: "opencode", label: "OpenCode", note: "Documented defaults + global overrides",
                rows: [{ key: "Ctrl + X → N", description: "New session", category: "OpenCode", context: "", source: "Global override" }] },
                { id: "tmux", label: "tmux", rows: [], note: "Installed but closed" }],
            library: [
                { id: "installed", label: "All shortcuts", terminal: false, note: "All installed references",
                  rows: [{ key: "Ctrl+B → c", description: "Create window", category: "tmux", context: "", source: "Defaults" }] },
                { id: "desktop", label: "Desktop", terminal: false, rows: bindings, note: "Live desktop bindings" },
                { id: "reference:tmux", label: "tmux", terminal: false, note: "Installed but closed",
                  rows: [{ key: "Ctrl+B → c", description: "Create window", category: "tmux", context: "", source: "Defaults" }] }
            ],
            tabs: [
                { id: "desktop", label: "Desktop", terminal: false, rows: bindings, note: "Live desktop bindings" },
                { id: "app:ghostty", label: "Ghostty (2)", terminal: true, toolIds: ["opencode"],
                  baseRows: [{ key: "Ctrl + Shift + C", description: "Copy", category: "Ghostty", context: "", source: "Ghostty configuration" }],
                  rows: [
                    { key: "Ctrl + Shift + C", description: "Copy", category: "Ghostty", context: "", source: "Ghostty configuration" },
                    { key: "Ctrl + Tab / Alt + Down", description: "Next session", category: "OpenCode", context: "", source: "Documented defaults" }
                  ], note: "Detected tools span terminal windows, not necessarily the focused pane." },
                { id: "app:unknown", label: "Unknown", terminal: false, rows: [], note: "No shortcut profile yet." }
            ]
        })
    }
    FloatingWindow {
        id: window
        implicitWidth: 940; implicitHeight: 700
        color: Atelier.Theme.panel
        Atelier.Bindings {
            id: reference
            anchors { fill: parent; margins: 20 }
            shell: fake
        }
        TestCase { id: keyboard; when: false }
    }
    IpcHandler {
        target: "test"
        function select(id: string): void { reference.selectTab(id); }
        function cycle(delta: int): void { reference.cycleTab(delta); }
        function scope(value: string): void { reference.selectScope(value); }
        function key(sequence: string): void {
            window.contentItem.Window.window.requestActivate();
            keyboard.keySequence(sequence);
        }
        function tool(id: string): void { reference.toolId = id; }
        function query(value: string): void { search(reference, "shortcut-search").text = value; }
        function category(value: string): void { reference.category = value; }
        function status(): string {
            return JSON.stringify({ selected: reference.tabId, rows: reference.filtered,
                scope: reference.scope, tabs: reference.tabs.map(t => t.label), tools: reference.tools.map(t => t.label),
                hints: hints(reference), green: Atelier.Theme.good.toString(), refreshes: fake.refreshes,
                query: search(reference, "shortcut-search").text,
                searchFocused: search(reference, "shortcut-search").activeFocus,
                categories: reference.categories, note: reference.note,
                width: reference.width, height: reference.height });
        }
    }
    function hints(item) {
        let result = [];
        if (item.objectName === "button-shortcut" && item.visible) {
            const caption = Array.from(item.parent.children).find(c => c.objectName === "button-label");
            result.push({ text: item.text, color: item.color.toString(), width: item.width, needed: item.implicitWidth,
                gap: caption ? item.x - caption.x - caption.width : 0 });
        }
        for (const child of item.children || []) result = result.concat(hints(child));
        return result;
    }
    function search(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children || []) {
            const found = search(child, name);
            if (found) return found;
        }
        return null;
    }
}
