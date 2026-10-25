import QtQuick
PageFrame {
    id:root;title:"Linux / システム"
    property var bridge
    signal terminal(string command)
    Column {
        x:61;y:119;width:262;spacing:12
        Rectangle { width:262;height:100;radius:24;color:"#19251f"
            Text { x:18;y:15;width:226;text:root.bridge?root.bridge.kernel+"\nuserspace "+root.bridge.bits+" bit":"";color:"#cfe4d2";font.family:"monospace";font.pixelSize:13;wrapMode:Text.Wrap;lineHeight:1.3 }
        }
        RoundButton { width:262;height:40;text:"カーネルログ  /  dmesg";onClicked:root.terminal("dmesg") }
        Row { spacing:10
            RoundButton { width:126;height:40;text:"メモリー";onClicked:root.terminal("memory") }
            RoundButton { width:126;height:40;text:"ストレージ";onClicked:root.terminal("df") }
        }
    }
}
