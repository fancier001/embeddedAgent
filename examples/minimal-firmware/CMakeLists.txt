cmake_minimum_required(VERSION 3.16)

project(minimal_firmware VERSION 1.0.0 LANGUAGES C)

include(CTest)

find_package(Python3 COMPONENTS Interpreter QUIET)

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

option(BUILD_DEFECT_FIXTURES "Expose intentionally defective review fixtures" OFF)

function(enable_firmware_diagnostics target)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /WX /Zi)
    else()
        target_compile_options(
            ${target}
            PRIVATE
                -Wall
                -Wextra
                -Wpedantic
                -Werror
                $<$<CONFIG:Debug>:-g3>
                $<$<CONFIG:Debug>:-fno-omit-frame-pointer>
        )
    endif()
endfunction()

add_library(status_led STATIC
    src/status_led.c
)
target_include_directories(status_led PUBLIC include)
enable_firmware_diagnostics(status_led)

add_library(reconnect_manager STATIC
    src/reconnect_manager.c
)
target_include_directories(reconnect_manager PUBLIC include)
enable_firmware_diagnostics(reconnect_manager)

add_executable(status_led_tests
    tests/fake_hal_gpio.c
    tests/test_status_led.c
)
target_include_directories(status_led_tests PRIVATE tests)
target_link_libraries(status_led_tests PRIVATE status_led)
enable_firmware_diagnostics(status_led_tests)

add_executable(reconnect_manager_tests
    tests/test_reconnect_manager.c
)
target_link_libraries(reconnect_manager_tests PRIVATE reconnect_manager)
enable_firmware_diagnostics(reconnect_manager_tests)

if(MSVC)
    target_link_options(
        status_led_tests
        PRIVATE
            /DEBUG
            /MAP:${CMAKE_CURRENT_BINARY_DIR}/status_led_tests.map
    )
elseif(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_link_options(
        status_led_tests
        PRIVATE
            -Wl,-Map,${CMAKE_CURRENT_BINARY_DIR}/status_led_tests.map
    )
    if(UNIX AND NOT APPLE)
        target_link_options(status_led_tests PRIVATE -Wl,--build-id=sha1)
    endif()
endif()

if(BUILD_TESTING)
    add_test(NAME status-led-unit COMMAND status_led_tests)
    add_test(NAME reconnect-manager COMMAND reconnect_manager_tests)
endif()

# A matching crash log must be derived from the executable that will be
# symbolized. Keep this host-only fixture out of normal firmware targets.
if(Python3_Interpreter_FOUND
   AND UNIX
   AND NOT APPLE
   AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    set(SYMBOLIZATION_FIXTURE_SCRIPT
        ${CMAKE_CURRENT_SOURCE_DIR}/../../.github/skills/firmware-log-analysis/scripts/artifact_evidence.py
    )
    set(SYMBOLIZATION_FIXTURE_LOG
        ${CMAKE_CURRENT_BINARY_DIR}/artifacts/matched-crash.log
    )
    set(SYMBOLIZATION_TOOL_ARGS)
    if(CMAKE_READELF)
        list(APPEND SYMBOLIZATION_TOOL_ARGS --readelf ${CMAKE_READELF})
    endif()
    if(CMAKE_NM)
        list(APPEND SYMBOLIZATION_TOOL_ARGS --nm ${CMAKE_NM})
    endif()
    if(CMAKE_ADDR2LINE)
        list(APPEND SYMBOLIZATION_TOOL_ARGS --addr2line ${CMAKE_ADDR2LINE})
    endif()

    add_custom_target(
        symbolization-fixture
        COMMAND ${CMAKE_COMMAND} -E make_directory
                ${CMAKE_CURRENT_BINARY_DIR}/artifacts
        COMMAND ${Python3_EXECUTABLE} ${SYMBOLIZATION_FIXTURE_SCRIPT}
                roundtrip
                --elf $<TARGET_FILE:status_led_tests>
                --log ${SYMBOLIZATION_FIXTURE_LOG}
                --symbol status_led_set
                ${SYMBOLIZATION_TOOL_ARGS}
        DEPENDS status_led_tests ${SYMBOLIZATION_FIXTURE_SCRIPT}
        VERBATIM
        COMMENT "Generate and verify a crash log from the built ELF"
    )

    if(BUILD_TESTING)
        add_test(
            NAME symbolization-positive
            COMMAND ${Python3_EXECUTABLE} ${SYMBOLIZATION_FIXTURE_SCRIPT}
                    roundtrip
                    --elf $<TARGET_FILE:status_led_tests>
                    --log
                    ${CMAKE_CURRENT_BINARY_DIR}/artifacts/ctest-matched-crash.log
                    --symbol status_led_set
                    ${SYMBOLIZATION_TOOL_ARGS}
        )
        add_test(
            NAME symbolization-mismatch
            COMMAND ${Python3_EXECUTABLE} ${SYMBOLIZATION_FIXTURE_SCRIPT}
                    match
                    --elf $<TARGET_FILE:status_led_tests>
                    --log ${CMAKE_CURRENT_SOURCE_DIR}/artifacts/sample-crash.log
                    --symbol status_led_set
                    ${SYMBOLIZATION_TOOL_ARGS}
        )
        set_tests_properties(symbolization-mismatch PROPERTIES WILL_FAIL TRUE)
    endif()
else()
    message(STATUS
        "Positive ELF symbolization fixture disabled: requires Python and "
        "a Linux GNU/Clang ELF build. Normal host tests remain available."
    )
endif()

if(Python3_Interpreter_FOUND AND BUILD_TESTING)
    add_test(
        NAME application-traceability
        COMMAND ${Python3_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/../../.github/skills/embedded-application-development/scripts/validate_traceability.py
                --input ${CMAKE_CURRENT_SOURCE_DIR}/requirements/network-reconnect.yml
                --root ${CMAKE_CURRENT_SOURCE_DIR}/../..
    )
endif()

# This source exists for QualityReviewer scenarios. Even when explicitly
# enabled, EXCLUDE_FROM_ALL prevents it from entering a normal build.
if(BUILD_DEFECT_FIXTURES)
    add_library(
        seeded_isr_overrun
        OBJECT
        EXCLUDE_FROM_ALL
        fixtures/defects/seeded_isr_overrun.c
    )
    target_include_directories(seeded_isr_overrun PRIVATE include)
endif()
