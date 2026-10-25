#include "../../stage28/native/session.hpp"
#include <QQmlContext>
#include <QGuiApplication>
#include <QImage>
#include <QJsonDocument>
#include <QLockFile>
#include <QQmlEngine>
#include <QQuickView>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTimer>
#include <QDebug>
#include <functional>
#include <memory>
#include <cstdio>

static void printJson(const QJsonObject &json) {
    const QByteArray data = QJsonDocument(json).toJson(QJsonDocument::Compact) + '\n';
    std::fwrite(data.constData(), 1, data.size(), stdout);
    std::fflush(stdout);
}
int main(int argc, char **argv) {
    bool guiStarted = false;
    try {
        const QString mode = argc > 1 ? QString::fromLocal8Bit(argv[1]) : QString();
        if (argc == 2 && mode == "--runtime-check") {
            printJson({{"status", "PASS"}, {"bits", int(sizeof(void *) * 8)},
                       {"qt_runtime", qVersion()}, {"qt_build", QT_VERSION_STR}, {"gui_started", false}});
            return 0;
        }
        const bool watch = mode == "--watch-session";
        const bool survey = mode == "--session-check";
        const bool capture = mode == "--capture-dir";
        AuroraSession::require((argc == 1) || ((watch || survey) && argc == 2) || (capture && argc == 3),
                               "Usage: aurora-preview [--runtime-check|--session-check|--watch-session|--capture-dir DIR]");
        std::unique_ptr<QLockFile> lock;
        if (watch || survey) {
            AuroraSession::require(sizeof(void *) == 4 && QString::fromLatin1(qVersion()) == "6.11.3",
                                   "Watch mode requires ARM32 build and Qt 6.11.3; no GUI was started");
            const auto session = AuroraSession::inspect();
            printJson(session.json());
            if (survey) return 0;
            AuroraSession::enter(session);
            lock = std::make_unique<QLockFile>(session.runtime + "/aurora-ui-stage30-preview.lock");
            lock->setStaleLockTime(0);
            AuroraSession::require(lock->tryLock(0), "Aurora UI preview is already running");
        } else {
            AuroraSession::require(::geteuid() != 0 || (capture && qgetenv("QT_QPA_PLATFORM") == "offscreen"),
                                   "From the ADB root shell use --watch-session; refusing a root GUI");
            if (capture) AuroraSession::require(qgetenv("QT_QPA_PLATFORM") == "offscreen",
                                               "Capture mode requires explicit QT_QPA_PLATFORM=offscreen");
        }
        if(capture)qputenv("AURORA_CAPTURE_DIR",QFile::encodeName(QDir(QString::fromLocal8Bit(argv[2])).absolutePath()));
        QGuiApplication app(argc, argv);
        QCoreApplication::setApplicationName("aurora-ui-stage30-preview");
        QGuiApplication::setDesktopFileName("aurora-ui-stage30-preview");
        QQuickView view;
        view.engine()->addImportPath(QCoreApplication::applicationDirPath()+"/qml");
        view.engine()->addImportPath("/usr/lib/qml");
        view.rootContext()->setContextProperty("captureMode",capture);
        view.setResizeMode(QQuickView::SizeRootObjectToView);
        view.setTitle("Aurora Shell Preview");
        if (watch) view.setFlags(Qt::Window | Qt::FramelessWindowHint);
        QObject::connect(view.engine(), &QQmlEngine::quit, &app, &QCoreApplication::quit);
        view.setSource(QUrl::fromLocalFile(QCoreApplication::applicationDirPath() + "/qml/Preview.qml"));
        if (view.status() != QQuickView::Ready || !view.rootObject()) return 2;
        view.resize(384, 384);
        if (watch) view.showFullScreen(); else view.show();
        guiStarted = true;
        if (watch) printJson({{"status", "WINDOW_REQUESTED"}, {"gui_uid", int(::geteuid())},
                              {"qt_runtime", qVersion()}, {"gui_started", true}});
        return app.exec();
    } catch (const std::exception &error) {
        printJson({{"status", "FAIL"}, {"error", error.what()}, {"gui_started", guiStarted}});
        return 2;
    }
}
