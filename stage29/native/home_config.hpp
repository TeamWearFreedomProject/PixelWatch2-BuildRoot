#pragma once
#include "home_state.hpp"
#include <QCoreApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QSaveFile>
#include <QJsonDocument>
#include <QUrl>
#include <QEventLoop>
#include <QTimer>
#include <memory>

inline QJsonObject configureHome(const QString &action) {
    using namespace AuroraHome;
    if(action=="activate")AuroraSession::require(AuroraSession::read("/etc/os-release").contains("BUILD_ID=\"20261005064926\""),"Activation requires the verified V1 build 20261005064926");
    const QString directory=QCoreApplication::applicationDirPath()+"/qml/";
    const Pair wanted{QUrl::fromLocalFile(directory+"NativeHome.qml").toString(),
                      QUrl::fromLocalFile(directory+"NativeApps.qml").toString()};
    for(const auto &name:{"NativeHome.qml","NativeApps.qml","HomeConfig.qml"})
        AuroraSession::require(QFileInfo(directory+name).isFile(),"Incomplete Aurora home bundle");
    QQmlEngine engine;
    engine.addImportPath("/usr/lib/qml");
    QQmlComponent component(&engine,QUrl::fromLocalFile(directory+"HomeConfig.qml"));
    std::unique_ptr<QObject> config(component.create());
    AuroraSession::require(config!=nullptr,"Cannot read Nemo home configuration: "+component.errorString());
    QObject *face=config->property("face").value<QObject*>();
    QObject *apps=config->property("apps").value<QObject*>();
    AuroraSession::require(face && apps,"Missing home configuration properties");
    auto read=[&]() {return Pair{face->property("value").toString(),apps->property("value").toString()};};
    const Pair current=read();
    const QString stateDir=QString::fromLocal8Bit(qgetenv("HOME"))+"/.local/share/aurora-ui";
    const QString backupPath=stateDir+"/home-backup.json";
    QJsonObject saved;
    const QFileInfo info(backupPath);
    if(info.exists() || info.isSymLink()) {
        AuroraSession::require(!info.isSymLink() && info.isFile() && info.ownerId()==unsigned(geteuid()),"Unsafe home backup file");
        QJsonParseError error;
        const auto doc=QJsonDocument::fromJson(AuroraSession::read(backupPath),&error);
        AuroraSession::require(error.error==QJsonParseError::NoError && doc.isObject(),"Invalid home backup JSON");saved=doc.object();
    }
    if(action=="status")return {{"status","PASS"},{"action",action},{"current",current.json()},
        {"this_bundle_active",current==wanted},{"backup_exists",!saved.isEmpty()},{"watch_modified",false}};
    const Plan update=plan(action,current,wanted,saved);
    if(action=="activate" && current==wanted && !saved.isEmpty())
        return {{"status","PASS"},{"action",action},{"already_active",true},{"watch_modified",false}};
    AuroraSession::require(QDir().mkpath(stateDir),"Cannot create home backup directory");
    auto writeBackup=[&](const QJsonObject &data) {
        QSaveFile out(backupPath);
        AuroraSession::require(out.open(QIODevice::WriteOnly),"Cannot write home backup");
        out.setPermissions(QFile::ReadOwner|QFile::WriteOwner);
        const auto bytes=QJsonDocument(data).toJson();
        AuroraSession::require(out.write(bytes)==bytes.size() && out.commit(),"Cannot commit home backup");
    };
    // Save the original pair before the compositor observes either new URL.
    if(action=="activate")writeBackup(update.backup);
    auto set=[&](bool isFace,const QString &value) {
        AuroraSession::require((isFace?face:apps)->setProperty("value",value),"Home configuration is not writable");
    };
    QObject *faceReady=config->property("faceReady").value<QObject*>();
    QObject *appsReady=config->property("appsReady").value<QObject*>();
    AuroraSession::require(faceReady && appsReady,"Missing home readiness properties");
    if(action=="activate") {faceReady->setProperty("value",QString());appsReady->setProperty("value",QString());}
    try {apply(current,update.desired,set,read);} catch(...) {
        if(action=="activate") {if(saved.isEmpty())QFile::remove(backupPath);else writeBackup(saved);}
        throw;
    }
    // Nemo.Configuration writes asynchronously through the GUI user's session
    // bus. Keep the event loop alive before checking and closing this CLI.
    QEventLoop loop;
    bool ready=action!="activate";
    QTimer poll;
    if(action=="activate") {
        QObject::connect(&poll,&QTimer::timeout,&loop,[&](){
            ready=faceReady->property("value").toString()==wanted.face && appsReady->property("value").toString()==wanted.apps;
            if(ready)loop.quit();
        });
        poll.start(100);
    }
    QTimer::singleShot(action=="activate"?12000:1800,&loop,&QEventLoop::quit);loop.exec();poll.stop();
    if(!ready) {
        apply(update.desired,current,set,read);
        QEventLoop undo;QTimer::singleShot(1800,&undo,&QEventLoop::quit);undo.exec();
        if(saved.isEmpty())QFile::remove(backupPath);else writeBackup(saved);
        throw std::runtime_error("Home components did not report ready within 12s; previous home settings restored");
    }
    AuroraSession::require(read()==update.desired,"Home values changed while applying configuration");
    if(update.removeBackup)AuroraSession::require(QFile::remove(backupPath),"Restored home, but could not remove backup");
    return {{"status","PASS"},{"action",action},{"current",read().json()},
             {"watch_modified",true},{"kernel_or_services_replaced",false}};
}
