import QtQuick 2.12

Item {
    id: page
    property var shell
    default property alias content: body.data
    Item { id: body; anchors.fill: parent }
    // Recreate the navigation control with its page, including offscreen renders.
    RoundButton {
        objectName: "backButton"
        z: 10
        x: 168; y: 18; width: 48; height: 40
        glyph: "back"
        fill: page.shell && page.shell.page === "light" ? "#d5d8db" : "#17191c"
        ink: page.shell && page.shell.page === "light" ? "black" : "#c6cbd1"
        motion: page.shell ? page.shell.motion : false
        onClicked: if (page.shell) page.shell.openPage("apps")
    }
}
