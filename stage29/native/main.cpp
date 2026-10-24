#include "../../stage28/native/session.hpp"
#include "home_config.hpp"
#include <QQmlContext>
#include <QMouseEvent>
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
        const bool configMode = mode == "--activate-home" || mode == "--restore-home" || mode == "--home-status";
        const bool nativeCapture = mode == "--capture-native";
        const bool watch = mode == "--watch-session";
        const bool survey = mode == "--session-check";
        const bool capture = mode == "--capture-dir" || nativeCapture;
        AuroraSession::require((argc == 1) || ((watch || survey || configMode) && argc == 2) || (capture && argc == 3),
                               "Usage: aurora-home [--runtime-check|--session-check|--watch-session|--home-status|--activate-home|--restore-home|--capture-dir DIR|--capture-native DIR]");
        std::unique_ptr<QLockFile> lock;
        if (watch || survey || configMode) {
            AuroraSession::require(sizeof(void *) == 4 && QString::fromLatin1(qVersion()) == "6.11.3",
                                   "Watch mode requires ARM32 build and Qt 6.11.3; no GUI was started");
            const auto session = AuroraSession::inspect();
            if(!configMode)printJson(session.json());
            if (survey) return 0;
            AuroraSession::enter(session);
            if(configMode) {
                QCoreApplication app(argc,argv);
                QLockFile configLock(session.runtime+"/aurora-home-config.lock");
                AuroraSession::require(configLock.tryLock(0),"Home configuration is already being changed");
                const QString action=mode=="--activate-home"?"activate":mode=="--restore-home"?"restore":"status";
                printJson(configureHome(action));return 0;
            }
            lock = std::make_unique<QLockFile>(session.runtime + "/aurora-ui-home.lock");
            lock->setStaleLockTime(0);
            AuroraSession::require(lock->tryLock(0), "Aurora UI preview is already running");
        } else {
            AuroraSession::require(::geteuid() != 0 || (capture && qgetenv("QT_QPA_PLATFORM") == "offscreen"),
                                   "From the ADB root shell use --watch-session; refusing a root GUI");
            if (capture) AuroraSession::require(qgetenv("QT_QPA_PLATFORM") == "offscreen",
                                               "Capture mode requires explicit QT_QPA_PLATFORM=offscreen");
        }
        QGuiApplication app(argc, argv);
        QCoreApplication::setApplicationName("aurora-ui-home");
        QGuiApplication::setDesktopFileName("aurora-ui-home");
        QQuickView view;
        view.engine()->addImportPath("/usr/lib/qml");
        view.setResizeMode(QQuickView::SizeRootObjectToView);
        view.setTitle("Aurora UI Home");
        if (watch) view.setFlags(Qt::Window | Qt::FramelessWindowHint);
        QObject::connect(view.engine(), &QQmlEngine::quit, &app, &QCoreApplication::quit);
        view.rootContext()->setContextProperty("captureMode",capture);
        view.setSource(QUrl::fromLocalFile(QCoreApplication::applicationDirPath() + (nativeCapture?"/qml/Fixture.qml":"/qml/Main.qml")));
        if (view.status() != QQuickView::Ready || !view.rootObject()) return 2;
        view.resize(384, 384);
        if (watch) view.showFullScreen(); else view.show();
        guiStarted = true;
        if (watch) printJson({{"status", "WINDOW_REQUESTED"}, {"gui_uid", int(::geteuid())},
                              {"qt_runtime", qVersion()}, {"gui_started", true}});
        if (!capture) return app.exec();
        QQuickWindow *window = &view;
        QObject *shell = nativeCapture ? view.rootObject() : view.rootObject()->findChild<QObject *>("auroraShell");
        AuroraSession::require(shell != nullptr, "Aurora QML root missing");
        const QDir output(QString::fromLocal8Bit(argv[2]));
        AuroraSession::require(QDir().mkpath(output.absolutePath()), "Cannot create capture directory");
        shell->setProperty("motion", false); shell->setProperty("previewTime", true);
        const QStringList pages = nativeCapture ? QStringList{"clock","apps","control","settings"} : QStringList{"clock", "apps", "control", "settings", "stopwatch", "style", "timer", "calculator", "about"};
        int index = 0;
        std::function<void()> next;
        next = [&]() {
            if (index == pages.size()) {
                if(!nativeCapture) {
                    auto mouse=[&](QEvent::Type type,int x,int y,Qt::MouseButton button,Qt::MouseButtons buttons) {
                        QMouseEvent event(type,QPointF(x,y),QPointF(x,y),button,buttons,Qt::NoModifier);
                        QCoreApplication::sendEvent(window,&event);QCoreApplication::processEvents();
                    };
                    auto click=[&](int x,int y){mouse(QEvent::MouseButtonPress,x,y,Qt::LeftButton,Qt::LeftButton);mouse(QEvent::MouseButtonRelease,x,y,Qt::LeftButton,Qt::NoButton);};
                    shell->setProperty("page","apps");QCoreApplication::processEvents();click(192,192);
                    if(shell->property("page").toString()!="clock"){qCritical()<<"Central honeycomb icon did not open";app.exit(5);return;}
                    shell->setProperty("page","apps");QCoreApplication::processEvents();
                    mouse(QEvent::MouseButtonPress,192,192,Qt::LeftButton,Qt::LeftButton);
                    mouse(QEvent::MouseMove,250,230,Qt::NoButton,Qt::LeftButton);
                    mouse(QEvent::MouseButtonRelease,250,230,Qt::LeftButton,Qt::NoButton);
                    auto hex=shell->findChild<QObject*>("honeycomb");
                    if(!hex || qAbs(hex->property("panX").toDouble())<20){qCritical()<<"Honeycomb drag did not pan";app.exit(6);return;}
                    click(192,38);
                    if(shell->property("page").toString()!="clock"){qCritical()<<"Honeycomb back did not return home";app.exit(7);return;}
                    qInfo()<<"3 real Qt Quick input checks passed";
                }
                app.exit(0);return;
            }
            if(nativeCapture) {
                QVariant result;
                if(index==0 && (!QMetaObject::invokeMethod(shell,"checkIntegration",Q_RETURN_ARG(QVariant,result)) || result.toString()!="PASS")) { qCritical()<<"Integration fixture failed"<<result;app.exit(8);return; }
                QMetaObject::invokeMethod(shell,"selectPage",Q_ARG(QVariant,QVariant(pages.at(index))));
            } else shell->setProperty("page", pages.at(index));
            window->requestUpdate();
            QTimer::singleShot(450, &app, [&]() {
                const QImage image = window->grabWindow();
                if (image.size() != QSize(384, 384) || !image.save(output.filePath(pages.at(index) + ".png"))) {
                    app.exit(3); return;
                }
                if (!nativeCapture && pages.at(index) != "clock" && pages.at(index) != "apps") {
                    int pixels = 0;
                    for (int y = 20; y < 56; ++y) for (int x = 170; x < 214; ++x)
                        if (qGray(image.pixel(x, y)) > 8) ++pixels;
                    if (pixels < 500) { qCritical() << "Navigation not rendered" << pages.at(index); app.exit(4); return; }
                }
                ++index; next();
            });
        };
        QTimer::singleShot(500, &app, next);
        return app.exec();
    } catch (const std::exception &error) {
        printJson({{"status", "FAIL"}, {"error", error.what()}, {"gui_started", guiStarted}});
        return 2;
    }
}
