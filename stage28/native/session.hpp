#pragma once
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonObject>
#include <QMap>
#include <QProcessEnvironment>
#include <QRegularExpression>
#include <QSet>
#include <QVector>
#include <grp.h>
#include <pwd.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdexcept>

namespace AuroraSession {
inline const QString booster = QStringLiteral("/usr/libexec/mapplauncherd/booster-asteroid-qt6");
inline void require(bool ok, const QString &why) {
    if (!ok) throw std::runtime_error(why.toStdString());
}
inline QByteArray read(const QString &path) {
    QFile file(path);
    require(file.open(QIODevice::ReadOnly), "Cannot read " + path);
    QByteArray data = file.read(1024 * 1024 + 1);
    require(data.size() <= 1024 * 1024, "Unexpectedly large session metadata");
    return data;
}
inline unsigned statusNumber(const QByteArray &status, const QString &field) {
    auto match = QRegularExpression("^" + field + ":\\s+(\\d+)", QRegularExpression::MultilineOption)
                     .match(QString::fromLatin1(status));
    require(match.hasMatch(), "Missing process " + field);
    return match.captured(1).toUInt();
}
inline unsigned identity(const QByteArray &status, const QString &field) {
    auto match = QRegularExpression("^" + field + ":\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)\\s+(\\d+)",
                                    QRegularExpression::MultilineOption).match(QString::fromLatin1(status));
    require(match.hasMatch(), "Missing process identity");
    for (int i = 2; i <= 4; ++i) require(match.captured(i) == match.captured(1), "Mixed process identity");
    return match.captured(1).toUInt();
}
inline bool ownedSocket(const QString &path, unsigned uid) {
    struct stat info{};
    return ::lstat(QFile::encodeName(path).constData(), &info) == 0 &&
           S_ISSOCK(info.st_mode) && info.st_uid == uid;
}
struct Session {
    unsigned uid{}, gid{};
    QString pid, user, home, runtime, socket, observedPlatform;
    QMap<QByteArray, QByteArray> environment;
    QJsonObject json() const {
        QJsonObject env;
        for (auto it = environment.cbegin(); it != environment.cend(); ++it)
            env[QString::fromLatin1(it.key())] = QString::fromLocal8Bit(it.value());
        return {{"status", "PASS"}, {"pid", pid}, {"uid", int(uid)}, {"gid", int(gid)},
                {"user", user}, {"runtime", runtime}, {"wayland_socket", socket},
                {"observed_platform", observedPlatform}, {"environment", env},
                {"watch_modified", false}, {"gui_started", false}};
    }
};
inline Session inspect(const QString &proc = "/proc") {
    struct Candidate { QString pid; unsigned parent; };
    QVector<Candidate> candidates;
    QSet<unsigned> ids;
    for (const QString &pid : QDir(proc).entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        bool numeric = false; unsigned number = pid.toUInt(&numeric);
        if (!numeric) continue;
        const QString base = proc + "/" + pid;
        if (QFileInfo(base + "/exe").symLinkTarget() != booster) continue;
        try {
            if (!read(base + "/cmdline").split('\0').contains("--systemd")) continue;
            candidates.append({pid, statusNumber(read(base + "/status"), "PPid")});
            ids.insert(number);
        } catch (const std::exception &) { /* A process may exit during the scan. */ }
    }
    QVector<Candidate> masters;
    for (const auto &candidate : candidates)
        if (!ids.contains(candidate.parent)) masters.append(candidate);
    require(masters.size() == 1, "Expected one running Asteroid Qt6 booster service; refusing to guess");
    Session session;
    session.pid = masters.first().pid;
    const QString base = proc + "/" + session.pid;
    require(QFileInfo(base + "/exe").symLinkTarget() == booster, "Booster changed during inspection");
    const QByteArray status = read(base + "/status");
    session.uid = identity(status, "Uid"); session.gid = identity(status, "Gid");
    require(session.uid != 0, "GUI session must belong to a non-root user");
    const passwd *account = ::getpwuid(session.uid);
    require(account != nullptr, "GUI user not found in passwd");
    session.user = QString::fromLocal8Bit(account->pw_name);
    session.home = QString::fromLocal8Bit(account->pw_dir);
    const QSet<QByteArray> allowed{
        "XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QT_QPA_PLATFORM",
        "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_PLUGIN_PATH", "QML_IMPORT_PATH", "QML2_IMPORT_PATH",
        "QT_QUICK_BACKEND", "QT_SCALE_FACTOR", "QT_WAYLAND_SHELL_INTEGRATION",
        "QT_WAYLAND_CLIENT_BUFFER_INTEGRATION", "EGL_PLATFORM", "HYBRIS_EGLPLATFORM",
        "HYBRIS_LD_LIBRARY_PATH", "LD_LIBRARY_PATH", "FONTCONFIG_FILE", "FONTCONFIG_PATH"};
    for (const QByteArray &entry : read(base + "/environ").split('\0')) {
        const int equal = entry.indexOf('=');
        if (equal > 0 && allowed.contains(entry.left(equal)))
            session.environment[entry.left(equal)] = entry.mid(equal + 1);
    }
    const QFileInfo runtime(QString::fromLocal8Bit(session.environment.value("XDG_RUNTIME_DIR")));
    require(runtime.isDir() && runtime.ownerId() == session.uid && !runtime.canonicalFilePath().isEmpty(),
            "No GUI-owned runtime directory in the live booster environment");
    session.runtime = runtime.canonicalFilePath();
    session.environment["XDG_RUNTIME_DIR"] = QFile::encodeName(session.runtime);
    QString display = QString::fromLocal8Bit(session.environment.value("WAYLAND_DISPLAY"));
    if (display.isEmpty()) {
        QStringList sockets;
        for (const QString &name : QDir(session.runtime).entryList(QDir::AllEntries | QDir::System | QDir::NoDotAndDotDot))
            if (name.startsWith("wayland-") && ownedSocket(session.runtime + "/" + name, session.uid)) sockets.append(name);
        require(sockets.size() == 1, "Expected one GUI-owned Wayland socket; refusing to guess");
        display = sockets.first();
    }
    session.socket = QDir::isAbsolutePath(display) ? display : session.runtime + "/" + display;
    require(ownedSocket(session.socket, session.uid), "Wayland socket is absent or belongs to another user");
    session.environment["WAYLAND_DISPLAY"] = QFile::encodeName(display);
    session.observedPlatform = QString::fromLocal8Bit(session.environment.value("QT_QPA_PLATFORM"));
    // This program is a Wayland client. Never inherit a compositor's direct-display platform.
    session.environment["QT_QPA_PLATFORM"] = session.observedPlatform == "wayland-egl" ? "wayland-egl" : "wayland";
    if (!session.environment.contains("DBUS_SESSION_BUS_ADDRESS") && ownedSocket(session.runtime + "/bus", session.uid))
        session.environment["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + QFile::encodeName(session.runtime + "/bus");
    return session;
}
inline void enter(const Session &session) {
    require(::geteuid() == 0 || (unsigned(::geteuid()) == session.uid && unsigned(::getegid()) == session.gid),
            "Run from the ADB root shell or as the GUI owner");
    // Only this new process changes identity. No service, account or filesystem permissions change.
    if (::geteuid() == 0) {
        require(::initgroups(session.user.toLocal8Bit().constData(), session.gid) == 0, "initgroups failed");
        require(::setgid(session.gid) == 0 && ::setuid(session.uid) == 0, "Cannot enter GUI user identity");
    }
    require(unsigned(::getuid()) == session.uid && unsigned(::geteuid()) == session.uid &&
            unsigned(::getgid()) == session.gid, "GUI identity verification failed");
    const auto keys = QProcessEnvironment::systemEnvironment().keys();
    for (const QString &key : keys)
        if (key.startsWith("QT_") || key.startsWith("QML") || key.startsWith("HYBRIS_") ||
            key == "LD_PRELOAD" || key == "LD_LIBRARY_PATH" || key == "DISPLAY") qunsetenv(key.toLocal8Bit().constData());
    for (auto it = session.environment.cbegin(); it != session.environment.cend(); ++it) qputenv(it.key().constData(), it.value());
    qputenv("HOME", QFile::encodeName(session.home));
    qputenv("USER", session.user.toLocal8Bit()); qputenv("LOGNAME", session.user.toLocal8Bit());
    qputenv("XDG_SESSION_TYPE", "wayland");
    ::umask(0077);
}
}
