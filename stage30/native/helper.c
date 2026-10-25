#define _GNU_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/timerfd.h>
#include <sys/klog.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <poll.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>

// Fixed local operations only. No shell input, arbitrary command, file path,
// socket forwarding, or writable kernel-log operation is accepted.
static int send_all(int fd,const char*data,size_t length){while(length){ssize_t n=send(fd,data,length,MSG_NOSIGNAL);if(n<=0)return-1;data+=n;length-=n;}return 0;}
static void text(int fd,const char*s){send_all(fd,s,strlen(s));}
static int unit(const char*verb,const char*name){pid_t p=fork();if(p<0)return-1;if(!p){execl("/usr/bin/systemctl","systemctl",verb,name,(char*)0);_exit(127);}int status;while(waitpid(p,&status,0)<0)if(errno!=EINTR)return-1;return WIFEXITED(status)?WEXITSTATUS(status):-1;}
int main(int argc,char**argv){
    if(argc!=2||geteuid()!=0)return 2;
    char*end=0;unsigned long number=strtoul(argv[1],&end,10);
    if(!*argv[1]||*end||!number||number>0xffffffffUL)return 2;
    uid_t allowed=(uid_t)number;
    clearenv();setenv("PATH","/usr/bin:/bin",1);setenv("LANG","C",1);
    signal(SIGPIPE,SIG_IGN);umask(0007);
    int server=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);if(server<0)return 3;
    struct sockaddr_un address={.sun_family=AF_UNIX};strcpy(address.sun_path,"/run/aurora/control.sock");
    unlink(address.sun_path);unlink("/run/aurora/ready");
    if(bind(server,(void*)&address,sizeof(address))||chmod(address.sun_path,0660)||listen(server,4))return 4;
    int timer=timerfd_create(CLOCK_BOOTTIME,TFD_CLOEXEC);
    struct itimerspec deadline={.it_value={60,0}};if(timer<0||timerfd_settime(timer,0,&deadline,0))return 5;
    int confirmed=0;
    for(;;){
        struct pollfd fds[2]={{server,POLLIN,0},{timer,POLLIN,0}};
        if(poll(fds,2,-1)<0){if(errno==EINTR)continue;return 6;}
        if(fds[1].revents&POLLIN){unsigned long long tick;read(timer,&tick,sizeof(tick));if(!confirmed)unit("start","aurora-rollback.service");}
        if(!(fds[0].revents&POLLIN))continue;
        int client=accept4(server,0,0,SOCK_CLOEXEC);if(client<0)continue;
        struct ucred peer; socklen_t size=sizeof(peer);
        if(getsockopt(client,SOL_SOCKET,SO_PEERCRED,&peer,&size)||peer.uid!=allowed){text(client,"ERROR\nPeer UID rejected");close(client);continue;}
        struct timeval timeout={2,0};setsockopt(client,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(client,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
        char request[33]={0};ssize_t length=recv(client,request,sizeof(request)-1,0);
        if(length<=0){close(client);continue;}
        if(!strcmp(request,"kernel\n")){
            char*data=malloc(262144);int count=data?klogctl(3,data,262144):-1;
            if(count<0){text(client,"ERROR\n");text(client,strerror(errno));}else{text(client,"OK\n");send_all(client,data,(size_t)count);}free(data);
        }else if(!strcmp(request,"ssh\n")){
            if(unit("start","sshd.socket")==0)text(client,"OK\nExisting SSH authentication retained");else text(client,"ERROR\nCould not start sshd.socket");
        }else if(!strcmp(request,"ready\n")){
            char path[64];struct stat peer_file,installed_file;
            snprintf(path,sizeof(path),"/proc/%ld/exe",(long)peer.pid);
            int valid=stat(path,&peer_file)==0&&stat("/var/lib/aurora/aurora-compositor",&installed_file)==0&&peer_file.st_dev==installed_file.st_dev&&peer_file.st_ino==installed_file.st_ino&&installed_file.st_uid==0&&!(installed_file.st_mode&0022);
            if(valid){
                int out=open("/run/aurora/ready",O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW|O_CLOEXEC,0640);
                if(out>=0){write(out,"ready\n",6);close(out);confirmed=1;struct itimerspec off={0};timerfd_settime(timer,0,&off,0);text(client,"OK\nScene and first frame ready");}else text(client,"ERROR\nCannot save readiness");
            }else text(client,"ERROR\nReady caller is not the installed compositor");
        }else text(client,"ERROR\nUnsupported operation");
        close(client);
    }
}
