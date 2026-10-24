#include "home_state.hpp"
#include <cstdio>

int main() {
    using namespace AuroraHome;
    const Pair stock{"stock-face","stock-apps"},first{"aurora1-face","aurora1-apps"},second{"aurora2-face","aurora2-apps"};
    auto a=plan("activate",stock,first,{});
    AuroraSession::require(Pair::from(a.backup["original"].toObject())==stock,"Original pair lost");
    auto b=plan("activate",first,second,a.backup);
    AuroraSession::require(Pair::from(b.backup["original"].toObject())==stock,"Upgrade lost original pair");
    auto c=plan("restore",second,{},b.backup);
    AuroraSession::require(c.desired==stock && c.removeBackup,"Restore did not select original pair");
    auto interrupted=plan("restore",stock,{},a.backup);
    AuroraSession::require(interrupted.desired==stock && interrupted.removeBackup,"Interrupted activation backup cannot be cleaned up");
    bool conflict=false;
    try {plan("restore",{"user-face","user-apps"},{},b.backup);}catch(...){conflict=true;}
    AuroraSession::require(conflict,"Concurrent user changes were overwritten");
    bool missing=false;try{plan("restore",stock,{},{});}catch(...){missing=true;}
    AuroraSession::require(missing,"Missing backup was accepted");
    Pair store=stock;bool fail=true,refused=false;
    auto setter=[&](bool face,const QString &value){if(!face && value==first.apps && fail){fail=false;throw std::runtime_error("injected second-write failure");}if(face)store.face=value;else store.apps=value;};
    try{apply(stock,first,setter,[&](){return store;});}catch(...){refused=true;}
    AuroraSession::require(refused && store==stock,"Partial write was not rolled back");
    std::puts("7 home activation/upgrade/restore/conflict/rollback checks passed; no real settings changed");
}
