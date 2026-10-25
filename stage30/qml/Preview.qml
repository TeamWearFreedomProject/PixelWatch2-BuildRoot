import QtQuick
import Aurora.System 1.0
Rectangle {
    id:root;width:384;height:384;color:"black"
    System { id:system }
    SystemBackend { id:settings;writable:!system.testMode }
    AuroraScene { id:shell;anchors.fill:parent;backend:settings;bridge:system }
    RoundButton { x:112;y:310;width:160;height:44;visible:shell.page==="about";text:"プレビューを閉じる";onClicked:Qt.quit() }
    Component.onCompleted:{system.selectDay(Qt.formatDate(shell.selectedDate,"yyyy-MM-dd"));system.sceneReady(shell)}
}
