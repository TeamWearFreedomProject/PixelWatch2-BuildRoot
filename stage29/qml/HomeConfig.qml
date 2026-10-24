import QtQml
import Nemo.Configuration

QtObject {
    property QtObject face: ConfigurationValue { key:"/desktop/asteroid/watchface";defaultValue:"file:///usr/share/asteroid-launcher/watchfaces/000-default-digital.qml" }
    property QtObject apps: ConfigurationValue { key:"/desktop/asteroid/applauncher";defaultValue:"file:///usr/share/asteroid-launcher/applauncher/000-default-horizontal.qml" }
    property QtObject faceReady: ConfigurationValue { key:"/org/aurora-ui/home-ready";defaultValue:"" }
    property QtObject appsReady: ConfigurationValue { key:"/org/aurora-ui/apps-ready";defaultValue:"" }
}
