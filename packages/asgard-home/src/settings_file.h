// Writes one key of system.cfg (SPEC CFG-4). No Qt, so test_settings_file.sh can run this exact code on the host.
#pragma once
#include <cerrno>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <fcntl.h>
#include <libgen.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

// Sets <key>=<value> in place, or removes the key if value is empty. Every other line stays as it is, comments too.
// A crash at any point leaves the old file or the new one, whole. Returns false, with the file untouched, if it can't
// read the existing file: writing then would replace all of the user's settings with this one key.
// lockPath is the lock the shell's set_setting and del_setting hold (J_CONF_LOCK in 001-functions).
inline bool writeSetting(const std::string &path, const std::string &lockPath, const std::string &key,
                         const std::string &value)
{
    const int lock = ::open(lockPath.c_str(), O_CREAT | O_WRONLY | O_CLOEXEC, 0644);
    if (lock >= 0)
        flock(lock, LOCK_EX);  // dropped when the fd closes; without it we still write, as the shell would be waiting
    struct Unlock { int fd; ~Unlock() { if (fd >= 0) ::close(fd); } } unlock{lock};

    std::vector<std::string> lines;
    struct stat st{};
    const bool exists = ::stat(path.c_str(), &st) == 0;
    if (exists) {
        std::ifstream in(path, std::ios::binary);
        if (!in)
            return false;
        std::stringstream all;
        all << in.rdbuf();
        if (in.bad() || all.bad())
            return false;
        std::string line;
        while (std::getline(all, line))
            lines.push_back(line);
    } else if (errno != ENOENT) {
        return false;
    }

    const std::string prefix = key + "=";
    std::vector<std::string> out;
    bool placed = false;
    for (const std::string &line : lines) {
        if (line.compare(0, prefix.size(), prefix) != 0) {
            out.push_back(line);
        } else if (!placed && !value.empty()) {
            out.push_back(prefix + value);
            placed = true;
        }
    }
    if (!placed && !value.empty())
        out.push_back(prefix + value);

    std::string text;
    for (const std::string &line : out)
        text += line + "\n";

    const std::string tmp = path + ".asgard-tmp";
    const int fd = ::open(tmp.c_str(), O_CREAT | O_TRUNC | O_WRONLY | O_CLOEXEC, exists ? (st.st_mode & 0777) : 0644);
    if (fd < 0)
        return false;
    size_t done = 0;
    while (done < text.size()) {
        const ssize_t n = ::write(fd, text.data() + done, text.size() - done);
        if (n <= 0) {
            ::close(fd);
            ::unlink(tmp.c_str());
            return false;
        }
        done += size_t(n);
    }
    const bool synced = ::fsync(fd) == 0;
    ::close(fd);
    if (!synced || std::rename(tmp.c_str(), path.c_str()) != 0) {
        ::unlink(tmp.c_str());
        return false;
    }
    std::string dir = path;
    const int dirFd = ::open(dirname(dir.data()), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dirFd >= 0) {
        ::fsync(dirFd);
        ::close(dirFd);
    }
    return true;
}
