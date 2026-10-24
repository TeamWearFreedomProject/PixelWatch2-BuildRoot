#include "session.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QTemporaryDir>
#include <sys/socket.h>
#include <sys/un.h>
#include <cstdio>
#include <cstring>
#include <functional>

using namespace AuroraSession;
static void save(const QString &name, const QByteArray &data) {
    QFile file(name); require(file.open(QIODevice::WriteOnly), "fixture write failed"); file.write(data);
}
struct Fixture {
    QTemporaryDir temp;
    QString proc = temp.path() + "/proc", runtime = temp.path() + "/run";
    unsigned uid = ::getuid() ? ::getuid() : 65534, gid = ::getgid() ? ::getgid() : 65534;
    int fd = -1;
    Fixture() {
        require(temp.isValid(), "fixture directory failed");
        QDir().mkpath(proc); QDir().mkpath(runtime);
        const QByteArray socketName = QFile::encodeName(runtime + "/wayland-0");
        fd = ::socket(AF_UNIX, SOCK_STREAM, 0); require(fd >= 0, "fixture socket failed");
        sockaddr_un address{}; address.sun_family = AF_UNIX;
        require(socketName.size() < int(sizeof(address.sun_path)), "fixture socket path too long");
        std::memcpy(address.sun_path, socketName.constData(), socketName.size() + 1);
        require(::bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0, "fixture bind failed");
        if (::geteuid() == 0) {
            require(::chown(QFile::encodeName(runtime).constData(), uid, gid) == 0, "fixture ownership failed");
            require(::chown(socketName.constData(), uid, gid) == 0, "fixture socket ownership failed");
        }
        process("100", 1);
    }
    ~Fixture() { if (fd >= 0) ::close(fd); }
    void process(const QString &pid, unsigned parent) {
        const QString base = proc + "/" + pid; QDir().mkpath(base);
        require(::symlink(QFile::encodeName(booster).constData(), QFile::encodeName(base + "/exe").constData()) == 0,
                "fixture exe link failed");
        save(base + "/cmdline", booster.toUtf8() + '\0' + "--systemd" + '\0');
        save(base + "/status", QString("PPid:\t%1\nUid:\t%2 %2 %2 %2\nGid:\t%3 %3 %3 %3\n")
                                  .arg(parent).arg(uid).arg(gid).toLatin1());
        environment(pid);
    }
    void environment(const QString &pid, const QByteArray &display = "wayland-0", const QString &runtimeOverride = {}) {
        QByteArray data = "XDG_RUNTIME_DIR=" + QFile::encodeName(runtimeOverride.isEmpty() ? runtime : runtimeOverride) + '\0';
        if (!display.isEmpty()) data += "WAYLAND_DISPLAY=" + display + '\0';
        data += QByteArray("QT_QPA_PLATFORM=eglfs") + '\0' + "API_TOKEN=do-not-leak" + '\0';
        save(proc + "/" + pid + "/environ", data);
    }
};
static void refuses(const std::function<void()> &action) {
    bool rejected = false; try { action(); } catch (const std::exception &) { rejected = true; }
    require(rejected, "invalid session accepted");
}
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    try {
        { Fixture f; auto s = inspect(f.proc); require(s.uid == f.uid, "owner mismatch");
          require(s.environment.value("QT_QPA_PLATFORM") == "wayland", "compositor platform inherited");
          require(!QJsonDocument(s.json()).toJson().contains("do-not-leak"), "unlisted environment leaked"); }
        { Fixture f; f.environment("100", {}); require(inspect(f.proc).socket.endsWith("wayland-0"), "socket discovery failed"); }
        { Fixture f; f.process("101", 100); require(inspect(f.proc).pid == "100", "booster child confused with service"); }
        { Fixture f; f.process("101", 1); refuses([&] { inspect(f.proc); }); }
        { Fixture f; f.environment("100", "missing-socket"); refuses([&] { inspect(f.proc); }); }
        { Fixture f; f.environment("100", "wayland-0", "/tmp"); refuses([&] { inspect(f.proc); }); }
        { Fixture f; save(f.proc + "/100/status", "PPid: 1\nUid: 0 0 0 0\nGid: 0 0 0 0\n"); refuses([&] { inspect(f.proc); }); }
        std::puts("7 live-session discovery/refusal checks passed; no user identity was changed");
        return 0;
    } catch (const std::exception &error) { std::fprintf(stderr, "%s\n", error.what()); return 1; }
}
