import QtQuick
PageFrame {
    id:root;title:"通知"
    property var notificationModel
    property var bridge
    readonly property int count:notificationModel?notificationModel.itemCount:0
    ListView {
        id:list;x:49;y:115;width:286;height:221;clip:true;spacing:10
        boundsBehavior:Flickable.StopAtBounds;model:root.notificationModel
        delegate:Rectangle {
            id:card
            required property var object
            width:list.width;height:Math.max(128,texts.height+44);radius:25;color:"#191e26"
            Column {
                id:texts;x:20;y:15;width:246;spacing:8
                Text { width:parent.width;text:card.object.appName;color:"#9cf45a";font.pixelSize:12;elide:Text.ElideRight;textFormat:Text.PlainText }
                Text { width:parent.width;text:card.object.summary;color:"white";font.pixelSize:18;font.weight:Font.DemiBold;wrapMode:Text.Wrap;textFormat:Text.PlainText }
                Text { width:parent.width;text:card.object.body;color:"#c2cad4";font.pixelSize:14;wrapMode:Text.Wrap;textFormat:Text.PlainText }
                Row {
                    spacing:8
                    RoundButton { width:115;height:36;text:"開く";visible:card.object.actions&&card.object.actions.indexOf("default")>=0;onClicked:card.object.actionInvoked("default") }
                    RoundButton { width:115;height:36;text:"消す";visible:card.object.userRemovable;onClicked:if(root.bridge)root.bridge.dismissNotification(card.object.replacesId) }
                }
            }
        }
    }
    Text { x:65;y:186;width:254;visible:root.count===0;text:"通知はありません";horizontalAlignment:Text.AlignHCenter;color:"#8996a6";font.pixelSize:18 }
}
