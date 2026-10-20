#define _GNU_SOURCE
#include <errno.h>
#include <linux/reboot.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

_Static_assert(sizeof(void *) == 4, "This helper must be ARM32 userspace");

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--check")) {
        puts("AURORA_RETURN_HELPER_ARM32_CHECK_OK");
        return 0;
    }
    if (argc != 2 || strcmp(argv[1], "--request")) {
        fputs("usage: aurora-return --check | --request\n", stderr);
        return 2;
    }
    /* Only the watch invokes this branch. CI exclusively uses --check. */
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
            LINUX_REBOOT_CMD_RESTART2, "bootloader");
    fprintf(stderr, "RESTART2 returned: %s; trying ordinary restart\n", strerror(errno));
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
            LINUX_REBOOT_CMD_RESTART, 0);
    fprintf(stderr, "Restart failed: %s\n", strerror(errno));
    return 1;
}
