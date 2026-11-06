import QtQuick
import Quickshell
import Quickshell.Services.Notifications

Scope {
    id: root
    required property var shell
    property bool dnd: false
    property var history: []
    property var toastItems: history.filter(n => n.live && n.popup && (!dnd || n.critical)).slice(0, 4)
    function remove(id) {
        const record = history.find(n => n.id === id);
        history = history.filter(n => n.id !== id);
        if (record && record.live) record.live.dismiss();
    }
    function clear() { history.slice().forEach(n => remove(n.id)); }
    function capture(notification) {
        const timeout = notification.expireTimeout;
        const critical = notification.urgency === NotificationUrgency.Critical;
        const record = { id: notification.id, app: notification.appName, title: notification.summary,
            body: notification.body, image: notification.image, icon: notification.appIcon,
            transient: notification.transient, critical: critical, live: notification,
            popup: !notification.lastGeneration, received: Date.now(),
            // v0.3.2 forwards the protocol's milliseconds, despite its docs
            // describing seconds. Covered by the real DBus expiration test.
            deadline: critical || timeout === 0 ? 0 : Date.now() + (timeout > 0 ? timeout : 5000) };
        const removed = history.filter(n => n.id !== notification.id);
        history = [record].concat(removed).slice(0, 100);
        removed.slice(99).forEach(n => { if (n.live) n.live.dismiss(); });
    }
    function closed(id) {
        history = history.filter(n => n.id !== id || !n.transient).map(n => n.id === id ? Object.assign({}, n, { live: null, popup: false }) : n);
    }
    NotificationServer {
        id: server
        actionsSupported: true
        bodySupported: true
        persistenceSupported: true
        imageSupported: true
        bodyMarkupSupported: false
        keepOnReload: true
        onNotification: notification => {
            notification.tracked = true;
            const id = notification.id;
            root.capture(notification);
            notification.closed.connect(() => root.closed(id));
        }
    }
    // Replacement IDs update an existing QObject, not the server's notification
    // signal. Keep its snapshot, popup and expiry synchronized with those updates.
    Variants {
        model: server.trackedNotifications.values
        Scope {
            required property var modelData
            Connections {
                target: modelData
                function onSummaryChanged() { root.capture(modelData); }
                function onBodyChanged() { root.capture(modelData); }
                function onExpireTimeoutChanged() { root.capture(modelData); }
                function onAppNameChanged() { root.capture(modelData); }
                function onImageChanged() { root.capture(modelData); }
                function onUrgencyChanged() { root.capture(modelData); }
            }
        }
    }
    Timer {
        interval: 250; running: true; repeat: true
        onTriggered: root.history.slice().forEach(n => {
            if (n.live && n.deadline > 0 && Date.now() >= n.deadline) n.live.expire();
        })
    }
    Toasts { shell: root.shell; service: root }
}
