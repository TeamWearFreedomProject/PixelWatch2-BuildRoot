import QtQuick
Rectangle {
    id:root;color:"#060b09"
    property var bridge
    property string command:"dmesg"
    property string filter:""
    property bool live:false
    signal back()
    function refresh(){if(bridge)bridge.runCommand(command)}
    RoundButton { z:10;x:168;y:16;width:48;height:38;glyph:"back";onClicked:root.back() }
    Text { x:65;y:69;width:254;text:"aurora:~$ "+root.command;color:"#9cf45a";font.family:"monospace";font.pixelSize:17;elide:Text.ElideRight }
    Row { x:56;y:101;spacing:6
        Repeater { model:["dmesg","uname","uptime","network"];RoundButton { width:64;height:29;text:modelData;fill:root.command===modelData?"#355743":"#192b24";onClicked:{root.command=modelData;root.refresh()} } }
    }
    Flickable {
        id:log;x:41;y:143;width:302;height:162;clip:true;contentHeight:lines.height;boundsBehavior:Flickable.StopAtBounds
        Text { id:lines;width:parent.width;text:root.bridge?root.bridge.output:"";color:"#c9e0d0";font.family:"monospace";font.pixelSize:11;wrapMode:Text.WrapAnywhere;textFormat:Text.PlainText }
    }
    Row { x:67;y:317;spacing:9
        RoundButton { width:120;height:33;text:"更新";onClicked:root.refresh() }
        RoundButton { width:120;height:33;text:root.live?"自動更新 ON":"自動更新 OFF";onClicked:root.live=!root.live }
    }
    Timer { interval:2000;running:root.visible&&root.live;repeat:true;onTriggered:root.refresh() }
    Text { x:100;y:354;width:184;text:"読み取り専用";color:"#627e69";font.pixelSize:10;horizontalAlignment:Text.AlignHCenter }
    Component.onCompleted:refresh()
}
