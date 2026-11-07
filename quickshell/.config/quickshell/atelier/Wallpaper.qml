import QtQuick
import Quickshell
import Quickshell.Wayland

PanelWindow {
    id: root
    required property string path
    readonly property bool ready: picture.status === Image.Ready
    visible: ready
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "atelier-wallpaper"
    mask: Region {}
    color: Theme.background
    Image {
        id: picture
        anchors.fill: parent
        source: root.path ? "file://" + root.path : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: true
    }
}
