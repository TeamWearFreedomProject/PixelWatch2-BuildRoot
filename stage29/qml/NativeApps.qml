import QtQuick
import Nemo.Configuration
import org.asteroid.controls as AsteroidControls

Item {
    id:root
    property var hostGrid:typeof grid === "undefined" ? null : grid
    property alias displayShell:shell
    property var previousDirections:null
    property var applications:typeof launcherModel === "undefined" ? null : launcherModel
    SystemBackend { id:system }
    ConfigurationValue { id:ready;key:"/org/aurora-ui/apps-ready";defaultValue:"" }
    Component { id:nativeIcon;AsteroidControls.Icon { property var entry;name:entry&&entry.nativeObject?entry.nativeObject.iconId:"ios-help";color:"white" } }
    AuroraShell {
        id:shell;anchors.fill:parent;page:"apps";backend:system;nativeModel:root.applications;nativeIconDelegate:nativeIcon;integrated:true
        onHomeRequested:if(root.hostGrid)root.hostGrid.moveTo(0,0)
        onAppsRequested:page="apps"
    }
    Component.onCompleted: {
        // Reserve honeycomb drags for panning. The visible back button returns
        // to the clock; the stock grid still handles notifications and home.
        if(parent && parent.forbidTop!==undefined) {
            previousDirections={top:parent.forbidTop,bottom:parent.forbidBottom,left:parent.forbidLeft,right:parent.forbidRight}
            parent.forbidTop=true;parent.forbidBottom=true;parent.forbidLeft=true;parent.forbidRight=true
            if(hostGrid)hostGrid.changeAllowedDirections()
        }
        if(system.writable && hostGrid && applications)ready.value=Qt.resolvedUrl("NativeApps.qml").toString()
    }
    Component.onDestruction: {
        if(parent && previousDirections) {parent.forbidTop=previousDirections.top;parent.forbidBottom=previousDirections.bottom;parent.forbidLeft=previousDirections.left;parent.forbidRight=previousDirections.right;if(hostGrid)hostGrid.changeAllowedDirections()}
    }
    Connections {
        target:root.hostGrid
        function onCurrentVerticalPosChanged() { if(root.hostGrid.currentVerticalPos===0)shell.page="apps" }
    }
}
