import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Pam

ShellRoot {
    AccessIdentity { id: accountInfo; mode: "lock" }
    // PamContext's empty user resolves the process's real UID natively. Public
    // avatar metadata never chooses an authentication identity or blocks unlock.
    PamContext { id: passwordPam; config: "atelier-lock" }
    PamContext { id: fingerprintPam; config: "atelier-fingerprint" }
    LockController {
        id: lockController
        password: passwordPam
        fingerprint: Quickshell.env("ATELIER_FINGERPRINT") === "1" ? fingerprintPam : null
        user: accountInfo.users.length ? accountInfo.users[0].user : ""
        secure: sessionLock.secure
        onAuthenticated: {
            sessionLock.locked = false;
            // Quickshell does not handle Qt.quit(). Exit only this instance,
            // after its authenticated unlock request has been dispatched.
            Qt.callLater(() => Quickshell.execDetached(["qs", "kill", "--pid", String(Quickshell.processId)]));
        }
    }
    WlSessionLock {
        id: sessionLock
        locked: true
        WlSessionLockSurface {
            color: Theme.background
            AccessScene { anchors.fill: parent; controller: lockController; identity: accountInfo }
        }
    }
    // Deliberately no unlock/cancel/password IPC, shortcuts, or preview bypass.
    IpcHandler { target: "lock"; function secure(): bool { return sessionLock.secure; } }
}
