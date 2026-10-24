#include <QDir>
#include <QDebug>
#include <QGuiApplication>
#include <QImage>
#include <QQmlApplicationEngine>
#include <QQuickWindow>
#include <QQuickItem>
#include <QStringList>
#include <QTimer>
#include <QUrl>
#include <QVariant>
#include <functional>

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QQmlApplicationEngine engine;
    engine.load(QUrl::fromLocalFile(QCoreApplication::applicationDirPath() + "/qml/Main.qml"));
    if (engine.rootObjects().isEmpty()) return 2;
    if (argc == 1) return app.exec();
    if (argc != 3 || QString::fromLocal8Bit(argv[1]) != "--capture-dir") return 2;
    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
    QObject *shell = window ? window->findChild<QObject *>("auroraShell") : nullptr;
    if (!shell) return 2;
    const QDir output(QString::fromLocal8Bit(argv[2]));
    if (!QDir().mkpath(output.absolutePath())) return 2;
    shell->setProperty("motion", false);
    shell->setProperty("previewTime", true);
    const QStringList pages{"clock", "apps", "stopwatch", "style", "timer", "calculator"};
    int index = 0;
    std::function<void()> capture;
    capture = [&]() {
        if (index == pages.size()) { app.exit(0); return; }
        shell->setProperty("page", pages.at(index));
        window->requestUpdate();
        QTimer::singleShot(350, &app, [&]() {
            const QImage image = window->grabWindow();
            if (image.size() != QSize(384, 384) ||
                !image.save(output.filePath(pages.at(index) + ".png"))) {
                app.exit(3); return;
            }
            if (pages.at(index) != "clock" && pages.at(index) != "apps") {
                int visible = 0;
                for (int y = 20; y < 56; ++y)
                    for (int x = 170; x < 214; ++x)
                        if (qGray(image.pixel(x, y)) > 8) ++visible;
                if (visible < 500) {
                    auto *back = shell->findChild<QQuickItem *>("backButton");
                    qCritical() << "Navigation missing from" << pages.at(index) << "pixels" << visible;
                    if (back) qCritical() << "Back item" << back->isVisible() << back->opacity()
                                         << back->size() << back->mapToScene(QPointF()) << back->property("color");
                    app.exit(4); return;
                }
            }
            ++index;
            capture();
        });
    };
    QTimer::singleShot(250, &app, capture);
    return app.exec();
}
