import QtQuick

// Compositor-context fixture using the grid contract in V1 c8c4d4bd46.
Item {
    id:fixture
    width:384;height:384
    property string scenario:"clock"
    property int launchCount:0
    property bool displayAmbient:false
    QtObject { id:wallClock;property bool enabled:true }
    QtObject {
        id:launcherModel
        property int count:18
        function get(i) { return {title:"アプリ "+(i+1),iconId:"",launchApplication:function(){fixture.launchCount++}} }
    }
    Item {
        id:grid;anchors.fill:parent
        property var records:({})
        property int currentVerticalPos:0
        property int currentHorizontalPos:0
        property int directionChanges:0
        function key(x,y){return x+","+y}
        function cellAt(x,y){return records[key(x,y)]}
        function place(r){r.item.x=r.col*384;r.item.y=r.row*384;r.item.width=384;r.item.height=384}
        function addPanel(x,y,component){var o=component.createObject(content);var r={item:o,col:x,row:y};place(r);o.panelsGrid=grid;records[key(x,y)]=r;return o}
        function movePanel(x,y,a,b){var r=cellAt(x,y);if(!r)return;delete records[key(x,y)];r.col=a;r.row=b;records[key(a,b)]=r;place(r)}
        function removePanel(x,y){var r=cellAt(x,y);if(r){r.item.destroy();delete records[key(x,y)]}}
        function moveTo(x,y){content.x=-x*384;content.y=-y*384;currentHorizontalPos=x;currentVerticalPos=y}
        function changeAllowedDirections(){directionChanges++}
        Item {
            id:content
            NativeHome { id:home;width:384;height:384 }
            Item {
                id:appsLoader;x:0;y:384;width:384;height:384
                property bool forbidTop:false
                property bool forbidBottom:false
                property bool forbidLeft:false
                property bool forbidRight:false
                NativeApps { id:apps;anchors.fill:parent }
            }
        }
    }
    Component { id:stockPanel;Item { property var panelsGrid } }
    Component.onCompleted:grid.addPanel(0,-1,stockPanel)
    function selectPage(name) {
        scenario=name
        if(name==="clock")grid.moveTo(0,0)
        else if(name==="apps") { apps.displayShell.page="apps";grid.moveTo(0,1) }
        else { var p=grid.cellAt(0,-1);if(p && p.item.shell)p.item.shell.page=name;grid.moveTo(0,-1) }
    }
    function checkIntegration() {
        if(!home.attached || !grid.cellAt(0,-64) || grid.cellAt(0,-1).item!==home.installedPanel)return "quick panel not installed with original parked"
        if(apps.displayShell.entries.length!==27)return "installed applications missing"
        apps.displayShell.choose(apps.displayShell.entries[9])
        if(launchCount!==1)return "native application callback not forwarded"
        if(!appsLoader.forbidTop || !appsLoader.forbidLeft)return "honeycomb drag not reserved"
        var original=grid.cellAt(0,-64).item
        home.detach()
        if(grid.cellAt(0,-64) || grid.cellAt(0,-1).item!==original)return "original panel not restored"
        home.attach()
        if(!home.attached)return "panel reinstallation failed"
        return "PASS"
    }
}
