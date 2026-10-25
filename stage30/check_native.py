#!/usr/bin/env python3
"""Run public-ABI code and the exact redirected V1 compositor under ARM QEMU."""
import hashlib,json,os,shutil,struct,subprocess,sys,tempfile,time
from pathlib import Path
from patch_compositor import main as patch_compositor

REPO=Path(__file__).resolve().parent.parent
PAGES=('clock','apps','control','settings','notifications','calendar','usb','steps','terminal','system','stopwatch','timer','calculator','style','about')

def command(work,exe,args,extra=None,session=False):
    work=work.resolve()
    values={'LD_BIND_NOW':'1','LD_LIBRARY_PATH':'/usr/lib:/lib','QT_QPA_PLATFORM':'offscreen',
            'QT_QUICK_BACKEND':'software','QT_IM_MODULE':'none','QML_DISABLE_DISK_CACHE':'1',
            'QML_IMPORT_PATH':str(exe.parent/'qml')+':'+str(work/'v1-runtime/usr/lib/qml'),
            'DBUS_SYSTEM_BUS_ADDRESS':'disabled:','DBUS_SESSION_BUS_ADDRESS':os.environ.get('DBUS_SESSION_BUS_ADDRESS','disabled:') if session else 'disabled:',
            'HOME':str(work/'guest-home'),'XDG_RUNTIME_DIR':os.environ.get('AURORA_TEST_RUNTIME',str(work/'guest-runtime')),'TZ':'UTC'}
    for name in ('guest-home','guest-runtime'):(work/name).mkdir(exist_ok=True,mode=0o700)
    (work/'guest-runtime').chmod(0o700)
    values.update(extra or {})
    result=[str(work/'sdk/sysroots/x86_64-oesdk-linux/usr/bin/qemu-arm'),'-cpu','cortex-a15','-L',str(work/'v1-runtime')]
    for key,value in values.items():result+=['-E',key+'='+str(value)]
    return result+[str(exe),*args]

def run(work,exe,args,extra=None,session=False,timeout=50):
    return subprocess.run(command(work,exe,args,extra,session),capture_output=True,text=True,errors='backslashreplace',timeout=timeout)

