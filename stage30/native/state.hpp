#pragma once
#include <QDate>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <algorithm>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QUuid>
#include <stdexcept>

struct AuroraState {
    QString path;
    QJsonObject data;
    QString problem;
    explicit AuroraState(QString file):path(std::move(file)) {
        QFile in(path);
        if(in.exists()) {
            if(!in.open(QIODevice::ReadOnly)||in.size()>1024*1024){problem="Cannot read Aurora state; original file preserved";return;}
            QJsonParseError err;auto doc=QJsonDocument::fromJson(in.readAll(),&err);
            if(err.error!=QJsonParseError::NoError||!doc.isObject()){problem="Invalid Aurora state; original file preserved";return;}
            data=doc.object();
        }
    }
    void save() const {
        if(!problem.isEmpty())throw std::runtime_error(problem.toStdString());
        QDir().mkpath(QFileInfo(path).absolutePath());QSaveFile out(path);
        if(!out.open(QIODevice::WriteOnly))throw std::runtime_error("Cannot save Aurora state");
        out.setPermissions(QFile::ReadOwner|QFile::WriteOwner);
        auto bytes=QJsonDocument(data).toJson();
        if(out.write(bytes)!=bytes.size()||!out.commit())throw std::runtime_error("Cannot commit Aurora state");
    }
    QString addEvent(const QString &title,const QDateTime &when) {
        const QString clean=title.trimmed().left(100);
        if(clean.isEmpty()||!when.isValid())throw std::runtime_error("Enter a title and valid time");
        auto events=data["events"].toArray();if(events.size()>=500)throw std::runtime_error("Schedule limit reached");
        const QString id=QUuid::createUuid().toString(QUuid::WithoutBraces);
        events.append(QJsonObject{{"id",id},{"title",clean},{"start",when.toUTC().toString(Qt::ISODate)}});
        data["events"]=events;save();return id;
    }
    void removeEvent(const QString &id) {
        auto events=data["events"].toArray();for(int i=events.size()-1;i>=0;--i)if(events[i].toObject()["id"]==id)events.removeAt(i);
        data["events"]=events;save();
    }
    QVariantList eventsFor(const QDate &day) const {
        QVariantList result;
        for(const auto &v:data["events"].toArray()) {
            auto o=v.toObject();auto time=QDateTime::fromString(o["start"].toString(),Qt::ISODate).toLocalTime();
            if(time.date()==day)result.append(QVariantMap{{"id",o["id"].toString()},{"title",o["title"].toString()},{"time",time.toString("HH:mm")}});
        }
        std::sort(result.begin(),result.end(),[](const QVariant&a,const QVariant&b){return a.toMap()["time"].toString()<b.toMap()["time"].toString();});return result;
    }
    qint64 ingestStep(qint64 raw,const QString &boot,const QDate &today) {
        if(raw<0)return data["steps"].toObject()["total"].toInteger();
        auto s=data["steps"].toObject();
        bool continuous=s["date"].toString()==today.toString(Qt::ISODate)&&s["boot"].toString()==boot;
        qint64 total=s["date"].toString()==today.toString(Qt::ISODate)?s["total"].toInteger():0;
        if(continuous){qint64 last=s["last"].toInteger();total+=raw>=last?raw-last:raw;}
        data["steps"]=QJsonObject{{"date",today.toString(Qt::ISODate)},{"boot",boot},{"last",raw},{"total",total}};
        return total;
    }
};
