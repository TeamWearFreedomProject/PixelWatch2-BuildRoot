import QtQuick
Rectangle {
    id:root;color:"black"
    property string title:""
    signal back()
    default property alias body:content.data
    Item { id:content;anchors.fill:parent }
    RoundButton { z:10;x:168;y:18;width:48;height:40;glyph:"back";onClicked:root.back() }
    Text { x:65;y:72;width:254;text:root.title;color:"white";font.pixelSize:24;font.weight:Font.Bold;horizontalAlignment:Text.AlignHCenter;elide:Text.ElideRight }
}
