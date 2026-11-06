import QtQuick

MouseArea {
    id: root
    objectName: "volume-wheel"
    required property var shell
    anchors.fill: parent
    z: 1
    acceptedButtons: Qt.NoButton
    scrollGestureEnabled: true
    enabled: !!shell.state.audio
    property real angleRemainder: 0
    property real pixelRemainder: 0
    function consume(angle, pixels) {
        if (!enabled || (!angle && !pixels)) return false;
        let steps = 0;
        if (angle) {
            angleRemainder += angle;
            steps = Math.trunc(angleRemainder / 120);
            angleRemainder -= steps * 120;
        } else {
            pixelRemainder += pixels;
            steps = Math.trunc(pixelRemainder / 40);
            pixelRemainder -= steps * 40;
        }
        // Relative operations use the real output state, not a possibly stale
        // status snapshot. The adapter serializes them with other audio writes.
        if (steps) shell.send("volume-step", { delta: Math.max(-100, Math.min(100, steps * 5)) });
        idle.restart();
        return true;
    }
    onWheel: event => { event.accepted = consume(event.angleDelta.y, event.pixelDelta.y); }
    Timer { id: idle; interval: 250; onTriggered: { root.angleRemainder = 0; root.pixelRemainder = 0; } }
}
