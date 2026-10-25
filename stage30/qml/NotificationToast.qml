import QtQuick
Item {
    id:root;visible:notificationPreviewPresenter.notification!==null
    property var note:notificationPreviewPresenter.notification
    Rectangle {
        x:55;y:68;width:parent.width-110;height:Math.min(200,body.height+63);radius:26;color:"#253024"
        Column { id:body;x:20;y:18;width:parent.width-40;spacing:9
            Text { width:parent.width;text:root.note?root.note.appName:"";color:"#9cf45a";font.pixelSize:12;textFormat:Text.PlainText;elide:Text.ElideRight }
            Text { width:parent.width;text:root.note?root.note.previewSummary:"";color:"white";font.pixelSize:18;font.weight:Font.DemiBold;maximumLineCount:2;wrapMode:Text.Wrap;elide:Text.ElideRight;textFormat:Text.PlainText }
            Text { width:parent.width;text:root.note?root.note.previewBody:"";color:"#c3d0be";font.pixelSize:14;maximumLineCount:3;wrapMode:Text.Wrap;elide:Text.ElideRight;textFormat:Text.PlainText }
        }
        MouseArea { anchors.fill:parent;onClicked:notificationPreviewPresenter.showNextNotification() }
    }
    Timer { interval:4500;running:root.visible;onTriggered:notificationPreviewPresenter.showNextNotification() }
}
