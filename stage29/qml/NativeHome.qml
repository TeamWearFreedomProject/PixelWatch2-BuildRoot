import QtQuick
import Nemo.Configuration

// Loaded by the stock watchface Loader. Its creation context supplies grid,
// displayAmbient and wallClock, exactly as for AsteroidOS's built-in faces.
Item {
    id:root
    property var hostGrid: typeof grid === "undefined" ? null : grid
    property bool attached: false
    property var installedPanel: null
    SystemBackend { id:system }
    ConfigurationValue { id:ready;key:"/org/aurora-ui/home-ready";defaultValue:"" }
    AuroraShell {
        anchors.fill:parent
        backend:system
        integrated:true
        clockActive:typeof wallClock === "undefined" ? true : wallClock.enabled
        onAppsRequested:if(root.hostGrid)root.hostGrid.moveTo(0,1)
        onHomeRequested:if(root.hostGrid)root.hostGrid.moveTo(0,0)
        onPageChanged:if(page==="control" && root.attached){page="clock";root.hostGrid.moveTo(0,-1)}
    }
    Component {
        id:panel
        Item {
            property alias shell:panelShell
            property bool forbidLeft:true
            property bool forbidRight:true
            property bool forbidTop:true
            property bool forbidBottom:false
            property var panelsGrid
            SystemBackend { id:panelSystem }
            AuroraShell {
                id:panelShell
                anchors.fill:parent;page:"control";backend:panelSystem;integrated:true
                onHomeRequested:if(panelsGrid)panelsGrid.moveTo(0,0)
                onAppsRequested:if(panelsGrid)panelsGrid.moveTo(0,1)
            }
        }
    }
    function attach() {
        var g=hostGrid
        if(!g || attached || !g.cellAt || !g.movePanel || !g.addPanel || !g.removePanel) return
        if(!g.cellAt(0,-1) || g.cellAt(0,-64)) return
        // Park, rather than destroy, the original quick panel. Restore it when
        // this watchface is unloaded; no compositor binary or OS QML is changed.
        g.movePanel(0,-1,0,-64)
        installedPanel=g.addPanel(0,-1,panel)
        if(!installedPanel) { g.movePanel(0,-64,0,-1);return }
        attached=true;g.changeAllowedDirections()
        if(system.writable)ready.value=Qt.resolvedUrl("NativeHome.qml").toString()
    }
    function detach() {
        var g=hostGrid
        if(attached && g && g.cellAt(0,-1) && g.cellAt(0,-1).item===installedPanel) {
            g.removePanel(0,-1);g.movePanel(0,-64,0,-1);g.changeAllowedDirections()
        }
        attached=false;installedPanel=null
    }
    Timer { interval:100;running:true;onTriggered:root.attach() }
    Component.onDestruction:detach()
}
