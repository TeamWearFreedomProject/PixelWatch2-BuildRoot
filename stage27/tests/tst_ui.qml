import QtQuick 2.12
import QtTest 1.2
import "../qml" as UI

Item {
    width: 384; height: 384
    UI.AuroraShell { id: shell; anchors.fill: parent }
    TestCase {
        name: "AuroraUI"
        when: windowShown
        function init() {
            shell.motion = false; shell.openPage("clock")
            shell.stopwatchReset(); shell.cancelTimer(); shell.calculate("C")
            wait(30)
        }
        function test_navigation() {
            var button = findChild(shell, "appsButton")
            verify(button !== null)
            mouseClick(button)
            compare(shell.page, "apps")
            compare(shell.appCount, 7)
            var ids = ["stopwatch","timer","calculator","light","style","about","clock"]
            for (var i=0;i<ids.length;i++) {
                var app = findChild(shell, "app_" + ids[i])
                verify(app !== null, ids[i])
                mouseClick(app)
                compare(shell.page, ids[i])
                if (ids[i] !== "clock") mouseClick(findChild(shell, "backButton"))
                else shell.openPage("apps")
                compare(shell.page, "apps")
            }
        }
        function test_stopwatch_pause_and_navigation() {
            shell.openPage("stopwatch")
            mouseClick(findChild(shell, "stopwatchToggle"))
            wait(120)
            verify(shell.stopwatchElapsed > 0)
            shell.openPage("apps")
            wait(120)
            shell.openPage("stopwatch")
            mouseClick(findChild(shell, "stopwatchToggle"))
            verify(shell.stopwatchElapsed >= 200)
            var frozen = shell.stopwatchElapsed
            wait(100)
            compare(shell.stopwatchElapsed, frozen)
            mouseClick(findChild(shell, "stopwatchReset"))
            compare(shell.stopwatchElapsed, 0)
        }
        function test_timer_expires_visually() {
            shell.openPage("timer")
            shell.startTimer(1)
            tryCompare(shell, "timerFinished", true, 2200)
            compare(shell.timerRunning, false)
            compare(shell.timerRemaining, 0)
        }
        function test_calculator_decimal_and_division_by_zero() {
            var keys = ["0",".","1","+","0",".","2","="]
            for (var i=0;i<keys.length;i++) shell.calculate(keys[i])
            compare(shell.calculation, "0.3")
            shell.calculate("÷"); shell.calculate("0"); shell.calculate("=")
            compare(shell.calculation, "Error")
            shell.calculate("4")
            compare(shell.calculation, "4")
        }
        function test_motion_toggle() {
            shell.openPage("style")
            mouseClick(findChild(shell, "motionButton"))
            compare(shell.motion, true)
        }
        function test_standalone_window() {
            var component = Qt.createComponent("../qml/Main.qml")
            compare(component.status, Component.Ready, component.errorString())
            var window = component.createObject(null, {visible: false})
            verify(window !== null)
            compare(window.width, 384)
            compare(window.height, 384)
            window.destroy()
        }
        function test_zz_screenshots() {
            shell.previewTime = true
            var pages = ["clock", "apps", "stopwatch", "style", "timer", "calculator"]
            for (var i=0;i<pages.length;i++) {
                shell.openPage(pages[i]); wait(100)
                var shot = grabImage(shell)
                compare(shot.width, 384)
                compare(shot.height, 384)
                shot.save("stage27-artifacts/" + pages[i] + ".png")
            }
        }
    }
}
