import QtQuick
PageFrame {
    id:root;title:"USBモード"
    property var bridge
    property string pending:""
    function label(mode){return mode==="adb_mode"?"ADB":mode==="developer_mode"?"SSH / USBネットワーク":mode==="charging_only"?"充電専用":mode}
    Column {
        x:58;y:115;width:268;spacing:10
        Text { width:parent.width;text:root.bridge?"現在: "+root.label(root.bridge.usbMode):"未取得";color:"#96a7ba";font.pixelSize:13;horizontalAlignment:Text.AlignHCenter;elide:Text.ElideRight }
        Repeater {
            model:["adb_mode","developer_mode","charging_only"]
            RoundButton {
                required property string modelData
                width:268;height:48;text:root.label(modelData)
                fill:root.bridge&&root.bridge.usbMode===modelData?"#2d7040":"#202731"
                opacity:root.bridge&&root.bridge.usbModes.indexOf(modelData)>=0?1:0.45
                onClicked:if(root.bridge&&!root.bridge.usbBusy)root.pending=modelData
            }
        }
        Text { width:268;text:root.bridge?root.bridge.usbAddress:"";color:"#8f9faf";font.pixelSize:12;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap }
    }
    Component.onCompleted:if(bridge)bridge.refreshUsb()
    Timer { interval:3000;running:root.visible;repeat:true;onTriggered:if(root.bridge)root.bridge.refreshUsb() }
    Rectangle { anchors.fill:parent;visible:root.pending!=="";color:"black";z:20
        Text { x:65;y:105;width:254;text:root.label(root.pending);color:"white";font.pixelSize:24;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap }
        Text { x:65;y:174;width:254;text:root.pending==="adb_mode"?"PCからADBで接続します。":"ADB接続が切れます。\n時計のこの画面から戻せます。\n再接続時は元の既定モードです。";color:"#a8b5c5";font.pixelSize:15;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap;lineHeight:1.3 }
        Row { x:66;y:288;spacing:10
            RoundButton { width:121;height:44;text:"戻る";onClicked:root.pending="" }
            RoundButton { width:121;height:44;text:"切り替え";fill:"#9cf45a";ink:"#122009";onClicked:{root.bridge.switchUsb(root.pending);root.pending=""} }
        }
    }
}
