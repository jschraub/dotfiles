import QtQuick
import QtQuick.Controls as Controls
import Quickshell

Controls.AbstractButton {
    id: root
    property bool selected: false
    property bool dangerous: false
    property string hint: ""
    property string hintShortcut: ""
    property bool alignLeft: false
    property color textColor: Theme.text
    property bool tabularDigits: false
    property bool accessibleToggle: false
    horizontalPadding: 12
    property bool hintReady: false
    function updateHint() {
        hintReady = false;
        if ((hovered || visualFocus) && enabled && !pressed && hint.length > 0) hintDelay.restart();
        else hintDelay.stop();
    }
    onHoveredChanged: updateHint()
    onVisualFocusChanged: updateHint()
    onHintChanged: updateHint()
    onHintShortcutChanged: updateHint()
    onEnabledChanged: updateHint()
    onPressedChanged: updateHint()
    Timer { id: hintDelay; interval: 600; onTriggered: root.hintReady = true }
    implicitHeight: Math.max(34, contentItem.implicitHeight + 12)
    implicitWidth: contentItem.implicitWidth + horizontalPadding * 2
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Keys.onReturnPressed: event => { if (!event.isAutoRepeat && enabled) clicked(); }
    Keys.onEnterPressed: event => { if (!event.isAutoRepeat && enabled) clicked(); }
    background: Rectangle {
        radius: 7
        color: root.down ? Theme.hover : root.hovered || root.selected || root.visualFocus ? Theme.raised : "transparent"
        border.width: root.visualFocus ? 1 : 0
        border.color: Theme.accent
        Behavior on color { enabled: !Theme.reducedMotion; ColorAnimation { duration: 100 } }
    }
    TextMetrics {
        id: inkMetrics
        font: buttonLabel.font
        text: root.text
    }
    contentItem: Item {
        id: content
        readonly property rect ink: inkMetrics.tightBoundingRect
        // Reserve symmetric bearing space large enough to contain BOTH the
        // label's advance and the actual glyph ink, including fallback icons.
        readonly property real bearing: Math.max(0, ink.x, inkMetrics.advanceWidth - ink.x - ink.width)
        implicitWidth: root.alignLeft ? Math.max(inkMetrics.advanceWidth, ink.x + ink.width) - Math.min(0, ink.x)
                                      : ink.width + bearing * 2
        implicitHeight: buttonLabel.implicitHeight
        Label {
            id: buttonLabel
            objectName: "button-label"
            x: root.alignLeft || content.width < content.implicitWidth - 0.01 ? Math.max(0, -content.ink.x)
                : (content.width - content.ink.width) / 2 - content.ink.x
            width: Math.max(0, content.width - x)
            height: content.height
            text: root.text
            horizontalAlignment: Text.AlignLeft
            color: root.dangerous ? Theme.dangerText : root.selected ? Theme.accent : root.textColor
            font.features: root.tabularDigits ? ({ "tnum": 1 }) : ({})
        }
    }
    PopupWindow {
        id: tooltip
        objectName: "atelier-tooltip"
        anchor.item: root
        anchor.rect: Qt.rect(0, root.height + 8, root.width, 1)
        anchor.edges: Edges.Top
        anchor.gravity: Edges.Bottom
        anchor.adjustment: PopupAdjustment.SlideX | PopupAdjustment.FlipY
        grabFocus: false
        visible: root.hintReady && (root.hovered || root.visualFocus) && root.enabled && !root.pressed && root.hint.length > 0
        implicitWidth: Math.min(360, hintMeasure.implicitWidth + (root.hintShortcut ? shortcutText.implicitWidth + 8 : 0) + 24)
        implicitHeight: hintText.implicitHeight + 16
        color: "transparent"
        // Measure unconstrained text, not the wrapped label whose width depends
        // on this popup. Otherwise multiline hints can shrink and wrap early.
        Label {
            id: hintMeasure
            visible: false
            text: root.hint
            font.pixelSize: 12
            wrapMode: Text.NoWrap
            elide: Text.ElideNone
        }
        Rectangle { anchors.fill: parent; color: Theme.panel; radius: 7; border.color: Theme.line }
        Label {
            id: hintText
            x: 12; y: 8
            width: tooltip.width - 24 - (root.hintShortcut ? shortcutText.implicitWidth + 8 : 0)
            text: root.hint
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            elide: Text.ElideNone
            textFormat: Text.PlainText
        }
        Label {
            id: shortcutText
            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
            visible: !!root.hintShortcut
            text: root.hintShortcut
            textFormat: Text.PlainText
            font.pixelSize: 12; color: Theme.good
        }
    }
    Accessible.name: text
    Accessible.description: hint + (hintShortcut ? (hint ? "\n" : "") + "Shortcut: " + hintShortcut : "")
    Accessible.checkable: accessibleToggle
    Accessible.checked: accessibleToggle && selected
}
