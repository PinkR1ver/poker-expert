#pragma once

#include <iostream>
#include <vector>
#include <string>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdexcept>

namespace poker {

/**
 * 一个简单的磁盘映射缓冲区，用于存储海量节点而不断内存。
 * macOS 会自动管理页面换入换出到硬盘。
 */
template<typename T>
class MmapBuffer {
public:
    MmapBuffer(const std::string& filename, size_t max_elements) 
        : filename_(filename), max_elements_(max_elements) {
        
        size_t size = max_elements_ * sizeof(T);
        
        // 创建/打开文件
        fd_ = open(filename_.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0666);
        if (fd_ == -1) {
            throw std::runtime_error("Failed to open mmap file: " + filename_);
        }

        // 调整文件大小
        if (ftruncate(fd_, size) == -1) {
            close(fd_);
            throw std::runtime_error("Failed to ftruncate mmap file");
        }

        // 映射内存
        data_ = (T*)mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        if (data_ == MAP_FAILED) {
            close(fd_);
            throw std::runtime_error("Failed to mmap file");
        }
    }

    ~MmapBuffer() {
        if (data_ && data_ != MAP_FAILED) {
            munmap(data_, max_elements_ * sizeof(T));
        }
        if (fd_ != -1) {
            close(fd_);
        }
        // 如果需要，可以在这里删除临时文件
        // unlink(filename_.c_str());
    }

    T& operator[](size_t index) {
        if (index >= max_elements_) {
            fprintf(stderr, "[CFR-CPP] FATAL: MmapBuffer access out of bounds! Index %zu, Limit %zu\n", index, max_elements_);
            return data_[0]; 
        }
        if (index >= count_) count_ = index + 1;
        return data_[index];
    }

    const T& operator[](size_t index) const {
        if (index >= max_elements_) {
            fprintf(stderr, "[CFR-CPP] FATAL: MmapBuffer const access out of bounds! Index %zu, Limit %zu\n", index, max_elements_);
            return data_[0];
        }
        return data_[index];
    }

    void push_back(const T& val) {
        if (count_ >= max_elements_) {
            throw std::runtime_error("MmapBuffer overflow in file: " + filename_ + 
                                   " (Limit: " + std::to_string(max_elements_) + ")");
        }
        data_[count_++] = val;
    }

    size_t size() const { return count_; }
    T* data() { return data_; }
    void clear() { count_ = 0; }

    void reserve(size_t n) {
        // 对于 mmap，reserve 只是检查是否超过初始分配的大小
        if (n > max_elements_) {
            throw std::runtime_error("Cannot reserve more than max_elements in MmapBuffer");
        }
    }

private:
    std::string filename_;
    int fd_ = -1;
    T* data_ = nullptr;
    size_t count_ = 0;
    size_t max_elements_ = 0;
};

} // namespace poker

