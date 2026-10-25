import QtQuick

Rectangle {
    id: root
    objectName: "auroraShell"
    width: 384
    height: 384
    color: "black"
    clip: true
    property string page: "clock"
    property var bridge:null
    property var notificationModel:null
    property var agendaModel:null
    property date selectedDate:new Date()
    property string terminalCommand:"dmesg"
    onSelectedDateChanged:if(bridge)bridge.selectDay(Qt.formatDate(selectedDate,"yyyy-MM-dd"))
    property var backend: null
    property var nativeModel: null
    property Component nativeIconDelegate:null
    property bool integrated: false
    property bool clockActive: true
    property string returnPage: "apps"
    signal homeRequested()
    signal appsRequested()
    readonly property var entries: makeEntries()
    function makeEntries() {
        var data = [
          {app:"clock",title:"時計",glyph:"clock",tint:"#287cfb"},
          {app:"settings",title:"設定",glyph:"settings",tint:"#6e7888"},
          {app:"stopwatch",title:"ストップウォッチ",glyph:"stopwatch",tint:"#ff853c"},
          {app:"timer",title:"タイマー",glyph:"timer",tint:"#7959ed"},
          {app:"calculator",title:"電卓",glyph:"calculator",tint:"#e6b742"},
          {app:"control",title:"コントロールセンター",glyph:"control",tint:"#328fbe"},
          {app:"light",title:"ライト",glyph:"light",tint:"#dce4ed"},
          {app:"style",title:"カラー",glyph:"style",tint:"#df5cac"},
          {app:"about",title:"Aurora UI",glyph:"about",tint:"#278d81"}
        ]
        var extra=[{app:"notifications",title:"通知",glyph:"bell",tint:"#f2756c"},{app:"calendar",title:"カレンダー",glyph:"calendar",tint:"#e65b83"},{app:"usb",title:"USB",glyph:"usb",tint:"#5298a6"},{app:"steps",title:"歩数",glyph:"steps",tint:"#3db57d"},{app:"terminal",title:"Linuxコンソール",glyph:"terminal",tint:"#4f8764"},{app:"system",title:"システム",glyph:"system",tint:"#6278a1"}]
        data=data.concat(extra)
        if (nativeModel) for(var i=0;i<nativeModel.count;++i) {
            var obj=nativeModel.get(i)
            if(/asteroid-(settings|calendar|calculator|stopwatch|timer|flashlight)\.desktop$/.test(obj.filePath||""))continue
            data.push({app:"native",title:obj.title,glyph:"apps",tint:["#4186ed","#e65772","#24a87b","#9b67ed","#ed9a36"][i%5],nativeObject:obj})
        }
        return data
    }
    function choose(entry) {
        if(entry.nativeObject) { entry.nativeObject.launchApplication(); return }
        openPage(entry.app)
    }
    function goBack() { openPage(returnPage) }
    Connections {
        target: root.backend
        function onAccentChanged() { root.accent=root.backend.accent }
        function onMotionChanged() { root.motion=root.backend.motion }
    }
    onBackendChanged: if(backend) { accent=backend.accent; motion=backend.motion }
    onAccentChanged: if(backend && backend.writable && backend.accent!==accent.toString())backend.accent=accent.toString()
    onMotionChanged: if(backend && backend.writable && backend.motion!==motion)backend.motion=motion
    property color accent: "#9cf45a"
    property bool motion: true
    property date now: new Date()
    property bool stopwatchRunning: false
    property double stopwatchStart: 0
    property double stopwatchSaved: 0
    property double stopwatchElapsed: 0
    property bool timerRunning: false
    property double timerDeadline: 0
    property int timerRemaining: 0
    property bool timerFinished: false
    property string calculation: "0"
    property var operand: null
    property string operation: ""
    property bool freshNumber: true
    property bool previewTime: false
    readonly property int appCount: entries.length

    function openPage(name) {
        var previous=page
        if(name==="clock") {page="clock";returnPage="apps";return}
        if(name==="settings")returnPage=previous==="control"?"control":"apps"
        else if(name==="style"||name==="about")returnPage=previous==="settings"?"settings":"apps"
        else if(name==="usb"||name==="system")returnPage=previous==="settings"?"settings":"apps"
        else if(name==="terminal")returnPage=previous==="system"?"system":"apps"
        else returnPage="apps"
        page=name
    }
    function stopwatchToggle() {
        if (stopwatchRunning) {
            stopwatchSaved += Date.now() - stopwatchStart
            stopwatchElapsed = stopwatchSaved
            stopwatchRunning = false
        } else {
            stopwatchStart = Date.now()
            stopwatchRunning = true
        }
    }
    function stopwatchReset() {
        stopwatchRunning = false; stopwatchSaved = 0; stopwatchElapsed = 0
    }
    function startTimer(seconds) {
        timerDeadline = Date.now() + seconds * 1000
        timerRemaining = seconds; timerFinished = false; timerRunning = true
    }
    function cancelTimer() { timerRunning = false; timerFinished = false; timerRemaining = 0 }
    function formatDuration(ms, hundredths) {
        var seconds = Math.floor(ms / 1000)
        var s = ("0" + seconds % 60).slice(-2)
        var m = ("0" + Math.floor(seconds / 60)).slice(-2)
        return m + ":" + s + (hundredths ? "." + ("0" + Math.floor(ms % 1000 / 10)).slice(-2) : "")
    }
    function calculate(key) {
        if (key === "C") { calculation = "0"; operand = null; operation = ""; freshNumber = true; return }
        if (key === "+" || key === "−" || key === "×" || key === "÷" || key === "=") {
            var n = Number(calculation)
            if (operand !== null && !freshNumber && operation) {
                var v = operation === "+" ? operand + n : operation === "−" ? operand - n : operation === "×" ? operand * n : operand / n
                calculation = isFinite(v) ? String(Number(v.toPrecision(10))) : "Error"
                n = Number(calculation)
            }
            operand = key === "=" || !isFinite(n) ? null : n
            operation = key === "=" ? "" : key
            freshNumber = true
        } else {
            if (freshNumber || calculation === "Error") { calculation = key === "." ? "0." : key; freshNumber = false }
            else if (key === ".") { if (calculation.indexOf(".") < 0) calculation += "." }
            else if (calculation.length < 10) calculation = calculation === "0" ? key : calculation + key
        }
    }

    Timer {
        interval: 1000; repeat: true; running: root.visible && root.clockActive && root.page === "clock"
        onTriggered: root.now = new Date()
    }
    Timer {
        interval: root.page === "stopwatch" ? 40 : 500
        repeat: true; running: root.clockActive && (root.stopwatchRunning || root.timerRunning)
        onTriggered: {
            if (root.stopwatchRunning) root.stopwatchElapsed = root.stopwatchSaved + Date.now() - root.stopwatchStart
            if (root.timerRunning) {
                root.timerRemaining = Math.max(0, Math.ceil((root.timerDeadline - Date.now()) / 1000))
                if (root.timerRemaining === 0) { root.timerRunning = false; root.timerFinished = true }
            }
        }
    }
    Item {
        id: face
        width: 384; height: 384
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 384
        Loader {
            id: content
            anchors.fill: parent
            sourceComponent: root.page === "clock" ? clockPage : root.page === "apps" ? appsPage : root.page === "stopwatch" ? stopwatchPage : root.page === "timer" ? timerPage : root.page === "calculator" ? calculatorPage : root.page === "light" ? lightPage : root.page === "style" ? stylePage : root.page === "control" ? controlPage : root.page === "settings" ? settingsPage : root.page === "notifications" ? notificationsPage : root.page === "calendar" ? calendarPage : root.page === "usb" ? usbPage : root.page === "steps" ? stepsPage : root.page === "terminal" ? terminalPage : root.page === "system" ? systemPage : aboutPage
            onLoaded: { root.now = new Date(); appearance.restart() }
        }
        ParallelAnimation {
            id: appearance
            NumberAnimation { target: content; property: "opacity"; from: root.motion ? 0 : 1; to: 1; duration: root.motion ? 190 : 0 }
            NumberAnimation { target: content; property: "scale"; from: root.motion ? 0.94 : 1; to: 1; duration: root.motion ? 230 : 0; easing.type: Easing.OutCubic }
        }
    }
    Component {
        id: clockPage
        Item {
            MouseArea {
                anchors.fill:parent
                property real sx:0
                property real sy:0
                onPressed:mouse=>{sx=mouse.x;sy=mouse.y}
                onReleased:mouse=>{var dx=mouse.x-sx,dy=mouse.y-sy;if(Math.max(Math.abs(dx),Math.abs(dy))<45)return;if(Math.abs(dy)>Math.abs(dx))root.openPage(dy>0?"control":"apps");else root.openPage(dx>0?"notifications":"calendar")}
            }
            RoundButton { x:158;y:54;width:68;height:38;glyph:"control";motion:root.motion;onClicked:root.openPage("control") }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 23; text: "A U R O R A"; color: root.accent; font.pixelSize: 14; font.weight: Font.DemiBold }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 105; text: root.previewTime ? "SUN, 25 OCT" : Qt.formatDate(root.now, "ddd, d MMM").toUpperCase(); color: "#91979e"; font.pixelSize: 18 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 137; text: root.previewTime ? "09:00" : Qt.formatTime(root.now, "hh:mm"); color: "#f7f9fb"; font.pixelSize: 82; font.weight: Font.Bold; font.letterSpacing: -3 }
            Text { x:92;y:253;width:200;text:root.bridge&&root.bridge.stepsValid?root.bridge.steps+" 歩":"歩数 —";color:"#9ba99d";font.pixelSize:13;horizontalAlignment:Text.AlignHCenter }
            RoundButton { x:57;y:285;width:50;height:42;glyph:"bell";onClicked:root.openPage("notifications") }
            RoundButton { x:277;y:285;width:50;height:42;glyph:"calendar";onClicked:root.openPage("calendar") }
            Rectangle { x: 156; y: 240; width: 72; height: 5; radius: 3; color: root.accent }
            RoundButton { objectName: "appsButton"; x: 122; y: 281; width: 140; height: 48; text: "アプリ"; glyph: "apps"; fill: "#22262a"; motion: root.motion; onClicked: root.openPage("apps") }
        }
    }
    Component {
        id: appsPage
        Honeycomb { entries:root.entries;nativeIconDelegate:root.nativeIconDelegate;motion:root.motion;onChosen:entry=>root.choose(entry);onBack:{ if(root.integrated)root.homeRequested();else root.openPage("clock") } }
    }
    Component {
        id:controlPage
        ControlCenter { backend:root.backend;accent:root.accent;motion:root.motion
            onSettings:root.openPage("settings")
            onLight:root.openPage("light")
            onBack:{ if(root.integrated)root.homeRequested();else root.openPage("clock") }
        }
    }
    Component {
        id:settingsPage
        SettingsPage { backend:root.backend;integrated:root.integrated;motion:root.motion
            onUsb:root.openPage("usb");onSystem:root.openPage("system")
            onBack:root.openPage("control");onStyle:root.openPage("style");onAbout:root.openPage("about") }
    }
    Component {
        id: stopwatchPage
        AppPage {
            shell: root
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 83; text: "ストップウォッチ"; color: "#a3aab2"; font.pixelSize: 18 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 141; text: root.formatDuration(root.stopwatchElapsed, true); color: "white"; font.pixelSize: 48; font.weight: Font.DemiBold; font.family: "monospace" }
            RoundButton { objectName: "stopwatchToggle"; x: 61; y: 234; width: 128; height: 52; text: root.stopwatchRunning ? "停止" : "開始"; fill: root.accent; ink: "#10180b"; motion: root.motion; onClicked: root.stopwatchToggle() }
            RoundButton { objectName: "stopwatchReset"; x: 199; y: 234; width: 124; height: 52; text: "リセット"; motion: root.motion; onClicked: root.stopwatchReset() }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 316; text: "AURORA TOOLS"; color: "#5b646e"; font.pixelSize: 12; font.letterSpacing: 1 }
        }
    }
    Component {
        id: timerPage
        AppPage {
            shell: root
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 80; text: "タイマー"; color: "#a3aab2"; font.pixelSize: 18 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 118; text: root.timerFinished ? "終了" : root.formatDuration(root.timerRemaining * 1000, false); color: root.timerFinished ? root.accent : "white"; font.pixelSize: 60; font.weight: Font.Bold }
            Row {
                x: 58; y: 214; spacing: 8
                Repeater {
                    model: [1,5,10]
                    RoundButton { width: 84; height: 48; text: modelData + "分"; fill: "#292331"; motion: root.motion; onClicked: root.startTimer(modelData * 60) }
                }
            }
            RoundButton { x: 124; y: 280; width: 136; text: "取り消す"; motion: root.motion; onClicked: root.cancelTimer() }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 337; text: "終了は画面表示でお知らせ"; color: "#78828d"; font.pixelSize: 12 }
        }
    }
    Component {
        id: calculatorPage
        AppPage {
            shell: root
            RoundButton { x: 74; y: 73; width: 40; height: 36; text: "C"; motion: root.motion; onClicked: root.calculate("C") }
            Text { x: 124; y: 70; width: 169; height: 42; horizontalAlignment: Text.AlignRight; text: root.calculation; color: "white"; font.pixelSize: 31; fontSizeMode: Text.Fit; minimumPixelSize: 17 }
            Grid {
                x: 74; y: 124; columns: 4; spacing: 7
                Repeater {
                    model: ["7","8","9","÷","4","5","6","×","1","2","3","−","0",".","=","+"]
                    RoundButton {
                        width: 54; height: 36; text: modelData
                        fill: modelData === "=" ? root.accent : index % 4 === 3 ? "#3c3020" : "#24272b"
                        ink: modelData === "=" ? "#10180b" : "white"; motion: root.motion
                        onClicked: root.calculate(modelData)
                    }
                }
            }
        }
    }
    Component {
        id: lightPage
        AppPage {
            shell: root
            Rectangle { anchors.fill: parent; color: "#ffffff" }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 290; text: "戻るボタンで終了"; color: "#666b70"; font.pixelSize: 15 }
        }
    }
    Component {
        id: stylePage
        AppPage {
            shell: root
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 80; text: "見た目"; color: "white"; font.pixelSize: 25; font.weight: Font.DemiBold }
            Rectangle {
                x: 62; y: 127; width: 260; height: 92; radius: 28; color: "#191c20"
                Text { x: 22; y: 13; text: "アクセント"; color: "#b7bec6"; font.pixelSize: 14 }
                Row {
                    x: 22; y: 43; spacing: 18
                    Repeater {
                        model: ["#9cf45a","#6fbaff","#ff9b62","#d59dff"]
                        Rectangle {
                            width: 40; height: 32; radius: 16; color: modelData
                            border.width: root.accent.toString() === modelData ? 3 : 0; border.color: "white"
                            MouseArea { anchors.fill: parent; onClicked: root.accent = modelData }
                        }
                    }
                }
            }
            RoundButton { objectName: "motionButton"; x: 62; y: 235; width: 260; height: 62; text: root.motion ? "アニメーション：オン" : "アニメーション：オフ"; fill: "#191c20"; motion: root.motion; onClicked: root.motion = !root.motion }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 321; text: "カラーと動きの設定を保存"; color: "#78828d"; font.pixelSize: 13 }
        }
    }
    Component {
        id: aboutPage
        AppPage {
            shell: root
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 92; text: "Aurora UI"; color: root.accent; font.pixelSize: 36; font.weight: Font.Bold }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 145; text: "Stage 30 · Aurora Shell"; color: "#b0b8c0"; font.pixelSize: 16 }
            Rectangle {
                x: 62; y: 198; width: 260; height: 96; radius: 27; color: "#191c20"
                Text { anchors.centerIn: parent; text: "AsteroidOS 2.2 / Qt 6.11.3\n丸い画面のためのホーム。"; horizontalAlignment: Text.AlignHCenter; color: "#e6e9ed"; font.pixelSize: 16; lineHeight: 1.5 }
            }
        }
    }
    Component { id:notificationsPage;NotificationCards { notificationModel:root.notificationModel;bridge:root.bridge;onBack:root.openPage("clock") } }
    Component { id:calendarPage;CalendarPage { bridge:root.bridge;agendaModel:root.agendaModel;selected:root.selectedDate;onSelectedDay:day=>root.selectedDate=day;onBack:root.openPage("clock") } }
    Component { id:usbPage;UsbPage { bridge:root.bridge;onBack:root.goBack() } }
    Component { id:stepsPage;StepsPage { bridge:root.bridge;onBack:root.openPage("apps") } }
    Component { id:terminalPage;TerminalPage { bridge:root.bridge;command:root.terminalCommand;onBack:root.goBack() } }
    Component { id:systemPage;SystemPage { bridge:root.bridge;onBack:root.goBack();onTerminal:command=>{root.terminalCommand=command;root.openPage("terminal")} } }
    Text { x:65;y:342;width:254;text:root.bridge?root.bridge.error:"";visible:text!=="";color:"#ffb98d";font.pixelSize:10;elide:Text.ElideRight;horizontalAlignment:Text.AlignHCenter }

}
