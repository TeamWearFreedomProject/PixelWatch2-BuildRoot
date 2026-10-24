import QtQuick

Rectangle {
    width:384;height:384;color:"black"
    SystemBackend { id:system;writable:!captureMode }
    AuroraShell { id:shell;anchors.fill:parent;backend:system }
    RoundButton { x:112;y:310;width:160;height:44;visible:shell.page==="about";text:"プレビューを閉じる";motion:shell.motion;onClicked:Qt.quit() }
}
