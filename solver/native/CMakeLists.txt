cmake_minimum_required(VERSION 3.12)
project(poker_solver_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 强制使用 Release 模式
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# 包含目录
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# 查找 Python 和 pybind11
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# 查找 pybind11
execute_process(
    COMMAND "${Python_EXECUTABLE}" -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
find_package(pybind11 REQUIRED HINTS ${pybind11_DIR})

# OpenMP 支持
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    message(STATUS "OpenMP found, enabling parallel computation")
    if(APPLE)
        if(NOT LIBOMP_INCLUDE_DIR)
            find_path(LIBOMP_INCLUDE_DIR omp.h HINTS /opt/homebrew/opt/libomp/include /usr/local/include)
        endif()
        if(NOT LIBOMP_LIBRARY)
            find_library(LIBOMP_LIBRARY NAMES omp libomp HINTS /opt/homebrew/opt/libomp/lib /usr/local/lib)
        endif()
        
        if(LIBOMP_INCLUDE_DIR AND LIBOMP_LIBRARY)
            message(STATUS "Found Homebrew libomp at: ${LIBOMP_LIBRARY}")
            include_directories(${LIBOMP_INCLUDE_DIR})
            set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Xpreprocessor -fopenmp")
            get_filename_component(LIBOMP_DIR ${LIBOMP_LIBRARY} DIRECTORY)
            set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -L${LIBOMP_DIR} -lomp")
            set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -L${LIBOMP_DIR} -lomp")
        endif()
    else()
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
    endif()
endif()

# 优化标志
if(MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /O2 /arch:AVX2")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native -flto")
endif()

# 定义模块
pybind11_add_module(poker_solver_cpp 
    bindings.cpp
    src/hand_evaluator.cpp
    src/cfr_engine.cpp
    src/game_tree_builder.cpp
)

# 链接 OpenMP
if(OpenMP_CXX_FOUND)
    target_link_libraries(poker_solver_cpp PRIVATE OpenMP::OpenMP_CXX)
endif()
