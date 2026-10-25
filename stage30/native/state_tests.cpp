#include "state.hpp"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <cstdio>
static void check(bool ok){if(!ok)throw std::runtime_error("State assertion failed");}
int main(int argc,char**argv){QCoreApplication app(argc,argv);QTemporaryDir temp;QString p=temp.path()+"/state.json";AuroraState s(p);auto date=QDate(2026,10,25);
    check(s.ingestStep(500,"boot1",date)==0);
    check(s.ingestStep(511,"boot1",date)==11);
    s.save();AuroraState reload(p);check(reload.ingestStep(520,"boot1",date)==20);
    check(reload.ingestStep(5,"boot1",date)==25);
    check(reload.ingestStep(100,"boot2",date)==25);
    check(reload.ingestStep(110,"boot2",date)==35);
    check(reload.ingestStep(111,"boot2",date.addDays(1))==0);
    auto id=reload.addEvent(" 勉強 ",QDateTime(date,QTime(9,30)));check(reload.eventsFor(date).size()==1);check(reload.eventsFor(date.addDays(1)).isEmpty());
    reload.removeEvent(id);check(reload.eventsFor(date).isEmpty());
    bool refused=false;try{reload.addEvent("   ",QDateTime());}catch(...){refused=true;}check(refused);
    QFile broken(temp.path()+"/broken.json");check(broken.open(QIODevice::WriteOnly));broken.write("not JSON");broken.close();AuroraState bad(broken.fileName());check(!bad.problem.isEmpty());
    refused=false;try{bad.save();}catch(...){refused=true;}check(refused);check(broken.open(QIODevice::ReadOnly));check(broken.readAll()=="not JSON");
    std::puts("12 event persistence/step baseline/restart/reset/rollover/corruption checks passed");
}
