import QtQuick
import "HoneycombMath.js" as Hex

Item {
    id: root
    objectName: "honeycomb"
    property var entries: []
    property var cells: Hex.cells(entries.length)
    property real panX: 0
    property real panY: 0
    property bool motion: true
    property bool dragging: false
    property string caption: "ドラッグして探す"
    readonly property real panLimit: 100 * (Math.ceil(Math.sqrt(entries.length)) + 1)
    signal chosen(var entry)
    signal back()
    function recenter(index) {
        var p = Hex.logical(cells[index]); panX = -p.x; panY = -p.y
    }
    function reset() { panX=0; panY=0 }
    Behavior on panX { enabled: root.motion && !root.dragging; NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
    Behavior on panY { enabled: root.motion && !root.dragging; NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
    Repeater {
        model: root.entries.length
        Rectangle {
            required property int index
            readonly property var entry: root.entries[index]
            readonly property var spot: Hex.project(root.cells[index],root.panX,root.panY)
            objectName: "hexIcon_"+index
            x: spot.x-width/2; y: spot.y-height/2
            width: spot.diameter; height: width; radius: width/2
            color: entry.tint || "#3679f5"
            opacity: spot.opacity
            visible: opacity > 0
            Icon { anchors.centerIn: parent; width: parent.width*0.51; height: width; kind: entry.glyph || "apps"; ink: entry.glyph === "light" ? "#141820" : "white" }
            Accessible.role: Accessible.Button
            Accessible.name: entry.title || entry.app
            Accessible.onPressAction: root.chosen(entry)
        }
    }
    MouseArea {
        id: touch
        objectName: "honeycombDrag"
        anchors.fill: parent
        anchors.topMargin: 62
        anchors.bottomMargin: 38
        preventStealing: true
        property real startX: 0
        property real startY: 0
        property real oldX: 0
        property real oldY: 0
        property bool moved: false
        onPressed: mouse => { root.dragging=true; startX=mouse.x; startY=mouse.y; oldX=root.panX; oldY=root.panY; moved=false }
        onPositionChanged: mouse => {
            if (!pressed) return
            var dx=mouse.x-startX, dy=mouse.y-startY
            if (Math.sqrt(dx*dx+dy*dy)>7) moved=true
            if (moved) { root.panX=Hex.clamp(oldX+dx*1.45,root.panLimit); root.panY=Hex.clamp(oldY+dy*1.45,root.panLimit) }
        }
        onReleased: mouse => {
            root.dragging=false
            if (moved) return
            var nearest=-1, best=1e10
            for (var i=0;i<root.cells.length;++i) {
                var p=Hex.project(root.cells[i],root.panX,root.panY)
                var dx=mouse.x-p.x,dy=mouse.y+touch.y-p.y,dist=dx*dx+dy*dy
                if(p.opacity>0.25 && dist<Math.pow(Math.max(19,p.diameter/2),2) && dist<best) { best=dist;nearest=i }
            }
            if(nearest<0) return
            root.caption=root.entries[nearest].title
            if(Hex.project(root.cells[nearest],root.panX,root.panY).scale<0.48) root.recenter(nearest)
            else root.chosen(root.entries[nearest])
        }
        onCanceled: root.dragging=false
    }
    RoundButton { x:168; y:18; width:48; height:40; glyph:"back"; motion:root.motion; onClicked:root.back() }
    Text { x:65; y:344; width:254; horizontalAlignment:Text.AlignHCenter; elide:Text.ElideRight; text:root.caption; color:"#929ba8"; font.pixelSize:13 }
}
