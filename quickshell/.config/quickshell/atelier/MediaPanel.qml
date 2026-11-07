import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Mpris

ColumnLayout {
    id: root
    required property var shell
    property var service: shell.desktopServices || null
    readonly property var players: service ? service.players : []
    property var player: players.find(p => p.isPlaying) || players[0] || null
    onPlayersChanged: if (!players.includes(player)) player = players.find(p => p.isPlaying) || players[0] || null
    readonly property int panelHeight: 430
    spacing: 12
    Label { text: "Now playing"; font.pixelSize: 22; font.weight: Font.DemiBold }
    RowLayout {
        Repeater {
            model: root.players
            ActionButton { required property var modelData; text: modelData.identity; selected: modelData === root.player; onClicked: root.player = modelData }
        }
    }
    Label { Layout.fillWidth: true; text: root.player ? root.player.trackTitle || "Unknown track" : "No media players available"; font.pixelSize: 19; wrapMode: Text.WordWrap }
    Label { Layout.fillWidth: true; text: root.player ? root.player.trackArtist || root.player.identity : "Start music or video in an MPRIS-compatible app."; color: Theme.muted; wrapMode: Text.WordWrap }
    Label { Layout.fillWidth: true; visible: !!root.player && !!root.player.trackAlbum; text: root.player ? root.player.trackAlbum : ""; color: Theme.muted; font.pixelSize: 12 }
    Item { Layout.fillHeight: true }
    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        ActionButton { text: "󰒮  Previous"; enabled: !!root.player && root.player.canControl && root.player.canGoPrevious; onClicked: root.player.previous() }
        ActionButton { objectName: "media-toggle"; text: root.player && root.player.isPlaying ? "󰏤  Pause" : "󰐊  Play"; selected: true; enabled: !!root.player && root.player.canControl && root.player.canTogglePlaying; onClicked: root.player.togglePlaying() }
        ActionButton { text: "Next  󰒭"; enabled: !!root.player && root.player.canControl && root.player.canGoNext; onClicked: root.player.next() }
    }
    ActionButton { text: "Open player ↗"; enabled: !!root.player && root.player.canRaise; onClicked: { root.player.raise(); shell.close(); } }
}
