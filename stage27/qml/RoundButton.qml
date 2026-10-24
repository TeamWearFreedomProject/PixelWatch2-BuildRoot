import QtQuick 2.12

Rectangle {
    id: button
    width: 132
    height: 48
    radius: height / 2
    property alias text: label.text
    property color fill: "#202326"
    property color ink: "white"
    property string glyph: ""
    property bool motion: true
    signal clicked()
    color: area.pressed ? Qt.darker(fill, 1.25) : fill
    scale: area.pressed ? 0.94 : 1
    Behavior on scale { NumberAnimation { duration: button.motion ? 110 : 0; easing.type: Easing.OutCubic } }
    Row {
        anchors.centerIn: parent
        spacing: 8
        Icon { width: label.text ? 20 : 30; height: width; kind: button.glyph; ink: button.ink; visible: button.glyph !== ""; anchors.verticalCenter: parent.verticalCenter }
        Text { id: label; visible: text !== ""; color: button.ink; font.pixelSize: 17; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: area; anchors.fill: parent; onClicked: button.clicked() }
    Accessible.role: Accessible.Button
    Accessible.name: text || glyph
    Accessible.onPressAction: button.clicked()
}
