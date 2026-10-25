#pragma once
#include "state.hpp"
#include <QObject>
#include <QQuickItem>
#include <QStepCounterSensor>
#include <QTimer>
#include <QPointer>
#include <functional>

class AuroraSystem:public QObject {
    Q_OBJECT
    Q_PROPERTY(QString output READ output NOTIFY outputChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(QString usbMode READ usbMode NOTIFY usbChanged)
    Q_PROPERTY(QString usbDefault READ usbDefault NOTIFY usbChanged)
    Q_PROPERTY(QString usbAddress READ usbAddress NOTIFY usbChanged)
    Q_PROPERTY(QStringList usbModes READ usbModes NOTIFY usbChanged)
    Q_PROPERTY(bool usbBusy READ usbBusy NOTIFY usbChanged)
    Q_PROPERTY(bool nativeShell READ nativeShell CONSTANT)
    Q_PROPERTY(bool testMode READ testMode CONSTANT)
    Q_PROPERTY(bool stepsAvailable READ stepsAvailable NOTIFY stepsChanged)
    Q_PROPERTY(bool stepsValid READ stepsValid NOTIFY stepsChanged)
    Q_PROPERTY(qint64 steps READ steps NOTIFY stepsChanged)
    Q_PROPERTY(int bits READ bits CONSTANT)
    Q_PROPERTY(QString kernel READ kernel CONSTANT)
    Q_PROPERTY(QVariantList localEvents READ localEvents NOTIFY eventsChanged)
public:
    explicit AuroraSystem(QObject*parent=nullptr);
    ~AuroraSystem() override;
    QString output()const{return m_output;}QString error()const{return m_error;}
    QString usbMode()const{return m_usbMode;}QString usbDefault()const{return m_usbDefault;}
    QString usbAddress()const;QStringList usbModes()const{return m_usbModes;}
    bool usbBusy()const{return m_usbBusy;}bool nativeShell()const{return m_native;}bool testMode()const{return m_test;}
    bool stepsAvailable()const{return m_stepAvailable;}bool stepsValid()const{return m_stepValid;}qint64 steps()const{return m_steps;}
    int bits()const{return sizeof(void*)*8;}QString kernel()const;
    QVariantList localEvents()const{return m_state.eventsFor(m_selected);}
    Q_INVOKABLE void runCommand(const QString&name);
    Q_INVOKABLE void refreshUsb();
    Q_INVOKABLE void switchUsb(const QString&mode);
    Q_INVOKABLE void selectDay(const QString&day);
    Q_INVOKABLE void addEvent(const QString&title,const QString&iso);
    Q_INVOKABLE void removeEvent(const QString&id);
    Q_INVOKABLE void dismissNotification(uint id);
    Q_INVOKABLE void sceneReady(QQuickItem*scene);
Q_SIGNALS:
    void outputChanged();void errorChanged();void usbChanged();void stepsChanged();void eventsChanged();
private Q_SLOTS:
    void frameReady();
private:
    void helper(const QByteArray&,const std::function<void(bool,QByteArray)>&);
    void setUsbNow(const QString&mode);
    void captureNext();
    void finishCapture();
    QString readText(const QString&path)const;
    AuroraState m_state;
    QStepCounterSensor m_step;
    QTimer m_flush,m_confirm;
    QString m_output,m_error,m_usbMode="unknown",m_usbDefault="unknown",m_currentMethod;
    QStringList m_usbModes;
    bool m_test=false,m_native=false,m_usbBusy=false,m_stepAvailable=false,m_stepValid=false,m_framed=false,m_scene=false;
    qint64 m_steps=0;
    QDate m_selected=QDate::currentDate();
    QPointer<QQuickItem> m_capture;
    QString m_captureDir;
    int m_pageIndex=0;
};
