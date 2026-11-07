import QtQuick
import Quickshell
import Quickshell.Wayland

ShellRoot {
    AccessIdentity { id: accountInfo; mode: "lock"; preview: true }
    QtObject {
        id: previewController
        readonly property string user: accountInfo.users.length ? accountInfo.users[0].user : ""
        property string message: "Your session is safe — authentication is disabled in this preview."
        property bool error: false
        property bool responseRequired: false
        property bool responseVisible: false
        property bool busy: false
        signal clearResponse()
    }
    FloatingWindow {
        title: "Atelier login & lock preview"
        implicitWidth: 1100; implicitHeight: 700
        color: Theme.background
        AccessScene {
            anchors.fill: parent
            controller: previewController; identity: accountInfo; preview: true
            login: Quickshell.env("ATELIER_ACCESS_PREVIEW") === "greeter"
        }
    }
}
