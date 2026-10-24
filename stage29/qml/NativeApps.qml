import QtQuick
import Nemo.Configuration

Item {
    id:root
    property var hostGrid:typeof grid === "undefined" ? null : grid
    property alias displayShell:shell
    property var applications:typeof launcherModel === "undefined" ? null : launcherModel
    SystemBackend { id:system }
    ConfigurationValue { id:ready;key:"/org/aurora-ui/apps-ready";defaultValue:"" }
    AuroraShell {
        id:shell;anchors.fill:parent;page:"apps";backend:system;nativeModel:root.applications;integrated:true
        onHomeRequested:if(root.hostGrid)root.hostGrid.moveTo(0,0)
        onAppsRequested:page="apps"
    }
    Component.onCompleted: {
        // Reserve honeycomb drags for panning. The visible back button returns
        // to the clock; the stock grid still handles notifications and home.
        if(parent && parent.forbidTop!==undefined) {
            parent.forbidTop=true;parent.forbidBottom=true;parent.forbidLeft=true;parent.forbidRight=true
            if(hostGrid)hostGrid.changeAllowedDirections()
        }
        if(system.writable && hostGrid && applications)ready.value=Qt.resolvedUrl("NativeApps.qml").toString()
    }
    Connections {
        target:root.hostGrid
        function onCurrentVerticalPosChanged() { if(root.hostGrid.currentVerticalPos===0)shell.page="apps" }
    }
}
