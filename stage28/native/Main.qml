import QtQuick 2.12

Rectangle {
    id: root
    width: 384; height: 384
    color: "black"
    Item {
        width: 384; height: 384
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 384
        AuroraShell { id: shell; anchors.fill: parent }
        RoundButton {
            x: 112; y: 310; width: 160; height: 44
            visible: shell.page === "about"
            text: "デモを閉じる"
            motion: shell.motion
            onClicked: Qt.quit()
        }
    }
}
