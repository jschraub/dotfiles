import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "." as Atelier

ShellRoot {
    QtObject { id: output1; property int id: 1; property string description: "Speakers"; property string nickname: ""; property string name: "speakers" }
    QtObject { id: output2; property int id: 2; property string description: "Headphones"; property string nickname: ""; property string name: "headphones" }
    QtObject { id: mic; property int id: 3; property string description: "Microphone"; property string nickname: ""; property string name: "mic" }
    QtObject {
        id: device
        property string name: "Test headphones"
        property string address: "00:11:22:33:44:55"
        property bool connected: true
        property bool paired: true
        property bool blocked: false
        property int state: connected ? 1 : 0
        property bool batteryAvailable: true
        property real battery: 0.73
    }
    QtObject {
        id: adapter
        property string name: "Test adapter"
        property bool enabled: true
        property bool discovering: false
        property QtObject devices: QtObject { property var values: [device] }
    }
    QtObject {
        id: player
        property string identity: "Test player"
        property string trackTitle: "Test track"
        property string trackArtist: "Test artist"
        property string trackAlbum: "Test album"
        property bool isPlaying: false
        property bool canControl: true
        property bool canGoPrevious: false
        property bool canGoNext: false
        property bool canTogglePlaying: true
        property bool canRaise: false
        function togglePlaying() { isPlaying = !isPlaying; }
    }
    QtObject {
        id: trayItem
        property string id: "test-app"
        property string title: "Test app"
        property string icon: ""
        property string tooltipTitle: "Test app"
        property string tooltipDescription: ""
        property bool onlyMenu: false
        property bool hasMenu: false
        function activate() { fakeShell.lastAction = "tray"; }
    }
    QtObject {
        id: service
        property var outputs: [output1, output2]
        property var inputs: [mic]
        property var defaultOutput: output1
        property var defaultInput: mic
        property var adapters: [adapter]
        property var players: [player]
        property var trayItems: [trayItem]
        function setDefault(node, input) { if (input) defaultInput = node; else defaultOutput = node; }
    }
    QtObject { id: identity; property string displayName: "Test user"; property string string: "test" }
    QtObject {
        id: authFlow
        property string message: "Test authentication"
        property string actionId: "org.example.test"
        property var identities: [identity]
        property var selectedIdentity: identity
        property bool isResponseRequired: true
        property string inputPrompt: "Password:"
        property bool responseVisible: false
        property string supplementaryMessage: ""
        property bool supplementaryIsError: false
        property bool failed: false
        property bool isCompleted: false
        property bool submitted: false
        property bool cancelled: false
        function submit(answer) { submitted = answer.length > 0; isResponseRequired = false; }
        function cancelAuthenticationRequest() { cancelled = true; isCompleted = true; }
    }
    QtObject {
        id: fakeShell
        property string panel: "audioDevices"
        property bool testing: false
        property bool preview: false
        property string message: ""
        property var desktopServices: service
        property var state: ({ microphone: { percent: 50, muted: false } })
        property string lastAction: ""
        function send(action, extra) { lastAction = action; }
        function open(name, output) { panel = name; }
        function close() { panel = ""; }
        function focusedScreen() { return Quickshell.screens[0]; }
    }
    PanelWindow {
        id: window
        anchors { top: true; left: true }
        implicitWidth: 600; implicitHeight: 720
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "atelier-services-test"
        color: Atelier.Theme.panel
        Loader {
            id: contents
            x: 20; y: 20; width: 560; height: 680
            sourceComponent: ({ audioDevices: audio, bluetooth: bluetooth, media: media, tray: tray, auth: auth })[fakeShell.panel] || null
        }
    }
    Component { id: audio; Atelier.AudioDevicesPanel { shell: fakeShell } }
    Component { id: bluetooth; Atelier.BluetoothPanel { shell: fakeShell } }
    Component { id: media; Atelier.MediaPanel { shell: fakeShell } }
    Component { id: tray; Atelier.TrayPanel { shell: fakeShell } }
    Component { id: auth; Atelier.AuthDialog { flow: authFlow } }
    Atelier.Osd { id: osd; shell: fakeShell }
    Atelier.Wallpaper { id: wallpaper; visible: false; screen: Quickshell.screens[0]; path: Qt.resolvedUrl("wallpaper.png").toString().replace("file://", "") }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        return null;
    }
    IpcHandler {
        target: "test"
        function page(name: string): void { fakeShell.panel = name; }
        function click(name: string): void { const button = find(contents.item, name); if (button && button.enabled) button.clicked(); }
        function answer(): void { find(contents.item, "authentication-response").text = "fixture-only-secret"; }
        function showOsd(): void { osd.show("brightness", 57, false); }
        function status(): string {
            const response = find(contents.item, "authentication-response");
            return JSON.stringify({ width: window.width, output: service.defaultOutput.id, microphone: fakeShell.lastAction,
                connected: device.connected, scanning: adapter.discovering, playing: player.isPlaying, tray: fakeShell.lastAction === "tray",
                responseLength: response ? response.text.length : 0, masked: response ? response.echoMode === TextInput.Password : false,
                submitted: authFlow.submitted, cancelled: authFlow.cancelled, wallpaperReady: wallpaper.ready,
                osd: osd.kind, osdPercent: osd.percent });
        }
    }
}
