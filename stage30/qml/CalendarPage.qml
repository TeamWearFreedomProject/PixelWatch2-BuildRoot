import QtQuick
PageFrame {
    id:root;title:Qt.formatDate(selected,"yyyy年 M月")
    property var bridge
    property var agendaModel
    property date selected:new Date()
    property bool editing:false
    property int minutes:9*60
    property string eventTitle:"予定"
    signal selectedDay(date day)
    function shiftMonth(delta){selected=new Date(selected.getFullYear(),selected.getMonth()+delta,1);selectedDay(selected)}
    RoundButton { x:69;y:72;width:36;height:30;text:"‹";onClicked:root.shiftMonth(-1) }
    RoundButton { x:279;y:72;width:36;height:30;text:"›";onClicked:root.shiftMonth(1) }
    Flickable {
        x:52;y:111;width:280;height:223;contentHeight:column.height+16;clip:true;boundsBehavior:Flickable.StopAtBounds
        Column {
            id:column;width:280;spacing:10
            Grid {
                columns:7;spacing:2
                Repeater { model:["日","月","火","水","木","金","土"];Text { width:38;height:20;text:modelData;color:index===0?"#f2859e":"#8794a6";font.pixelSize:11;horizontalAlignment:Text.AlignHCenter } }
                Repeater {
                    model:42
                    Rectangle {
                        required property int index
                        property date day:new Date(root.selected.getFullYear(),root.selected.getMonth(),1-new Date(root.selected.getFullYear(),root.selected.getMonth(),1).getDay()+index)
                        property bool current:Qt.formatDate(day,"yyyy-MM-dd")===Qt.formatDate(root.selected,"yyyy-MM-dd")
                        width:38;height:30;radius:15;color:current?"#9cf45a":"#171c23"
                        opacity:day.getMonth()===root.selected.getMonth()?1:0.35
                        Text { anchors.centerIn:parent;text:parent.day.getDate();color:parent.current?"#121b0b":"white";font.pixelSize:13 }
                        MouseArea { anchors.fill:parent;onClicked:{root.selected=parent.day;root.selectedDay(root.selected)} }
                    }
                }
            }
            Text { width:parent.width;text:Qt.formatDate(root.selected,"M月d日の予定");color:"#a9b5c3";font.pixelSize:15 }
            Repeater {
                model:root.bridge?root.bridge.localEvents:[]
                Rectangle {
                    required property var modelData
                    width:280;height:65;radius:21;color:"#1d2330"
                    Text { x:16;y:12;text:modelData.time;color:"#9cf45a";font.pixelSize:12 }
                    Text { x:16;y:31;width:204;text:modelData.title;color:"white";font.pixelSize:16;elide:Text.ElideRight }
                    RoundButton { x:231;y:20;width:33;height:30;text:"×";onClicked:root.bridge.removeEvent(parent.modelData.id) }
                }
            }
            Repeater {
                model:root.agendaModel
                Rectangle {
                    width:280;height:70;radius:21;color:"#1d2330"
                    Text { x:16;y:13;text:Qt.formatTime(model.occurrence.startTime,"HH:mm");color:"#7db9ff";font.pixelSize:12 }
                    Text { x:16;y:34;width:248;text:model.event.displayLabel;color:"white";font.pixelSize:16;elide:Text.ElideRight }
                }
            }
            Text { width:280;text:"時計内の予定・同期カレンダー";color:"#788698";font.pixelSize:11;horizontalAlignment:Text.AlignHCenter }
            RoundButton { width:280;height:47;text:"＋ 予定を追加";onClicked:root.editing=true }
        }
    }
    Rectangle {
        anchors.fill:parent;visible:root.editing;color:"black";z:20
        Text { x:65;y:77;width:254;text:"予定を追加";color:"white";font.pixelSize:25;horizontalAlignment:Text.AlignHCenter }
        Grid { x:66;y:124;columns:2;spacing:10
            Repeater { model:["予定","勉強","運動","用事"];RoundButton { width:121;height:41;text:modelData;fill:root.eventTitle===modelData?"#426e2e":"#212832";onClicked:root.eventTitle=modelData } }
        }
        Row { x:66;y:231;spacing:10
            RoundButton { width:52;text:"−";onClicked:root.minutes=(root.minutes+1425)%1440 }
            Text { width:112;height:48;text:("0"+Math.floor(root.minutes/60)).slice(-2)+":"+("0"+root.minutes%60).slice(-2);color:"white";font.pixelSize:28;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter }
            RoundButton { width:52;text:"＋";onClicked:root.minutes=(root.minutes+15)%1440 }
        }
        Row { x:67;y:297;spacing:10
            RoundButton { width:120;height:42;text:"戻る";onClicked:root.editing=false }
            RoundButton { width:120;height:42;text:"保存";fill:"#9cf45a";ink:"#101b08";onClicked:{var d=new Date(root.selected);d.setHours(Math.floor(root.minutes/60),root.minutes%60,0,0);root.bridge.addEvent(root.eventTitle,d.toISOString());root.editing=false} }
        }
    }
}
