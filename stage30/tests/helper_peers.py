#!/usr/bin/env python3
"""Isolated ephemeral-runner test of the privileged helper's peer policy.

No kernel log is read and no SSH/systemd operation is requested. The successful
ready caller is a small root-owned fixture executable, not the real GUI.
"""
import json,os,socket,subprocess,sys,time
from pathlib import Path

CLIENT=r'''
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
int main(){int s=socket(AF_UNIX,SOCK_STREAM,0);struct sockaddr_un a={.sun_family=AF_UNIX};strcpy(a.sun_path,"/run/aurora/control.sock");if(connect(s,(void*)&a,sizeof(a)))return 2;write(s,"ready\n",6);char b[256];int n=read(s,b,sizeof(b));if(n>0)write(1,b,n);return 0;}
'''

def main(work,out):
    assert os.geteuid()!=0,'Run as the ordinary CI user with sudo available'
    prefix=Path('/var/lib/aurora');runtime=Path('/run/aurora')
    assert not prefix.exists() and not prefix.is_symlink() and not runtime.exists(),'Fixture paths already exist'
    uid=os.getuid();gid=os.getgid()
    source=work/'peer-client.c';source.write_text(CLIENT);client=work/'peer-client'
    subprocess.run(['cc',str(source),'-o',str(client)],check=True)
    subprocess.run(['sudo','mkdir',str(prefix),str(runtime)],check=True)
    subprocess.run(['sudo','chown','0:'+str(gid),str(runtime)],check=True)
    subprocess.run(['sudo','chmod','0750',str(runtime)],check=True)
    installed=prefix/'aurora-compositor'
    subprocess.run(['sudo','install','-o','0','-g','0','-m','0755',str(client),str(installed)],check=True)
    qemu=work/'sdk/sysroots/x86_64-oesdk-linux/usr/bin/qemu-arm'
    # The runner permits ordinary sudo, but does not grant sudo's -g override.
    # Match the service's primary GID inside the already-root fixture process.
    launcher='import os,sys;os.setgid(int(sys.argv[1]));os.execv(sys.argv[2],sys.argv[2:])'
    cmd=['sudo',sys.executable,'-c',launcher,str(gid),str(qemu),'-L',str(work/'v1-runtime'),str(work/'arm32-shell/aurora-helper'),str(uid)]
    process=subprocess.Popen(cmd,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    def request(data):
        s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect(str(runtime/'control.sock'));s.sendall(data);b=s.recv(2048);s.close();return b
    try:
        for attempt in range(60):
            if (runtime/'control.sock').exists():break
            if process.poll() is not None:raise ValueError(f'Helper exit {process.returncode}: '+process.stderr.read().decode(errors='replace'))
            time.sleep(.05)
        assert b'Unsupported operation' in request(b'not-a-command\n')
        assert b'not the installed compositor' in request(b'ready\n')
        result=subprocess.run(['sudo',str(installed)],capture_output=True,check=True)
        assert b'Peer UID rejected' in result.stdout,'Different UID was accepted'
        result=subprocess.run([str(installed)],capture_output=True,check=True)
        assert result.stdout.startswith(b'OK\n') and (runtime/'ready').exists(),'Verified GUI executable was rejected'
        out.mkdir(parents=True,exist_ok=True)
        (out/'helper-peer-check.json').write_text(json.dumps({'status':'PASS','checks':4,'kernel_log_read':False,'ssh_started':False,'recovery_executed':False},indent=2)+'\n')
        print('4 privileged helper peer/executable/operation checks passed',flush=True)
    finally:
        subprocess.run(['sudo','/bin/kill','-TERM','--','-'+str(process.pid)],check=False,capture_output=True)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:subprocess.run(['sudo','/bin/kill','-KILL','--','-'+str(process.pid)],check=False,capture_output=True)
        for path in (runtime/'control.sock',runtime/'ready',installed):
            subprocess.run(['sudo','rm','-f',str(path)],check=True)
        subprocess.run(['sudo','rmdir',str(prefix),str(runtime)],check=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
