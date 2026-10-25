import QtQuick
PageFrame {
    id:root;title:"今日の歩数"
    property var bridge
    Text { x:65;y:140;width:254;text:root.bridge&&root.bridge.stepsValid?root.bridge.steps.toLocaleString(Qt.locale(),'f',0):"—";color:"#9cf45a";font.pixelSize:64;font.weight:Font.Bold;horizontalAlignment:Text.AlignHCenter }
    Text { x:65;y:217;width:254;text:root.bridge&&root.bridge.stepsAvailable?(root.bridge.stepsValid?"歩":"計測待ち") :"歩数センサーを取得できません";color:"#a5b3c3";font.pixelSize:16;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap }
    Text { x:76;y:277;width:232;text:"このUIで記録した当日の歩数\n保存して次の起動へ引き継ぎます";color:"#77879b";font.pixelSize:12;horizontalAlignment:Text.AlignHCenter;lineHeight:1.5 }
}
