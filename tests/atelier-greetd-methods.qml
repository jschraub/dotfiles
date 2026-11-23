import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Greetd
import "." as Atelier

ShellRoot {
    Atelier.GreetdTransport { id: transport }
    Atelier.GreeterController {
        id: controller
        service: transport
        property var sleepAcknowledgements: []
        onFingerprintStoppedForSleep: generation => {
            sleepAcknowledgements = sleepAcknowledgements.concat([generation]);
        }
        Component.onCompleted: {
            updateHardware(true, true, true, "");
            selectUser("fixture-account");
            begin();
        }
    }
    IpcHandler {
        target: "test"
        function password(): void { controller.chooseMethod("password"); }
        function sleep(): void {
            controller.sleeping = true;
            controller.updateHardware(true, false, true, "Fingerprint paused for sleep/resume");
            controller.prepareForSleep(1);
        }
        function wake(): void {
            controller.updateHardware(true, true, true, "");
            controller.sleeping = false;
        }
        function respond(): void { controller.respond("fixture-protocol-secret"); }
        function status(): string {
            return JSON.stringify({ method: controller.method, needsResponse: controller.responseRequired,
                switching: controller.switching, choiceSent: controller.choiceSent,
                sleepAcknowledgements: controller.sleepAcknowledgements });
        }
    }
}
