import QtQuick 2.12

Rectangle {
    id: root
    width: 384
    height: 384
    color: "black"
    clip: true
    property string page: "clock"
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
    readonly property int appCount: apps.count

    function openPage(name) { page = name }
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
        interval: 1000; repeat: true; running: root.visible && root.page === "clock"
        onTriggered: root.now = new Date()
    }
    Timer {
        interval: root.page === "stopwatch" ? 40 : 500
        repeat: true; running: root.stopwatchRunning || root.timerRunning
        onTriggered: {
            if (root.stopwatchRunning) root.stopwatchElapsed = root.stopwatchSaved + Date.now() - root.stopwatchStart
            if (root.timerRunning) {
                root.timerRemaining = Math.max(0, Math.ceil((root.timerDeadline - Date.now()) / 1000))
                if (root.timerRemaining === 0) { root.timerRunning = false; root.timerFinished = true }
            }
        }
    }
    ListModel {
        id: apps
        ListElement { app: "clock"; tint: "#247cfa"; px: 192; py: 192 }
        ListElement { app: "stopwatch"; tint: "#ff853c"; px: 192; py: 94 }
        ListElement { app: "timer"; tint: "#7959ed"; px: 277; py: 143 }
        ListElement { app: "calculator"; tint: "#e6b742"; px: 277; py: 241 }
        ListElement { app: "light"; tint: "#dce4ed"; px: 192; py: 290 }
        ListElement { app: "style"; tint: "#df5cac"; px: 107; py: 241 }
        ListElement { app: "about"; tint: "#278d81"; px: 107; py: 143 }
    }
    Item {
        id: face
        width: 384; height: 384
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 384
        Loader {
            id: content
            anchors.fill: parent
            sourceComponent: root.page === "clock" ? clockPage : root.page === "apps" ? appsPage : root.page === "stopwatch" ? stopwatchPage : root.page === "timer" ? timerPage : root.page === "calculator" ? calculatorPage : root.page === "light" ? lightPage : root.page === "style" ? stylePage : aboutPage
            onLoaded: { root.now = new Date(); appearance.restart() }
        }
        ParallelAnimation {
            id: appearance
            NumberAnimation { target: content; property: "opacity"; from: root.motion ? 0 : 1; to: 1; duration: root.motion ? 190 : 0 }
            NumberAnimation { target: content; property: "scale"; from: root.motion ? 0.94 : 1; to: 1; duration: root.motion ? 230 : 0; easing.type: Easing.OutCubic }
        }
        RoundButton {
            objectName: "backButton"
            z: 10
            x: 168; y: 18; width: 48; height: 40
            glyph: "back"; fill: root.page === "light" ? "#d5d8db" : "#17191c"
            ink: root.page === "light" ? "black" : "#c6cbd1"
            visible: root.page !== "clock" && root.page !== "apps"
            motion: root.motion
            onClicked: root.openPage("apps")
        }
    }
    Component {
        id: clockPage
        Item {
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 62; text: "A U R O R A"; color: root.accent; font.pixelSize: 14; font.weight: Font.DemiBold }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 105; text: root.previewTime ? "SAT, 24 OCT" : Qt.formatDate(root.now, "ddd, d MMM").toUpperCase(); color: "#91979e"; font.pixelSize: 18 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 137; text: root.previewTime ? "08:32" : Qt.formatTime(root.now, "hh:mm"); color: "#f7f9fb"; font.pixelSize: 82; font.weight: Font.Bold; font.letterSpacing: -3 }
            Rectangle { x: 156; y: 240; width: 72; height: 5; radius: 3; color: root.accent }
            RoundButton { objectName: "appsButton"; x: 122; y: 281; width: 140; height: 48; text: "アプリ"; glyph: "apps"; fill: "#22262a"; motion: root.motion; onClicked: root.openPage("apps") }
        }
    }
    Component {
        id: appsPage
        Item {
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 30; text: "アプリ"; color: "#bdc3ca"; font.pixelSize: 16 }
            Repeater {
                model: apps
                RoundButton {
                    objectName: "app_" + model.app
                    x: model.px - width/2; y: model.py - height/2; width: 68; height: 68
                    glyph: model.app; fill: model.tint; ink: model.app === "light" ? "#161a20" : "white"
                    motion: root.motion
                    Accessible.name: model.app
                    onClicked: root.openPage(model.app)
                }
            }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 342; text: "タップして開く"; color: "#717a84"; font.pixelSize: 13 }
        }
    }
    Component {
        id: stopwatchPage
        Item {
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 83; text: "ストップウォッチ"; color: "#a3aab2"; font.pixelSize: 18 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 141; text: root.formatDuration(root.stopwatchElapsed, true); color: "white"; font.pixelSize: 48; font.weight: Font.DemiBold; font.family: "monospace" }
            RoundButton { objectName: "stopwatchToggle"; x: 61; y: 234; width: 128; height: 52; text: root.stopwatchRunning ? "停止" : "開始"; fill: root.accent; ink: "#10180b"; motion: root.motion; onClicked: root.stopwatchToggle() }
            RoundButton { objectName: "stopwatchReset"; x: 199; y: 234; width: 124; height: 52; text: "リセット"; motion: root.motion; onClicked: root.stopwatchReset() }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 316; text: "AURORA TOOLS"; color: "#5b646e"; font.pixelSize: 12; font.letterSpacing: 1 }
        }
    }
    Component {
        id: timerPage
        Item {
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
        Item {
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
        Rectangle { color: "#ffffff"; Text { anchors.horizontalCenter: parent.horizontalCenter; y: 290; text: "戻るボタンで終了"; color: "#666b70"; font.pixelSize: 15 } }
    }
    Component {
        id: stylePage
        Item {
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
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 321; text: "このデモを閉じるまで有効"; color: "#78828d"; font.pixelSize: 13 }
        }
    }
    Component {
        id: aboutPage
        Item {
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 92; text: "Aurora UI"; color: root.accent; font.pixelSize: 36; font.weight: Font.Bold }
            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 145; text: "Stage 27 · Preview 1"; color: "#b0b8c0"; font.pixelSize: 16 }
            Rectangle {
                x: 62; y: 198; width: 260; height: 96; radius: 27; color: "#191c20"
                Text { anchors.centerIn: parent; text: "AsteroidOSを土台に\n丸い画面のための、新しいUI。"; horizontalAlignment: Text.AlignHCenter; color: "#e6e9ed"; font.pixelSize: 16; lineHeight: 1.5 }
            }
        }
    }
}
