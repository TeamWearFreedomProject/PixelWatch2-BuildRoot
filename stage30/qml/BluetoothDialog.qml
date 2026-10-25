import QtQuick
import org.nemomobile.lipstick
Rectangle {
    id:root;visible:bluetoothAgent.windowVisible;color:"black"
    property string digits:""
    readonly property bool input:bluetoothAgent.state===BluetoothAgent.ReqPinCode||bluetoothAgent.state===BluetoothAgent.ReqPasskey
    Text { x:65;y:75;width:254;text:"Bluetooth ペアリング";color:"white";font.pixelSize:19;horizontalAlignment:Text.AlignHCenter }
    Text { x:65;y:115;width:254;text:root.input?root.digits:(bluetoothAgent.state===BluetoothAgent.DisplayPinCode?bluetoothAgent.pinCode:("000000"+bluetoothAgent.passkey).slice(-6));color:"#9cf45a";font.pixelSize:29;horizontalAlignment:Text.AlignHCenter }
    Grid { x:80;y:162;columns:5;spacing:5;visible:root.input
        Repeater { model:["1","2","3","4","5","6","7","8","9","0"];RoundButton { width:41;height:39;text:modelData;onClicked:if(root.digits.length<(bluetoothAgent.state===BluetoothAgent.ReqPasskey?6:16))root.digits+=modelData } }
    }
    Row { x:65;y:279;spacing:10
        RoundButton { width:122;height:44;text:"キャンセル";onClicked:bluetoothAgent.userCancels() }
        RoundButton { width:122;height:44;text:"確認";fill:"#9cf45a";ink:"#11200b";onClicked:{if(root.input&&root.digits.length===0)return;if(bluetoothAgent.state===BluetoothAgent.ReqPinCode)bluetoothAgent.pinCode=root.digits;else if(bluetoothAgent.state===BluetoothAgent.ReqPasskey)bluetoothAgent.passkey=Number(root.digits);bluetoothAgent.userAccepts()} }
    }
    Connections { target:bluetoothAgent;function onStateChanged(){root.digits=""} }
}
