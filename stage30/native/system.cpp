#include "system.hpp"
#include <QGuiApplication>
#include <QQuickWindow>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QJsonDocument>
#include <QLocalSocket>
#include <QNetworkInterface>
#include <QStorageInfo>
#include <QSysInfo>
#include <QImage>
#include <QQmlEngine>
#include <QQmlContext>
#include <QRegularExpression>
#include <memory>
#include <QMouseEvent>
#include <sys/utsname.h>
#include <cstdio>

static const QString service="com.meego.usb_moded",object="/com/meego/usb_moded";
static void usbCall(QObject*owner,const QString&method,const QVariantList&args,const std::function<void(QDBusMessage)>&done){
    auto message=QDBusMessage::createMethodCall(service,object,service,method);message.setArguments(args);
    auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,4000),owner);
    QObject::connect(watch,&QDBusPendingCallWatcher::finished,owner,[watch,done](){done(watch->reply());watch->deleteLater();});
}
AuroraSystem::AuroraSystem(QObject*parent):QObject(parent),m_state(QDir::homePath()+"/.local/share/aurora-ui/state30.json") {
    m_error=m_state.problem;
    m_test=QGuiApplication::platformName()=="offscreen";
    m_native=qApp->metaObject()->indexOfSignal("homeReady()")>=0;
    if(m_native)connect(qApp,SIGNAL(homeReady()),this,SLOT(frameReady()));
    m_flush.setSingleShot(true);m_flush.setInterval(15000);
    connect(&m_flush,&QTimer::timeout,this,[this](){try{m_state.save();}catch(const std::exception&e){m_error=e.what();emit errorChanged();}});
    connect(&m_step,&QSensor::readingChanged,this,[this](){if(!m_step.reading())return;m_steps=m_state.ingestStep(m_step.reading()->steps(),readText("/proc/sys/kernel/random/boot_id").trimmed(),QDate::currentDate());m_stepValid=true;if(!m_flush.isActive())m_flush.start();emit stepsChanged();});
    if(!m_test){m_step.setAlwaysOn(true);m_stepAvailable=m_step.start();refreshUsb();}
    connect(&m_confirm,&QTimer::timeout,this,[this](){if(m_framed&&m_scene)helper("ready\n",[this](bool ok,QByteArray){if(ok)m_confirm.stop();});});
    m_confirm.setInterval(2000);
}
AuroraSystem::~AuroraSystem(){try{if(m_stepValid)m_state.save();}catch(...){}}
QString AuroraSystem::readText(const QString&path)const{QFile f(path);if(!f.open(QIODevice::ReadOnly))return "読めません: "+f.errorString();return QString::fromUtf8(f.read(262144));}
QString AuroraSystem::kernel()const{return QSysInfo::kernelType()+" "+QSysInfo::kernelVersion()+" / "+QSysInfo::currentCpuArchitecture();}
QString AuroraSystem::usbAddress()const {QStringList out;for(const auto&i:QNetworkInterface::allInterfaces())if(i.name().contains("usb")||i.name().contains("rndis"))for(const auto&a:i.addressEntries())if(a.ip().protocol()==QAbstractSocket::IPv4Protocol)out<<i.name()+"  "+a.ip().toString();return out.isEmpty()?"USBネットワークのIP未取得":out.join("\n");}
void AuroraSystem::helper(const QByteArray&request,const std::function<void(bool,QByteArray)>&done){
    auto*s=new QLocalSocket(this);auto buffer=std::make_shared<QByteArray>();auto finished=std::make_shared<bool>(false);
    auto finish=[s,done,buffer,finished](bool ok){if(*finished)return;*finished=true;done(ok,*buffer);s->deleteLater();};
    connect(s,&QLocalSocket::connected,s,[s,request](){s->write(request);s->flush();});
    connect(s,&QLocalSocket::readyRead,s,[s,buffer,finish](){buffer->append(s->readAll());if(buffer->size()>300000){s->abort();finish(false);}});
    connect(s,&QLocalSocket::disconnected,s,[buffer,finish](){finish(buffer->startsWith("OK\n"));});
    connect(s,&QLocalSocket::errorOccurred,s,[finish](QLocalSocket::LocalSocketError e){if(e!=QLocalSocket::PeerClosedError)finish(false);});
    QTimer::singleShot(6000,s,[s,finish](){s->abort();finish(false);});s->connectToServer("/run/aurora/control.sock");
}
void AuroraSystem::runCommand(const QString&name){
    if(name=="dmesg") {m_output="カーネルログを読み取り中…";emit outputChanged();helper("kernel\n",[this](bool ok,QByteArray b){m_output=ok?QString::fromUtf8(b.mid(3)):"dmesg: "+(b.isEmpty()?QString("ログヘルパーに接続できません。ホーム導入後に利用できます。"):QString::fromUtf8(b));emit outputChanged();});return;}
    if(name=="uname"){struct utsname u{};::uname(&u);m_output=QString("%1 %2 %3 %4 %5\nuserspace: %6-bit\nQt: %7").arg(u.sysname,u.nodename,u.release,u.version,u.machine).arg(bits()).arg(qVersion());}
    else if(name=="uptime")m_output=readText("/proc/uptime")+"\nload average: "+readText("/proc/loadavg");
    else if(name=="memory")m_output=readText("/proc/meminfo");
    else if(name=="network"){QStringList lines;for(const auto&i:QNetworkInterface::allInterfaces())for(const auto&a:i.addressEntries())lines<<i.name()+"  "+a.ip().toString();m_output=lines.join("\n");}
    else if(name=="df"){QStringList lines{"Filesystem  Size  Available  Mount"};for(const auto&s:QStorageInfo::mountedVolumes())if(s.isValid())lines<<QString("%1  %2 MiB  %3 MiB  %4").arg(QString::fromUtf8(s.device())).arg(s.bytesTotal()/1048576).arg(s.bytesAvailable()/1048576).arg(s.rootPath());m_output=lines.join("\n");}
    else m_output="選択できるコマンドではありません";emit outputChanged();
}
void AuroraSystem::refreshUsb(){
    if(m_test)return;
    usbCall(this,"get_config",{},[this](QDBusMessage r){if(r.type()!=QDBusMessage::ErrorMessage&&!r.arguments().isEmpty()){m_usbDefault=r.arguments().first().toString();emit usbChanged();}});
    usbCall(this,"get_modes",{},[this](QDBusMessage r){if(r.type()==QDBusMessage::ErrorMessage){m_error=r.errorMessage();emit errorChanged();return;}if(!r.arguments().isEmpty()){auto all=r.arguments().first().toString().split(QRegularExpression("[,\\s]+"),Qt::SkipEmptyParts);m_usbModes.clear();for(const auto&mode:QStringList{"adb_mode","developer_mode","charging_only"})if(all.contains(mode)||mode=="charging_only")m_usbModes<<mode;emit usbChanged();}});
    auto msg=QDBusMessage::createMethodCall(service,object,"org.freedesktop.DBus.Introspectable","Introspect");
    auto*w=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg,4000),this);
    connect(w,&QDBusPendingCallWatcher::finished,this,[this,w](){auto r=w->reply();w->deleteLater();if(r.arguments().isEmpty())return;auto xml=r.arguments().first().toString();for(const auto&name:QStringList{"mode_request","get_mode","get_current_mode","get_current_state"})if(xml.contains("name=\""+name+"\"")){m_currentMethod=name;usbCall(this,name,{},[this](QDBusMessage state){if(state.type()!=QDBusMessage::ErrorMessage&&!state.arguments().isEmpty()){m_usbMode=state.arguments().first().toString();emit usbChanged();}});break;}});
}
void AuroraSystem::switchUsb(const QString&mode){
    if(m_test||!m_native){m_error="USBの切替はホーム導入後に利用できます";emit errorChanged();return;}
    if(m_usbBusy||!m_usbModes.contains(mode)){m_error="このモードは利用できません";emit errorChanged();return;}
    m_usbBusy=true;emit usbChanged();
    if(mode=="developer_mode")helper("ssh\n",[this,mode](bool ok,QByteArray b){if(ok)setUsbNow(mode);else{m_usbBusy=false;m_error="SSHの準備に失敗: "+QString::fromUtf8(b);emit usbChanged();emit errorChanged();}});else setUsbNow(mode);
}
void AuroraSystem::setUsbNow(const QString&mode){usbCall(this,"set_mode",{mode},[this,mode](QDBusMessage r){m_usbBusy=false;if(r.type()==QDBusMessage::ErrorMessage){m_error=r.errorMessage();emit errorChanged();}else m_usbMode=r.arguments().isEmpty()?mode:r.arguments().first().toString();emit usbChanged();QTimer::singleShot(1800,this,&AuroraSystem::refreshUsb);});}
void AuroraSystem::selectDay(const QString&day){auto date=QDate::fromString(day,Qt::ISODate);if(date.isValid()){m_selected=date;emit eventsChanged();}}
void AuroraSystem::addEvent(const QString&t,const QString&iso){try{m_state.addEvent(t,QDateTime::fromString(iso,Qt::ISODate));emit eventsChanged();}catch(const std::exception&e){m_error=e.what();emit errorChanged();}}
void AuroraSystem::removeEvent(const QString&id){try{m_state.removeEvent(id);emit eventsChanged();}catch(const std::exception&e){m_error=e.what();emit errorChanged();}}
void AuroraSystem::dismissNotification(uint id){auto m=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","CloseNotification");m.setArguments({id});QDBusConnection::sessionBus().asyncCall(m);}
void AuroraSystem::frameReady(){m_framed=true;if(m_scene&&!m_test)m_confirm.start();}
void AuroraSystem::sceneReady(QQuickItem*scene){m_scene=true;m_capture=scene;if(m_framed&&!m_test)m_confirm.start();m_captureDir=QString::fromLocal8Bit(qgetenv("AURORA_CAPTURE_DIR"));if(m_test&&!m_captureDir.isEmpty()){QDir().mkpath(m_captureDir);QTimer::singleShot(600,this,&AuroraSystem::captureNext);}}
void AuroraSystem::captureNext(){
    static const QStringList pages{"clock","apps","control","settings","notifications","calendar","usb","steps","terminal","system","stopwatch","timer","calculator","style","about"};
    if(!m_capture||!m_capture->window()){qApp->exit(31);return;}
    if(m_pageIndex==pages.size()){finishCapture();return;}
    auto*win=m_capture->window();win->resize(384,384);win->show();m_capture->setProperty("motion",false);m_capture->setProperty("previewTime",true);
    if(m_native && pages[m_pageIndex]=="notifications") {
        auto*context=QQmlEngine::contextForObject(m_capture);
        auto*presenter=context?context->contextProperty("notificationPreviewPresenter").value<QObject*>():nullptr;
        if(presenter)QMetaObject::invokeMethod(presenter,"showNextNotification");
    }
    m_capture->setProperty("page",pages[m_pageIndex]);win->requestUpdate();
    QTimer::singleShot(450,this,[this,win](){auto image=win->grabWindow();static const QStringList names{"clock","apps","control","settings","notifications","calendar","usb","steps","terminal","system","stopwatch","timer","calculator","style","about"};
        if(image.size()!=QSize(384,384)||!image.save(m_captureDir+"/"+names[m_pageIndex]+".png")){qApp->exit(32);return;}
        int light=0;for(int y=60;y<320;++y)for(int x=70;x<314;++x)if(qGray(image.pixel(x,y))>35)++light;
        if(light<150){qApp->exit(33);return;}++m_pageIndex;captureNext();});
}

void AuroraSystem::finishCapture(){
    auto show=[this](const QString&p){return QMetaObject::invokeMethod(m_capture,"openPage",Q_ARG(QVariant,QVariant(p)));};
    if(!show("apps")){qApp->exit(34);return;}
    QTimer::singleShot(60,this,[this](){
        auto*w=m_capture->window();
        auto mouse=[w](QEvent::Type type,int x,int y,Qt::MouseButton button,Qt::MouseButtons buttons){QMouseEvent e(type,QPointF(x,y),QPointF(x,y),button,buttons,Qt::NoModifier);QCoreApplication::sendEvent(w,&e);QCoreApplication::processEvents();};
        mouse(QEvent::MouseButtonPress,192,192,Qt::LeftButton,Qt::LeftButton);mouse(QEvent::MouseMove,250,230,Qt::NoButton,Qt::LeftButton);mouse(QEvent::MouseButtonRelease,250,230,Qt::LeftButton,Qt::NoButton);
        auto*hex=m_capture->findChild<QObject*>("honeycomb");if(!hex||qAbs(hex->property("panX").toDouble())<20){qApp->exit(35);return;}
        mouse(QEvent::MouseButtonPress,192,38,Qt::LeftButton,Qt::LeftButton);mouse(QEvent::MouseButtonRelease,192,38,Qt::LeftButton,Qt::NoButton);
        QTimer::singleShot(60,this,[this](){
            if(m_capture->property("page").toString()!="clock"){qApp->exit(36);return;}
            QMetaObject::invokeMethod(m_capture,"openPage",Q_ARG(QVariant,QVariant("apps")));
            QTimer::singleShot(60,this,[this](){
                auto*hex=m_capture->findChild<QObject*>("honeycomb");
                if(!hex||qAbs(hex->property("panX").toDouble())>0.01||qAbs(hex->property("panY").toDouble())>0.01){qApp->exit(37);return;}
                QObject*model=m_capture->property("notificationModel").value<QObject*>();
                const int notificationCount=model?model->property("itemCount").toInt():0;
                QJsonObject report{{"notifications",notificationCount},{"status","PASS"},{"native_compositor",m_native},{"first_frame_signal",m_framed},{"pages",15},{"gesture_checks",3},{"honeycomb_resets_after_home",true}};
                QFile out(m_captureDir+"/capture-result.json");if(!out.open(QIODevice::WriteOnly)){qApp->exit(38);return;}out.write(QJsonDocument(report).toJson());out.close();
                qApp->exit(0);
            });
        });
    });
}
