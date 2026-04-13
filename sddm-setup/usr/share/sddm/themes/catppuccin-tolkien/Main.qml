import QtQuick 2.15
import SddmComponents 2.0

Rectangle {
    id: root
    width: 640
    height: 480
    color: "#1e1e2e"

    property int sessionIndex: sessionModel.lastIndex
    property string userName: userModel.lastUser
    property bool loginFailed: false
    property string fontFamily: "CaskaydiaCove Nerd Font"

    TextConstants { id: textConstants }

    Connections {
        target: sddm
        function onLoginSucceeded() {
            loginFailed = false
        }
        function onLoginFailed() {
            loginFailed = true
            passwordField.text = ""
            errorAnimation.start()
        }
    }

    // ── Background ──
    Image {
        id: wallpaper
        anchors.fill: parent
        source: Qt.resolvedUrl("background.jpg")
        fillMode: Image.PreserveAspectCrop
        smooth: true
    }

    // ── Clock Timer ──
    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            var now = new Date()
            timeLabel.text = Qt.formatTime(now, "HH:mm")
            dateLabel.text = Qt.formatDate(now, "dddd, dd MMMM yyyy")
        }
    }

    // ── Time (top-right) ──
    Text {
        id: timeLabel
        anchors {
            top: parent.top
            right: parent.right
            topMargin: 30
            rightMargin: 30
        }
        color: "#cdd6f4"
        font.pixelSize: 90
        font.family: fontFamily
        renderType: Text.NativeRendering
    }

    // ── Date (below time, top-right) ──
    Text {
        id: dateLabel
        anchors {
            top: timeLabel.bottom
            right: parent.right
            topMargin: 10
            rightMargin: 30
        }
        color: "#cdd6f4"
        font.pixelSize: 25
        font.family: fontFamily
        renderType: Text.NativeRendering
    }

    // ── Center column: Avatar + Input ──
    Column {
        id: centerColumn
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -20
        spacing: 20

        // ── User Avatar (circular) ──
        Item {
            id: avatarContainer
            width: 108
            height: 108
            anchors.horizontalCenter: parent.horizontalCenter

            // Peach border ring
            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "transparent"
                border.color: "#fab387"
                border.width: 4
            }

            // Avatar image (hidden, used as source)
            Image {
                id: avatarSource
                anchors.centerIn: parent
                width: 100
                height: 100
                source: Qt.resolvedUrl("face.icon")
                fillMode: Image.PreserveAspectCrop
                smooth: true
                sourceSize.width: 200
                sourceSize.height: 200
                visible: false
                onStatusChanged: avatarCanvas.requestPaint()
            }

            // Fallback circle when image not loaded
            Rectangle {
                anchors.centerIn: parent
                width: 100
                height: 100
                radius: width / 2
                color: "#313244"
                visible: avatarSource.status !== Image.Ready
            }

            // Canvas draws the image clipped to a circle
            Canvas {
                id: avatarCanvas
                anchors.centerIn: parent
                width: 100
                height: 100
                visible: avatarSource.status === Image.Ready

                property var imgSrc: Qt.resolvedUrl("face.icon")

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.save()
                    ctx.beginPath()
                    ctx.arc(width / 2, height / 2, width / 2, 0, Math.PI * 2)
                    ctx.closePath()
                    ctx.clip()
                    ctx.drawImage(imgSrc, 0, 0, width, height)
                    ctx.restore()
                }

                Component.onCompleted: {
                    loadImage(imgSrc)
                }

                onImageLoaded: {
                    requestPaint()
                }
            }
        }

        // ── Username display ──
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: userName
            color: "#cdd6f4"
            font.pixelSize: 18
            font.family: fontFamily
            renderType: Text.NativeRendering
        }

        // ── Password Input Field ──
        Rectangle {
            id: inputContainer
            width: 300
            height: 60
            radius: 30
            color: "#313244"
            border.color: loginFailed ? "#f38ba8" : "#fab387"
            border.width: 4
            anchors.horizontalCenter: parent.horizontalCenter

            SequentialAnimation {
                id: errorAnimation
                NumberAnimation { target: inputContainer; property: "x"; to: inputContainer.x - 10; duration: 50 }
                NumberAnimation { target: inputContainer; property: "x"; to: inputContainer.x + 10; duration: 50 }
                NumberAnimation { target: inputContainer; property: "x"; to: inputContainer.x - 10; duration: 50 }
                NumberAnimation { target: inputContainer; property: "x"; to: inputContainer.x; duration: 50 }
            }

            Row {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 10

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "󰌾"
                    font.pixelSize: 20
                    font.family: fontFamily
                    color: "#fab387"
                    renderType: Text.NativeRendering
                }

                TextInput {
                    id: passwordField
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 50
                    height: parent.height
                    verticalAlignment: TextInput.AlignVCenter
                    color: "#cdd6f4"
                    echoMode: TextInput.Password
                    font.pixelSize: 16
                    font.family: fontFamily
                    focus: true
                    clip: true
                    selectionColor: "#fab387"
                    selectedTextColor: "#1e1e2e"
                    passwordCharacter: "●"
                    renderType: Text.NativeRendering

                    // Placeholder
                    Text {
                        anchors.fill: parent
                        anchors.verticalCenter: parent.verticalCenter
                        verticalAlignment: Text.AlignVCenter
                        text: "Password"
                        color: "#6c7086"
                        font.pixelSize: 16
                        font.family: fontFamily
                        font.italic: true
                        visible: passwordField.text.length === 0
                        renderType: Text.NativeRendering
                    }

                    Keys.onReturnPressed: sddm.login(userName, passwordField.text, sessionIndex)
                    Keys.onEnterPressed: sddm.login(userName, passwordField.text, sessionIndex)

                    KeyNavigation.tab: loginButton
                }
            }
        }

        // ── Error text ──
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: loginFailed ? "Login failed. Try again." : ""
            color: "#f38ba8"
            font.pixelSize: 14
            font.family: fontFamily
            font.italic: true
            renderType: Text.NativeRendering
        }
    }

    // ── Login Button (subtle, below input) ──
    Rectangle {
        id: loginButton
        width: 120
        height: 40
        radius: 20
        color: loginButtonArea.containsMouse ? "#fab387" : "transparent"
        border.color: "#fab387"
        border.width: 2
        anchors {
            top: centerColumn.bottom
            topMargin: 10
            horizontalCenter: parent.horizontalCenter
        }

        Text {
            anchors.centerIn: parent
            text: "Login"
            color: loginButtonArea.containsMouse ? "#1e1e2e" : "#fab387"
            font.pixelSize: 16
            font.family: fontFamily
            font.bold: true
            renderType: Text.NativeRendering
        }

        MouseArea {
            id: loginButtonArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: sddm.login(userName, passwordField.text, sessionIndex)
        }

        Behavior on color { ColorAnimation { duration: 150 } }
    }

    // ── Bottom bar: Session selector + Power buttons ──
    Row {
        id: bottomBar
        anchors {
            bottom: parent.bottom
            horizontalCenter: parent.horizontalCenter
            bottomMargin: 30
        }
        spacing: 30

        // ── Custom Session Selector ──
        Item {
            id: sessionSelector
            width: 200
            height: 36

            property bool expanded: false

            // Main button
            Rectangle {
                id: sessionButton
                anchors.fill: parent
                radius: 18
                color: "#313244"
                border.color: sessionMouseArea.containsMouse ? "#fab387" : "#45475a"
                border.width: 2

                Behavior on border.color { ColorAnimation { duration: 150 } }

                Text {
                    id: sessionText
                    anchors.left: parent.left
                    anchors.leftMargin: 15
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 40
                    color: "#cdd6f4"
                    font.pixelSize: 14
                    font.family: root.fontFamily
                    elide: Text.ElideRight
                    renderType: Text.NativeRendering
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: sessionSelector.expanded ? "▲" : "▼"
                    color: "#a6adc8"
                    font.pixelSize: 10
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    id: sessionMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sessionSelector.expanded = !sessionSelector.expanded
                }
            }
        }

        // Power buttons
        Row {
            spacing: 15
            anchors.verticalCenter: parent.verticalCenter

            // Suspend
            Rectangle {
                width: 36; height: 36; radius: 18
                color: suspendArea.containsMouse ? "#45475a" : "transparent"
                visible: sddm.canSuspend

                Text {
                    anchors.centerIn: parent
                    text: "⏾"
                    color: "#a6adc8"
                    font.pixelSize: 18
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    id: suspendArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sddm.suspend()
                }

                Behavior on color { ColorAnimation { duration: 150 } }
            }

            // Reboot
            Rectangle {
                width: 36; height: 36; radius: 18
                color: rebootArea.containsMouse ? "#45475a" : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "⟳"
                    color: "#a6adc8"
                    font.pixelSize: 20
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    id: rebootArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sddm.reboot()
                }

                Behavior on color { ColorAnimation { duration: 150 } }
            }

            // Power Off
            Rectangle {
                width: 36; height: 36; radius: 18
                color: powerArea.containsMouse ? "#45475a" : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "⏻"
                    color: "#a6adc8"
                    font.pixelSize: 18
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    id: powerArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sddm.powerOff()
                }

                Behavior on color { ColorAnimation { duration: 150 } }
            }
        }
    }

    // ── Session Dropdown (root level, above bottom bar) ──
    Rectangle {
        id: sessionDropdown
        width: 200
        height: sessionSelector.expanded ? sessionListView.contentHeight + 8 : 0
        radius: 12
        color: "#313244"
        border.color: "#45475a"
        border.width: 2
        clip: true
        visible: sessionSelector.expanded
        z: 100

        // Position dynamically relative to session button
        function updatePosition() {
            var mapped = sessionSelector.mapToItem(root, 0, 0)
            sessionDropdown.x = mapped.x
            sessionDropdown.y = mapped.y - sessionDropdown.height - 4
        }

        onVisibleChanged: if (visible) updatePosition()
        onHeightChanged: if (visible) updatePosition()

        Behavior on height { NumberAnimation { duration: 150 } }

        ListView {
            id: sessionListView
            anchors.fill: parent
            anchors.margins: 4
            model: sessionModel
            clip: true
            interactive: false

            delegate: Rectangle {
                width: sessionListView.width
                height: 32
                radius: 8

                property int sessionIdx: index
                property string sessionName: model.name

                color: itemMouseArea.containsMouse ? "#45475a" : "transparent"

                Behavior on color { ColorAnimation { duration: 100 } }

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: parent.sessionName
                    color: parent.sessionIdx === root.sessionIndex ? "#fab387" : "#cdd6f4"
                    font.pixelSize: 14
                    font.family: root.fontFamily
                    renderType: Text.NativeRendering
                }

                MouseArea {
                    id: itemMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.sessionIndex = parent.sessionIdx
                        sessionText.text = parent.sessionName
                        sessionSelector.expanded = false
                    }
                }
            }
        }
    }

    // ── Close dropdown when clicking elsewhere ──
    MouseArea {
        anchors.fill: parent
        z: -1
        onClicked: {
            sessionSelector.expanded = false
            passwordField.forceActiveFocus()
        }
    }

    // ── Session name helper ──
    Repeater {
        id: sessionNames
        model: sessionModel
        Item { property string name: model.name }
    }

    function sessionName(idx) {
        if (idx >= 0 && idx < sessionNames.count)
            return sessionNames.itemAt(idx).name
        return "Session"
    }

    onSessionIndexChanged: sessionText.text = sessionName(sessionIndex)

    // ── Focus password on load ──
    Component.onCompleted: {
        passwordField.forceActiveFocus()
        sessionText.text = sessionName(root.sessionIndex)
    }
}
