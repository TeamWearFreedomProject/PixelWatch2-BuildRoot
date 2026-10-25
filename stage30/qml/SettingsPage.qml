import QtQuick

Rectangle {
    id:root
    color:"black"
    property var backend
    property bool integrated:false
    property bool motion:true
    signal back()
    signal style()
    signal about()
    signal usb()
    signal system()
    RoundButton { z:10;x:168;y:18;width:48;height:40;glyph:"back";motion:root.motion;onClicked:root.back() }
    Flickable {
        id:list
        objectName:"settingsList"
        x:50;y:68;width:284;height:272
        contentHeight:column.height+24;clip:true;boundsBehavior:Flickable.StopAtBounds
        Column {
            id:column;width:parent.width;spacing:10
            Text { width:parent.width;height:43;text:"設定";horizontalAlignment:Text.AlignHCenter;color:"white";font.pixelSize:29;font.weight:Font.Bold }
            Repeater {
                model:[{name:"Wi-Fi",kind:"wifi"},{name:"Bluetooth",kind:"bluetooth"},{name:"自動の明るさ",kind:"auto"},{name:"常時表示",kind:"aod"}]
                Rectangle {
                    required property var modelData
                    property bool checked: !root.backend ? false : modelData.kind==="wifi" ? root.backend.wifiOn : modelData.kind==="bluetooth" ? root.backend.bluetoothOn : modelData.kind==="auto" ? root.backend.autoBrightness : root.backend.alwaysOn
                    width:column.width;height:62;radius:22;color:"#1b1f25"
                    Text { x:20;anchors.verticalCenter:parent.verticalCenter;text:modelData.name;color:"#f5f6f8";font.pixelSize:17 }
                    Rectangle { x:216;y:19;width:48;height:26;radius:13;color:parent.checked?"#9cf45a":"#454b55"
                        Rectangle { x:parent.parent.checked?25:3;y:3;width:20;height:20;radius:10;color:parent.parent.checked?"#18220f":"#dce1e8" }
                    }
                    MouseArea { anchors.fill:parent;onClicked:{if(!root.backend)return;var k=parent.modelData.kind;if(k==="wifi")root.backend.toggleWifi();else if(k==="bluetooth")root.backend.toggleBluetooth();else if(k==="auto")root.backend.toggleAutoBrightness();else root.backend.toggleAlwaysOn()} }
                }
            }
            RoundButton { width:column.width;height:62;text:"USBモード";fill:"#1b1f25";onClicked:root.usb() }
            RoundButton { width:column.width;height:62;text:"Linux・システム";fill:"#1b1f25";onClicked:root.system() }
            RoundButton { width:column.width;height:62;text:"カラー・アニメーション";fill:"#1b1f25";motion:root.motion;onClicked:root.style() }
            RoundButton { width:column.width;height:62;text:"Aurora UIについて";fill:"#1b1f25";motion:root.motion;onClicked:root.about() }
            Text { width:column.width;text:root.integrated?"Aurora Shell":"Aurora Shell プレビュー";horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap;color:"#8792a1";font.pixelSize:13;lineHeight:1.5 }
        }
    }
}
