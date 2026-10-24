import QtQuick
import Nemo.Configuration
import Nemo.Mce
import Connman
import org.asteroid.settings
import org.asteroid.utils

Item {
    id: root
    visible: false
    property bool writable: typeof captureMode === "undefined" || !captureMode
    readonly property bool wifiOn: wifi.powered
    readonly property bool wifiConnected: wifi.connected
    readonly property bool bluetoothOn: bt.powered
    readonly property int battery: level.valid?level.percent:-1
    readonly property int brightness: display.brightness
    readonly property bool autoBrightness: display.ambientLightSensorEnabled
    readonly property bool alwaysOn: aod.value
    property alias accent: accentConfig.value
    property alias motion: motionConfig.value
    property string message: ""
    NetworkTechnology { id:wifi; path:"/net/connman/technology/wifi" }
    BluetoothStatus { id:bt }
    MceBatteryLevel { id:level }
    MceChargerType { id:charger }
    DisplaySettings { id:display }
    ConfigurationValue { id:aod; key:"/org/asteroidos/settings/always-on-display"; defaultValue:true }
    ConfigurationValue { id:nightstand; key:"/desktop/asteroid/nightstand/enabled"; defaultValue:true }
    ConfigurationValue { id:accentConfig; key:"/org/aurora-ui/accent"; defaultValue:"#9cf45a" }
    ConfigurationValue { id:motionConfig; key:"/org/aurora-ui/motion"; defaultValue:true }
    Timer { id:verify; interval:2500; property string kind; property bool wanted
        onTriggered: {
            var actual=kind==="wifi" ? root.wifiOn : root.bluetoothOn
            root.message=actual===wanted ? "変更しました" : "反映されませんでした。標準設定も確認してね"
        }
    }
    function toggleWifi() { if(!writable)return; verify.kind="wifi";verify.wanted=!wifi.powered;wifi.powered=verify.wanted;message="変更中…";verify.restart() }
    function toggleBluetooth() { if(!writable)return;verify.kind="bluetooth";verify.wanted=!bt.powered;bt.powered=verify.wanted;message="変更中…";verify.restart() }
    function setBrightness(value) { if(writable) display.brightness=Math.max(10,Math.min(100,Math.round(value/10)*10)) }
    function toggleAutoBrightness() { if(writable)display.ambientLightSensorEnabled=!display.ambientLightSensorEnabled }
    function toggleAlwaysOn() {
        if(!writable)return
        aod.value=!aod.value
        if(!nightstand.value || charger.type===MceChargerType.None) display.lowPowerModeEnabled=aod.value
    }
}