def check(work,out):
    out.mkdir(parents=True,exist_ok=True);bundle=out/'aurora-stage30';bundle.mkdir(exist_ok=True)
    build=work/'arm32-shell'
    shutil.copytree(build/'qml',bundle/'qml',dirs_exist_ok=True)
    strip=work/'sdk/sysroots/x86_64-oesdk-linux/usr/bin/arm-oe-linux-gnueabi/arm-oe-linux-gnueabi-strip'
    for name in ('aurora-preview','aurora-helper'):
        shutil.copy2(build/name,bundle/name);subprocess.run([str(strip),'--strip-unneeded',str(bundle/name)],check=True);(bundle/name).chmod(0o755)
    subprocess.run([str(strip),'--strip-unneeded',str(bundle/'qml/Aurora/System/libaurorasystemplugin.so')],check=True)
    patch_compositor(work,bundle)
    for name in ('ui.qml','desktop.js'):shutil.copyfile(REPO/'stage30'/name,bundle/name)
    shutil.copytree(REPO/'stage30/compositor',bundle/'compositor',dirs_exist_ok=True)
    for name in ('install.sh','restore.sh'):shutil.copyfile(REPO/'stage30/deploy'/name,bundle/name)
    for file in (bundle/'aurora-preview',bundle/'aurora-helper',bundle/'aurora-compositor',bundle/'qml/Aurora/System/libaurorasystemplugin.so'):
        h=file.read_bytes()[:64]
        assert h[:6]==b'\x7fELF\x01\x01' and struct.unpack_from('<H',h,18)[0]==40
        assert struct.unpack_from('<I',h,36)[0]&0xFF000400==0x05000400
    for name,expected in [('aurora-state-tests','12 event persistence'),('aurora-session-tests','7 live-session')]:
        result=run(work,build/name,[]);(out/(name+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0 and expected in result.stdout,name
    result=run(work,bundle/'aurora-preview',['--runtime-check']);(out/'runtime.log').write_text(result.stdout+result.stderr)
    data=json.loads(result.stdout);assert result.returncode==0 and data['bits']==32 and data['qt_runtime']=='6.11.3'
    for mode in ('--session-check','--watch-session'):
        result=run(work,bundle/'aurora-preview',[mode]);(out/(mode[2:]+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==2 and json.loads(result.stdout)['gui_started'] is False
    screenshots=out/'preview';screenshots.mkdir(exist_ok=True)
    result=run(work,bundle/'aurora-preview',['--capture-dir',str(screenshots)])
    (out/'preview.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0, 'Independent scene/input capture failed'
    report=json.loads((screenshots/'capture-result.json').read_text());assert report['honeycomb_resets_after_home']
    # The actual modified copy uses its installed entry URI. The temporary
    # prefix is confined to an ephemeral CI runner and removed in finally.
    prefix=Path('/var/lib/aurora')
    if prefix.exists() or prefix.is_symlink():raise ValueError('CI prefix already exists; refusing to replace it')
    subprocess.run(['sudo','ln','-s',str(bundle),str(prefix)],check=True)
    native=out/'native';native.mkdir(exist_ok=True)
    try:
        cmd=command(work,bundle/'aurora-compositor',[],{'AURORA_CAPTURE_DIR':str(native),'WAYLAND_DISPLAY':'aurora-stage30-test'},session=True)
        with (out/'native.log').open('w') as log:
            process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            try:
                notified=False
                for attempt in range(35):
                    if process.poll() is not None:break
                    result=subprocess.run(['busctl','--user','--timeout=1','call','org.freedesktop.Notifications','/org/freedesktop/Notifications','org.freedesktop.Notifications','Notify','susssasa{sv}i','Aurora CI','0','','通知のテスト','V1の通知バックエンドから受信しました','0','0','0'],capture_output=True,text=True)
                    if result.returncode==0:notified=True;break
                    time.sleep(0.1)
                code=process.wait(timeout=45)
            except BaseException:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill()
                raise
        if code!=0:print((out/'native.log').read_text(errors='replace')[-16000:],file=sys.stderr)
        assert code==0,f'Native V1 compositor did not render the Aurora root (exit {code})'
        assert notified,'Notification DBus fixture failed'
        native_report=json.loads((native/'capture-result.json').read_text())
        assert native_report['native_compositor'] and native_report['first_frame_signal']
        assert native_report['notifications']>=1,'Real notification missing from native model'
        assert native_report['native_apps_visible']>=1,'Installed V1 applications missing from honeycomb'
        assert native_report['honeycomb_resets_after_home']
    finally:
        if prefix.is_symlink() and prefix.readlink()==bundle:subprocess.run(['sudo','rm',str(prefix)],check=True)
    for folder in (screenshots,native):
        for page in PAGES:assert (folder/(page+'.png')).stat().st_size>500
    result={'status':'PASS','bits':32,'qt_runtime':'6.11.3','preview_pages':15,'native_compositor_pages':15,
            'native_first_frame_signal':True,'native_notifications_verified':True,'native_apps_verified':True,'honeycomb_resets_after_home':True,
            'scene_input_checks':3,'state_checks':12,'session_checks':7,'kernel_or_usb_changed_on_watch':False,
            'watch_hardware_tested':False,'usb_modes_hardware_tested':False,'step_sensor_hardware_tested':False,
            'preview_sha256':hashlib.sha256((bundle/'aurora-preview').read_bytes()).hexdigest(),
            'compositor':json.loads((bundle/'compositor-patch.json').read_text())}
    (out/'native-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
    if not os.environ.get('AURORA_ISOLATED_BUS'):
        home=work/'bus-home';home.mkdir(parents=True,exist_ok=True)
        # Wayland's AF_UNIX socket path must fit sockaddr_un.sun_path (108 bytes).
        # A checked-out Actions workspace path is too long for that socket.
        with tempfile.TemporaryDirectory(prefix='aurora-s30-') as runtime:
            env=os.environ.copy();env.update({'AURORA_ISOLATED_BUS':'1','AURORA_TEST_RUNTIME':runtime,'HOME':str(home),'XDG_CONFIG_HOME':str(home/'config'),'XDG_DATA_HOME':str(home/'data')})
            raise SystemExit(subprocess.call(['dbus-run-session','--',sys.executable,*sys.argv],env=env))
    check(work,out)
