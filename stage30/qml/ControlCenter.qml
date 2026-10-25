import QtQuick

Rectangle {
    id:root
    color:"black"
    property var backend
    property color accent:"#9cf45a"
    property bool motion:true
    signal settings()
    signal back()
    signal light()
    RoundButton { x:168;y:18;width:48;height:40;glyph:"back";motion:root.motion;onClicked:root.back() }
    Text { x:60;y:70;width:264;text:"コントロールセンター";horizontalAlignment:Text.AlignHCenter;color:"#f6f8fa";font.pixelSize:20;font.weight:Font.DemiBold }
    Text { x:80;y:101;width:224;text:root.backend && root.backend.battery>=0 ? "バッテリー  "+root.backend.battery+"%" : "AsteroidOS";horizontalAlignment:Text.AlignHCenter;color:"#959eaa";font.pixelSize:14 }
    Grid {
        x:62;y:132;columns:2;spacing:12
        RoundButton { objectName:"wifiToggle";width:124;height:66;glyph:"wifi";text:"Wi-Fi";fill:root.backend&&root.backend.wifiOn ? "#2788ef":"#20252d";motion:root.motion;onClicked:if(root.backend)root.backend.toggleWifi() }
        RoundButton { objectName:"bluetoothToggle";width:124;height:66;glyph:"bluetooth";text:"BT";fill:root.backend&&root.backend.bluetoothOn ? "#6166ee":"#20252d";motion:root.motion;onClicked:if(root.backend)root.backend.toggleBluetooth() }
        RoundButton { width:124;height:54;glyph:"light";text:"ライト";fill:"#33343b";motion:root.motion;onClicked:root.light() }
        RoundButton { width:124;height:54;glyph:"settings";text:"設定";fill:"#33343b";motion:root.motion;onClicked:root.settings() }
    }
    Rectangle {
        x:62;y:278;width:260;height:44;radius:22;color:"#242830"
        Icon { x:15;y:12;width:20;height:20;kind:"sun";ink:"#c0c8d2" }
        Rectangle { x:45;y:19;width:158;height:6;radius:3;color:"#4b515a"
            Rectangle { width:parent.width*(root.backend?root.backend.brightness:50)/100;height:6;radius:3;color:root.accent }
        }
        Text { x:207;y:13;width:43;horizontalAlignment:Text.AlignHCenter;text:root.backend?root.backend.brightness:"—";color:"white";font.pixelSize:14 }
        MouseArea { objectName:"brightnessSlider";anchors.fill:parent;preventStealing:true
            function updateValue(x) { if(root.backend)root.backend.setBrightness((x-45)/158*100) }
            onPressed:mouse=>updateValue(mouse.x)
            onPositionChanged:mouse=>{if(pressed)updateValue(mouse.x)}
        }
    }
    Text { x:64;y:333;width:256;text:root.backend?root.backend.message:"";color:"#a2acb8";font.pixelSize:11;horizontalAlignment:Text.AlignHCenter;elide:Text.ElideRight }
}
