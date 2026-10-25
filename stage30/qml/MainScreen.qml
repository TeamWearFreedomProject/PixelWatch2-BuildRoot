import QtQuick
import org.nemomobile.lipstick
import org.nemomobile.calendar
import org.asteroid.controls as AsteroidControls
import Aurora.System 1.0
import "../desktop.js" as Desktop

Item {
    id:root
    property bool aboutToOpen:false
    property bool aboutToClose:false
    property bool aboutToMinimize:false
    property bool activeDisplay:true
    onAboutToCloseChanged:if(aboutToClose)shell.openPage("clock")
    onAboutToMinimizeChanged:if(aboutToMinimize)shell.openPage("clock")
    System { id:system }
    SystemBackend { id:settings;writable:!system.testMode }
    LauncherModel { id:apps }
    NotificationListModel { id:notifications }
    AgendaModel {
        id:agenda
        startDate:new Date(shell.selectedDate.getFullYear(),shell.selectedDate.getMonth(),shell.selectedDate.getDate(),0,0,0)
        endDate:new Date(shell.selectedDate.getFullYear(),shell.selectedDate.getMonth(),shell.selectedDate.getDate(),23,59,59)
    }
    Component { id:nativeIcon;AsteroidControls.Icon { property var entry;name:entry&&entry.nativeObject?entry.nativeObject.iconId:"ios-help";color:"white" } }
    QtObject {
        id:position
        readonly property int currentVerticalPos:shell.page==="clock"?0:shell.page==="apps"?1:shell.page==="control"?-1:2
        readonly property int currentHorizontalPos:shell.page==="notifications"?-1:shell.page==="calendar"?1:0
    }
    AuroraScene {
        id:shell;anchors.fill:parent;backend:settings;bridge:system;nativeModel:apps;nativeIconDelegate:nativeIcon
        notificationModel:notifications;agendaModel:agenda;clockActive:root.activeDisplay
    }
    Connections {
        target:Lipstick.compositor
        function onDisplayAboutToBeOn(){root.activeDisplay=true}
        function onDisplayAboutToBeOff(){root.activeDisplay=false;shell.openPage("clock")}
        function onDisplayAmbientEntered(){root.activeDisplay=false}
        function onDisplayAmbientLeft(){root.activeDisplay=true}
        function onDisplayAmbientUpdate(){shell.now=new Date();ambientDelay.restart()}
        function onHomeActiveChanged(){if(Lipstick.compositor.homeActive)shell.openPage("clock")}
    }
    Timer { id:ambientDelay;interval:200;onTriggered:Lipstick.compositor.setAmbientUpdatesEnabled(false) }
    Component.onCompleted:{Desktop.desktop=root;Desktop.panelsGrid=position;system.selectDay(Qt.formatDate(shell.selectedDate,"yyyy-MM-dd"));system.sceneReady(shell)}
}
