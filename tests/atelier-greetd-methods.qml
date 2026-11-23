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
        Component.onCompleted: {
            updateHardware(true, true, true, "");
            selectUser("fixture-account");
            begin();
        }
    }
    IpcHandler {
        target: "test"
        function password(): void { controller.chooseMethod("password"); }
        function respond(): void { controller.respond("fixture-protocol-secret"); }
        function status(): string {
            return JSON.stringify({ method: controller.method, needsResponse: controller.responseRequired,
                switching: controller.switching, choiceSent: controller.choiceSent });
        }
    }
}
