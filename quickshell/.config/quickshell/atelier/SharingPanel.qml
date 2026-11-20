import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var shell
    property var service: shell.sharingService || null
    readonly property var state: service ? service.state : ({})
    readonly property var streams: service ? service.streams : []
    readonly property var pending: streams.find(s => s.state === "pin_required") || null
    readonly property string pendingTarget: pending ? pending.target : ""
    readonly property string credentialKind: pending ? pending.credentialKind : ""
    readonly property int panelHeight: 760
    spacing: 12
    Component.onCompleted: if (service) service.send("status")
    onPendingTargetChanged: {
        secret.text = "";
        if (pendingTarget) Qt.callLater(() => { if (root.pendingTarget) secret.forceActiveFocus(Qt.TabFocusReason); });
    }
    onCredentialKindChanged: secret.text = ""
    Component.onDestruction: secret.text = ""
    function submit() {
        const target = pendingTarget, value = secret.text;
        secret.text = "";
        if (service && target && value) service.respond(target, value);
    }
    function configure(encoder, resolution, audio) {
        if (service) service.configure(encoder, resolution, audio);
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "Screen sharing"; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
        ActionButton {
            objectName: "sharing-stop"
            text: "Stop sharing"; dangerous: true
            enabled: !!root.service && (!!root.state.daemonRunning || !!root.state.networkRunning || root.streams.length > 0)
            onClicked: { secret.text = ""; root.service.send("stop"); }
        }
    }
    Label {
        Layout.fillWidth: true; wrapMode: Text.WordWrap
        text: "AirPlay for Apple TV. Miracast and Chromecast open Network Displays. Nothing connects without your selection."
        font.pixelSize: 12; color: Theme.muted
    }
    Label { text: "AIRPLAY"; color: Theme.accent; font.pixelSize: 11 }
    Label {
        Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11; color: Theme.muted
        text: "Doubletake is experimental. Do not use it for confidential work. No Apple TV app is required."
    }
    Label {
        visible: !root.state.airplayAvailable
        text: root.service ? "Install the optional backend: ./setup.sh casting" : "Sharing is disabled in this preview"
        Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 12
    }
    Flow {
        Layout.fillWidth: true; spacing: 6
        Repeater {
            model: [{ id: "auto", name: "Auto encoder" }, { id: "nvenc", name: "NVIDIA" },
                    { id: "vaapi", name: "AMD / Intel" }, { id: "none", name: "Software" }]
            ActionButton {
                required property var modelData
                objectName: "sharing-encoder-" + modelData.id
                text: modelData.name; selected: root.state.encoder === modelData.id
                Accessible.selected: selected
                enabled: !!root.service && !root.service.busy && root.streams.length === 0
                onClicked: root.configure(modelData.id, root.state.resolution || "1920x1080", !!root.state.audio)
            }
        }
    }
    Flow {
        Layout.fillWidth: true; spacing: 6
        Repeater {
            model: [{ id: "1280x720", name: "720p" }, { id: "1920x1080", name: "1080p" }, { id: "max", name: "Receiver maximum" }]
            ActionButton {
                required property var modelData
                text: modelData.name; selected: root.state.resolution === modelData.id
                Accessible.selected: selected
                enabled: !!root.service && !root.service.busy && root.streams.length === 0
                onClicked: root.configure(root.state.encoder || "auto", modelData.id, !!root.state.audio)
            }
        }
        ActionButton {
            objectName: "sharing-audio"
            text: root.state.audio ? "Computer audio: On" : "Computer audio: Off"
            Accessible.name: "Share computer audio"; accessibleToggle: true; selected: !!root.state.audio
            enabled: !!root.service && !root.service.busy && root.streams.length === 0
            hint: "Mirrors the default output, not the microphone\nLocal playback remains on\nApplies to AirPlay only"
            onClicked: root.configure(root.state.encoder || "auto", root.state.resolution || "1920x1080", !root.state.audio)
        }
    }
    RowLayout {
        ActionButton {
            objectName: "sharing-discover"
            text: root.state.daemonRunning ? "Refresh AirPlay devices" : "Find AirPlay devices"
            enabled: !!root.service && !!root.state.airplayAvailable && !root.service.busy
            onClicked: root.service.send("discover")
        }
        ActionButton {
            objectName: "sharing-check"
            text: "Check encoders"
            enabled: !!root.service && !root.service.busy
            onClicked: root.service.send("check")
        }
    }
    Label {
        Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11; color: Theme.muted
        text: Object.keys(root.state.plugins || {}).length ? "GStreamer elements: " +
            Object.keys(root.state.plugins).filter(key => root.state.plugins[key]).join(", ") +
            "\nAvailable elements are not a successful GPU/capture test." : "Capture selection uses the Wayland portal. Start at 1080p / 30 fps."
    }
    Controls.ScrollView {
        Layout.fillWidth: true; Layout.preferredHeight: 140
        contentWidth: availableWidth; clip: true
        Controls.ScrollBar.vertical: ScrollHandle {}
        ColumnLayout {
            width: parent.width
            Repeater {
                model: root.service ? root.service.devices : []
                ActionButton {
                    required property var modelData
                    objectName: "sharing-device-" + modelData.target
                    Layout.fillWidth: true; alignLeft: true
                    text: modelData.name + "\u2003" + modelData.target
                    enabled: !!root.service && !root.service.busy && root.streams.length === 0
                    onClicked: root.service.send("connect", { target: modelData.target })
                }
            }
            Label { visible: !root.service || root.service.devices.length === 0; text: "No AirPlay receivers listed yet"; color: Theme.muted; font.pixelSize: 12 }
        }
    }
    Repeater {
        model: root.streams
        Label {
            required property var modelData
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            text: modelData.name + "\u2003" + modelData.state.replace(/_/g, " ")
                + (modelData.state === "streaming" ? "\nEncoder: " + modelData.encoder + (modelData.hardware ? " (hardware)" : " (software / unknown)") : "")
            color: modelData.state === "streaming" ? Theme.good : Theme.accent
        }
    }
    ColumnLayout {
        visible: root.pendingTarget !== ""
        Layout.fillWidth: true
        Label { text: root.credentialKind === "password" ? "Receiver password" : "Enter the code shown on your TV"; color: Theme.accent }
        SearchField {
            id: secret
            objectName: "sharing-credential"
            Layout.fillWidth: true; maximumLength: 256
            echoMode: TextInput.Password
            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhHiddenText
            placeholderText: root.credentialKind === "password" ? "Receiver password" : "TV pairing code"
            onAccepted: root.submit()
        }
        ActionButton { objectName: "sharing-submit"; text: "Pair"; enabled: secret.text.length > 0 && !!root.service && !root.service.busy; onClicked: root.submit() }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
    Label { text: "MIRACAST / CHROMECAST"; color: Theme.accent; font.pixelSize: 11 }
    ActionButton {
        objectName: "sharing-network"
        text: root.state.networkRunning ? "Network Displays is open" : "Open Network Displays ↗"
        enabled: !!root.service && !!root.state.networkAvailable && !root.service.busy && !root.state.networkRunning
        onClicked: root.service.send("network")
    }
    Label {
        Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11; color: Theme.muted
        text: "Receiver selection, pairing and audio for these protocols stay in Network Displays. Miracast needs Wi-Fi Direct support. Casting is not automatically resumed after a helper restart."
    }
    Label {
        visible: !!root.service && !!root.service.message
        text: root.service ? root.service.message : ""
        Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 12
    }
}
