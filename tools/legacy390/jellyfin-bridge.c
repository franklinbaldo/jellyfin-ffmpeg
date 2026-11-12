/* FFmpeg launcher for legacy NVIDIA decode + software Jellyfin filters.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
#define _GNU_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <unistd.h>
#include <signal.h>
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int probe(const char *ffprobe, const char *input)
{
    int fd[2], status;
    char buffer[8192], *line, *save = NULL;
    char codec[64] = "", pixel[64] = "", profile[128] = "";
    int width = 0, height = 0, level = 0;
    size_t used = 0;
    if (pipe(fd) < 0) return 0;
    pid_t pid = fork();
    if (pid < 0) { close(fd[0]); close(fd[1]); return 0; }
    if (pid == 0) {
        prctl(PR_SET_PDEATHSIG, SIGTERM);
        if (getppid() == 1) _exit(125);
        close(fd[0]); dup2(fd[1], STDOUT_FILENO); close(fd[1]);
        execl(ffprobe, ffprobe, "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=codec_name,pix_fmt,profile,width,height,level",
              "-of", "default=noprint_wrappers=1", input, (char *)NULL);
        _exit(127);
    }
    close(fd[1]);
    for (;;) {
        char chunk[1024];
        ssize_t n = read(fd[0], chunk, sizeof(chunk));
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        size_t take = (size_t)n;
        if (take > sizeof(buffer) - 1 - used) take = sizeof(buffer) - 1 - used;
        memcpy(buffer + used, chunk, take); used += take;
    }
    close(fd[0]); buffer[used] = 0;
    while (waitpid(pid, &status, 0) < 0) if (errno != EINTR) return 0;
    if (!WIFEXITED(status) || WEXITSTATUS(status)) return 0;
    for (line = strtok_r(buffer, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        if (!strncmp(line, "codec_name=", 11)) snprintf(codec, sizeof(codec), "%s", line + 11);
        else if (!strncmp(line, "pix_fmt=", 8)) snprintf(pixel, sizeof(pixel), "%s", line + 8);
        else if (!strncmp(line, "profile=", 8)) snprintf(profile, sizeof(profile), "%s", line + 8);
        else if (!strncmp(line, "width=", 6)) width = atoi(line + 6);
        else if (!strncmp(line, "height=", 7)) height = atoi(line + 7);
        else if (!strncmp(line, "level=", 6)) level = atoi(line + 6);
    }
    return !strcmp(codec, "h264") && !strcmp(pixel, "yuv420p") &&
           (!strcmp(profile, "High") || !strcmp(profile, "Main") ||
            !strcmp(profile, "Baseline") || !strcmp(profile, "Constrained Baseline")) &&
           width > 0 && width <= 1920 && height > 0 && height <= 1088 &&
           level > 0 && level <= 41;
}

static int cuda_available(void)
{
    void *lib = dlopen("libcuda.so.1", RTLD_NOW | RTLD_LOCAL);
    if (!lib) return 0;
    int (*init)(unsigned int) = (int (*)(unsigned int))dlsym(lib, "cuInit");
    int (*count_fn)(int *) = (int (*)(int *))dlsym(lib, "cuDeviceGetCount");
    int count = 0;
    int ok = init && count_fn && init(0) == 0 && count_fn(&count) == 0 && count > 0;
    dlclose(lib);
    return ok;
}

int main(int argc, char **argv)
{
    char path[PATH_MAX], real[PATH_MAX], ffprobe[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (n <= 0 || (size_t)n >= sizeof(path) - 1) return 127;
    path[n] = 0;
    char *slash = strrchr(path, '/');
    if (!slash) return 127;
    *slash = 0;
    if (snprintf(real, sizeof(real), "%s/ffmpeg", path) >= (int)sizeof(real) ||
        snprintf(ffprobe, sizeof(ffprobe), "%s/ffprobe", path) >= (int)sizeof(ffprobe)) return 127;
    int input_index = 0, hls = 0, sw_video = 0, explicit_hw = 0, no_video = 0;
    int filter_index = 0, complex_filter = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc && !input_index) input_index = i;
        if (!strcmp(argv[i], "-f") && i + 1 < argc && !strcmp(argv[i+1], "hls")) hls = 1;
        if ((!strncmp(argv[i], "-codec:v", 8) || !strncmp(argv[i], "-c:v", 4)) &&
            i + 1 < argc && !strcmp(argv[i+1], "libx264")) sw_video = 1;
        if (!strncmp(argv[i], "-hwaccel", 8) || strstr(argv[i], "_cuvid")) explicit_hw = 1;
        if (!strcmp(argv[i], "-vn")) no_video = 1;
        if ((!strcmp(argv[i], "-vf") || !strcmp(argv[i], "-filter:v") ||
             !strcmp(argv[i], "-filter:v:0") || !strcmp(argv[i], "-filter_complex")) && i + 1 < argc) {
            if (filter_index) explicit_hw = 1; /* Preserve unfamiliar multi-graph commands. */
            filter_index = i + 1;
            complex_filter = !strcmp(argv[i], "-filter_complex");
        }
    }
    int enable = getenv("LEGACY390_JELLYFIN_BRIDGE") &&
                 !getenv("LEGACY390_FORCE_CPU") && hls && sw_video &&
                 input_index && !explicit_hw && !no_video;
    if (enable) {
        const char *input = argv[input_index+1];
        struct stat st;
        if (!strncmp(input, "file:", 5)) input += 5;
        enable = input[0] == '/' && stat(input, &st) == 0 && S_ISREG(st.st_mode) &&
                 probe(ffprobe, input) && cuda_available();
    }
    char *download_filter = NULL;
    if (enable && filter_index) {
        const char *old = argv[filter_index], *at = old;
        if (complex_filter) {
            const char *labels[] = {"[0:0]", "[0:v:0]", "[0:v]"};
            at = NULL;
            for (size_t k = 0; k < sizeof(labels)/sizeof(labels[0]); k++) {
                const char *found = strstr(old, labels[k]);
                if (found && !strstr(found + strlen(labels[k]), labels[k])) {
                    at = found + strlen(labels[k]); break;
                }
            }
            if (!at) enable = 0;
        }
        if (enable) {
            const char *prefix = "hwdownload,format=nv12,";
            size_t before = (size_t)(at - old), len = strlen(old) + strlen(prefix) + 1;
            download_filter = malloc(len);
            if (!download_filter) return 127;
            memcpy(download_filter, old, before);
            memcpy(download_filter + before, prefix, strlen(prefix));
            strcpy(download_filter + before + strlen(prefix), at);
        }
    }
    char **args = calloc((size_t)argc + 12, sizeof(*args));
    if (!args) return 127;
    int j = 0; args[j++] = real;
    for (int i = 1; i < argc; i++) {
        if (enable && i == input_index) {
            args[j++] = "-hwaccel"; args[j++] = "cuda";
            args[j++] = "-hwaccel_output_format"; args[j++] = "cuda";
            args[j++] = "-hwaccel_flags"; args[j++] = "+unsafe_output";
        }
        if (enable && !filter_index && i == argc - 1) {
            args[j++] = "-vf"; args[j++] = "hwdownload,format=nv12";
        }
        args[j++] = enable && i == filter_index ? download_filter : argv[i];
    }
    if (enable) fprintf(stderr, "LEGACY390_BRIDGE nvdec=h264 output=filter_copyback pinned_pool=%s\n",
                        getenv("LEGACY390_PINNED_DOWNLOAD") && getenv("LEGACY390_PINNED_POOL") ? "enabled" : "disabled");
    execv(real, args);
    perror("legacy390 exec");
    return 127;
}
