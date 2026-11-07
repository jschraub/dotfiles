import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property var flow
    signal focusResponse(real y, real height)
    spacing: 14
    function submit() {
        if (!flow || !flow.isResponseRequired) return;
        const answer = response.text;
        response.text = "";
        flow.submit(answer); // Direct native polkit conversation, never adapter/IPC/argv.
    }
    function reset() {
        response.text = "";
        if (flow && flow.isResponseRequired) { response.forceActiveFocus(); focusResponse(response.y, response.height); }
    }
    onFlowChanged: Qt.callLater(reset)
    Component.onCompleted: Qt.callLater(reset)
    Component.onDestruction: response.text = ""
    Connections {
        target: root.flow
        ignoreUnknownSignals: true
        function onInputPromptChanged() { root.reset(); }
        function onIsResponseRequiredChanged() { root.reset(); }
        function onAuthenticationFailed() { root.reset(); }
        function onIsCompletedChanged() { response.text = ""; }
        function onSelectedIdentityChanged() { root.reset(); }
    }
    Label { text: "Authentication required"; font.pixelSize: 22; font.weight: Font.DemiBold }
    Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: root.flow ? root.flow.message : "" }
    Label { Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; text: root.flow ? root.flow.actionId : ""; font.pixelSize: 11; color: Theme.muted }
    Repeater {
        model: root.flow && root.flow.identities.length > 1 ? root.flow.identities : []
        ActionButton {
            required property var modelData
            Layout.fillWidth: true
            text: modelData.displayName || modelData.string
            selected: root.flow.selectedIdentity === modelData
            onClicked: { response.text = ""; root.flow.selectedIdentity = modelData; }
        }
    }
    Label {
        visible: !!root.flow && !!root.flow.selectedIdentity
        text: root.flow && root.flow.selectedIdentity ? "Authenticate as " + (root.flow.selectedIdentity.displayName || root.flow.selectedIdentity.string) : ""
        color: Theme.muted
    }
    Label { text: root.flow ? root.flow.inputPrompt : ""; visible: !!root.flow && root.flow.isResponseRequired }
    SearchField {
        id: response
        objectName: "authentication-response"
        Layout.fillWidth: true
        enabled: !!root.flow && root.flow.isResponseRequired
        echoMode: root.flow && root.flow.responseVisible ? TextInput.Normal : TextInput.Password
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | (root.flow && !root.flow.responseVisible ? Qt.ImhHiddenText : 0)
        placeholderText: "Authentication response"
        onAccepted: root.submit()
        onActiveFocusChanged: if (activeFocus) root.focusResponse(y, height)
    }
    Label {
        Layout.fillWidth: true; wrapMode: Text.WordWrap
        visible: !!root.flow && (!!root.flow.supplementaryMessage || root.flow.failed)
        text: root.flow ? root.flow.supplementaryMessage || "Authentication failed. Please try again." : ""
        color: root.flow && (root.flow.supplementaryIsError || root.flow.failed) ? Theme.danger : Theme.muted
    }
    RowLayout {
        Layout.fillWidth: true
        ActionButton { objectName: "auth-cancel"; text: "Cancel"; onClicked: if (root.flow) { response.text = ""; root.flow.cancelAuthenticationRequest(); } }
        Item { Layout.fillWidth: true }
        ActionButton { objectName: "auth-submit"; text: "Authenticate"; selected: true; enabled: !!root.flow && root.flow.isResponseRequired; onClicked: root.submit() }
    }
}
