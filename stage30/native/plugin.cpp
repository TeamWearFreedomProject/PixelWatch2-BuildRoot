#include "system.hpp"
#include <QQmlExtensionPlugin>
#include <qqml.h>
class AuroraPlugin:public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:void registerTypes(const char*uri)override{qmlRegisterType<AuroraSystem>(uri,1,0,"System");}
};
#include "plugin.moc"
