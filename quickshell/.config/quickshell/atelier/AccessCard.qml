import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell.Widgets

ColumnLayout {
    id: root
    required property var controller
    required property var users
    property bool login: false
    property bool preview: false
    readonly property var account: users.find(user => user.user === controller.user) || users[0] || null
    readonly property bool passwordPrompt: !controller.message || /^password\s*:?\s*$/i.test(controller.message.trim())
    signal response(string value)
    signal begin()
    signal selectUser(string user)
    spacing: 16
    function clear() { secret.text = ""; }
    function focusResponse() { if (controller.responseRequired) secret.forceActiveFocus(); }
    function submit() {
        if (!controller.responseRequired) { root.begin(); return; }
        const value = secret.text;
        clear();
        root.response(value); // Direct PAM/greetd conversation, never backend/IPC/argv.
    }
    Component.onDestruction: clear()
    Component.onCompleted: Qt.callLater(focusResponse)
    Connections {
        target: root.controller
        function onClearResponse() { root.clear(); }
        function onResponseRequiredChanged() { root.clear(); Qt.callLater(root.focusResponse); }
        function onUserChanged() { root.clear(); }
        function onErrorChanged() {
            if (root.controller.error && !root.controller.busy)
                Qt.callLater(() => submitButton.forceActiveFocus(Qt.TabFocusReason));
        }
        function onBusyChanged() {
            if (root.controller.error && !root.controller.busy)
                Qt.callLater(() => submitButton.forceActiveFocus(Qt.TabFocusReason));
        }
    }
    ClippingRectangle {
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: 108; implicitHeight: 108; radius: 54
        color: Theme.raised
        Image {
            anchors.fill: parent
            source: root.account && root.account.avatar ? "file://" + root.account.avatar : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
        }
        Label {
            anchors.centerIn: parent
            visible: !root.account || !root.account.avatar
            text: root.account ? root.account.name.charAt(0).toUpperCase() : "?"
            font.pixelSize: 40; color: Theme.accent
        }
        border { width: 2; color: Theme.accent }
    }
    Label {
        Layout.fillWidth: true
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: root.login ? "Speak, friend, and enter." : "Keep it secret. Keep it safe."
        font.pixelSize: 24; font.weight: Font.DemiBold
    }
    Label {
        Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
        text: root.account ? root.account.name : root.login ? "No local login account found" : "Current user"
        font.pixelSize: 18
    }
    RowLayout {
        visible: root.login && root.users.length > 1
        Layout.alignment: Qt.AlignHCenter
        Repeater {
            model: root.users
            ActionButton {
                required property var modelData
                text: modelData.user; selected: root.controller.user === modelData.user
                enabled: !root.preview && !root.controller.busy
                onClicked: root.selectUser(modelData.user)
            }
        }
    }
    Label {
        objectName: "access-message"
        Layout.fillWidth: true; wrapMode: Text.WordWrap
        visible: !!root.controller.message && (root.controller.error || !root.passwordPrompt)
        text: root.controller.message
        color: root.controller.error ? Theme.danger : Theme.muted
        font.pixelSize: 12
    }
    SearchField {
        id: secret
        objectName: "access-response"
        Layout.fillWidth: true
        enabled: root.controller.responseRequired && !root.preview
        echoMode: root.controller.responseVisible ? TextInput.Normal : TextInput.Password
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
            | (root.controller.responseVisible ? 0 : Qt.ImhHiddenText)
        placeholderText: root.preview || root.passwordPrompt ? "Password" : "Enter here"
        Accessible.name: root.passwordPrompt ? "Password" : root.controller.message
        onAccepted: root.submit()
    }
    Label {
        Layout.fillWidth: true
        visible: !root.login && !!root.controller.fingerprintAvailable
        text: "Fingerprint enabled — touch the sensor or enter your password"
        font.pixelSize: 11; color: Theme.muted; wrapMode: Text.WordWrap
    }
    ActionButton {
        id: submitButton
        objectName: "access-submit"
        Layout.fillWidth: true
        text: root.preview || root.controller.responseRequired ? (root.login ? "Sign in" : "Unlock")
            : root.controller.busy ? "Authenticating…" : root.login && !root.controller.error ? "Continue" : "Try again"
        selected: true
        enabled: !root.preview && (!root.login || !!root.account) && (root.controller.responseRequired || !root.controller.busy)
        onClicked: root.submit()
    }
    Label {
        Layout.fillWidth: true; visible: root.preview
        horizontalAlignment: Text.AlignHCenter
        text: "Visual preview only — this does not lock your session"
        font.pixelSize: 11; color: Theme.good
    }
}
