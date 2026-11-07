import QtQuick
import Quickshell.Services.Pipewire
import Quickshell.Services.Mpris
import Quickshell.Services.SystemTray
import Quickshell.Bluetooth

// Read-only discovery. Writes happen only in explicit, capability-checked UI actions.
QtObject {
    id: root
    readonly property var outputs: Pipewire.nodes.values.filter(n => n.audio && n.isSink && !n.isStream)
    readonly property var inputs: Pipewire.nodes.values.filter(n => n.audio && !n.isSink && !n.isStream)
    readonly property var defaultOutput: Pipewire.defaultAudioSink
    readonly property var defaultInput: Pipewire.defaultAudioSource
    readonly property var adapters: Bluetooth.adapters.values
    readonly property var players: Mpris.players.values
    readonly property var trayItems: SystemTray.items.values.filter(item => item.status !== Status.Passive)
    property PwObjectTracker tracker: PwObjectTracker { objects: root.outputs.concat(root.inputs) }
    function setDefault(node, input) {
        if (!node || !(input ? inputs : outputs).includes(node)) return;
        if (input) Pipewire.preferredDefaultAudioSource = node;
        else Pipewire.preferredDefaultAudioSink = node;
    }
}
