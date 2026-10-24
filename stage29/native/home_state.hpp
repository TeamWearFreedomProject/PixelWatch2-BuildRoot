#pragma once
#include "../../stage28/native/session.hpp"
#include <QJsonObject>
#include <functional>

namespace AuroraHome {
struct Pair {
    QString face, apps;
    bool operator==(const Pair &other) const { return face==other.face && apps==other.apps; }
    QJsonObject json() const { return {{"face",face},{"apps",apps}}; }
    static Pair from(const QJsonObject &obj) {
        Pair p{obj["face"].toString(),obj["apps"].toString()};
        AuroraSession::require(!p.face.isEmpty() && !p.apps.isEmpty(),"Invalid home backup values");return p;
    }
};
struct Plan { Pair desired; QJsonObject backup; bool removeBackup=false; };
inline Plan plan(const QString &action,const Pair &current,const Pair &wanted,const QJsonObject &saved) {
    if(action=="activate") {
        Pair original=current;
        if(!saved.isEmpty()) {
            AuroraSession::require(saved["schema"].toInt()==1,"Unsupported home backup schema");
            original=Pair::from(saved["original"].toObject());
            AuroraSession::require(current==Pair::from(saved["installed"].toObject()),
                "Home settings changed since activation; refusing to overwrite them");
        }
        return {wanted,{{"schema",1},{"original",original.json()},{"installed",wanted.json()}},false};
    }
    AuroraSession::require(action=="restore" && !saved.isEmpty(),"No Aurora home backup to restore");
    AuroraSession::require(saved["schema"].toInt()==1,"Unsupported home backup schema");
    AuroraSession::require(current==Pair::from(saved["installed"].toObject()),
        "Home settings changed since activation; refusing to overwrite them");
    return {Pair::from(saved["original"].toObject()),saved,true};
}
inline void apply(const Pair &before,const Pair &after,
                  const std::function<void(bool,const QString&)> &set,
                  const std::function<Pair()> &get) {
    try {
        set(true,after.face);set(false,after.apps);
        AuroraSession::require(get()==after,"Home settings did not accept both values");
    } catch(...) {
        set(true,before.face);set(false,before.apps);
        throw;
    }
}
}
