#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/reboot.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

_Static_assert(sizeof(void *) == 8, "ARM64 static PID1 required");

static void log_line(const char *line)
{
    int fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    if (fd >= 0) { dprintf(fd, "<5>%s\n", line); close(fd); }
    dprintf(STDOUT_FILENO, "%s\n", line);
}

static int restart_bootloader(void)
{
    log_line("AURORA_STAGE26_RESTART2_BOOTLOADER");
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
            LINUX_REBOOT_CMD_RESTART2, "bootloader");
    log_line("AURORA_STAGE26_RESTART2_FAILED_TRY_NORMAL_RESTART");
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
            LINUX_REBOOT_CMD_RESTART, 0);
    return 1;
}

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--check")) {
        puts("AURORA_STAGE26_STATIC_PID1_CHECK_OK");
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "--request")) return restart_bootloader();
    if (argc != 1 || getpid() != 1) {
        fputs("PID1 only; use --check or --request\n", stderr);
        return 64;
    }
    struct timespec deadline;
    if (clock_gettime(CLOCK_MONOTONIC, &deadline)) return restart_bootloader();
    deadline.tv_sec += 90;
    pid_t child = fork();
    if (child < 0) return restart_bootloader();
    if (child == 0) {
        int rc;
        do { rc = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, NULL); }
        while (rc == EINTR);
        log_line(rc ? "AURORA_STAGE26_TIMER_ERROR" : "AURORA_STAGE26_DEADLINE");
        _exit(restart_bootloader());
    }
    log_line("AURORA_STAGE26_TIMER_ARMED seconds=90");
    char *args[] = {"/aurora26/busybox", "sh", "/aurora26/init", NULL};
    execv(args[0], args);
    log_line("AURORA_STAGE26_SHELL_EXEC_FAILED");
    /* Keep PID1 alive so its already-armed timer can run. */
    for (;;) pause();
}
