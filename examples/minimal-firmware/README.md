# Minimal Firmware Host Example

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

这是一个不依赖硬件的 C99 固件示例。`status_led` 驱动通过 `hal_gpio.h` 使用 GPIO；测试程序链接 fake HAL，并由 CTest 执行。Debug 构建保留调试符号并生成 linker map，便于演示评审和故障分析。任何构建、测试或符号化目标都不会连接或操作真实设备。

### 构建与测试

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware -DCMAKE_BUILD_TYPE=Debug
cmake --build build/minimal-firmware --config Debug
ctest --test-dir build/minimal-firmware -C Debug --output-on-failure
```

fake HAL 可以针对下一次 `configure-output` 或 `write` 调用注入失败。单元测试覆盖初始化时的低电平写入、配置失败、初始化低电平写入失败，以及 `status_led_set` 写入失败，且会检查调用次数和请求电平。

`reconnect_manager` 是 host-only 应用状态机示例：掉线后按 1/2/4 秒退避，最多三次；重复/乱序事件保持幂等，用户停止会取消 fake timer 并禁止后续重连。`reconnect-manager` CTest 使用 fake clock/network，需求矩阵位于 `requirements/network-reconnect.yml`。

### 真实 ELF 符号化正例

在 Linux 的 GNU/Clang ELF 构建中，以下目标从刚构建的 `status_led_tests` 读取真实 GNU build ID 和 `status_led_set` 地址，生成 `build/minimal-firmware/artifacts/matched-crash.log`，再使用 `addr2line` 或 `llvm-addr2line` 验证函数名和源码行。日志不包含手写或预置地址。

```sh
cmake --build build/minimal-firmware --target symbolization-fixture
```

正常执行 CTest 时还会运行 `symbolization-positive` 与不匹配负例。若要分开收集证据，可直接运行 Skill 脚本；交叉工具链可显式传入 `--readelf`、`--nm` 和 `--addr2line`：

```sh
python .github/skills/firmware-log-analysis/scripts/artifact_evidence.py roundtrip \
  --elf build/minimal-firmware/status_led_tests \
  --log build/minimal-firmware/artifacts/matched-crash.log \
  --symbol status_led_set
python .github/skills/firmware-log-analysis/scripts/artifact_evidence.py symbolize \
  --elf build/minimal-firmware/status_led_tests \
  --log build/minimal-firmware/artifacts/matched-crash.log
```

脚本只有在日志 build ID、当前 ELF build ID、日志地址、当前符号地址和源码行全部匹配时才输出 JSON `status: COMPLETE` 和 `symbolization`；不匹配时返回 `INSUFFICIENT_EVIDENCE` 与退出码 `3`。MSVC/PE 构建仍运行常规单元测试，但会明确跳过这个仅限 ELF 的正例。

`artifacts/sample-crash.log` 是故意不匹配的负例，不包含伪造地址。将它与任意已构建 ELF 一起交给 Reviewer 时，预期状态为 `INSUFFICIENT_EVIDENCE`，不得继续猜测符号。

### 缺陷评审夹具

`fixtures/defects/seeded_isr_overrun.c` 是故意保留的越界缺陷。正常配置看不到该 target；即使设置 `BUILD_DEFECT_FIXTURES=ON`，它也被 `EXCLUDE_FROM_ALL` 排除，只能显式构建，不能进入常规固件。

## English

This is a hardware-independent C99 firmware example. The `status_led` driver uses GPIO through `hal_gpio.h`; the test executable links a fake HAL and runs through CTest. Debug builds preserve debug symbols and produce a linker map for review and fault-analysis exercises. No build, test, or symbolization target connects to or operates a real device.

### Build and test

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware -DCMAKE_BUILD_TYPE=Debug
cmake --build build/minimal-firmware --config Debug
ctest --test-dir build/minimal-firmware -C Debug --output-on-failure
```

The fake HAL can inject a failure into the next `configure-output` or `write` call. Unit tests cover the initialization low write, configure failure, initialization low-write failure, and `status_led_set` write failure, including call-count and requested-level assertions.

`reconnect_manager` is a host-only application state-machine example: it backs off for 1/2/4 seconds after link loss, stops after three retries, handles duplicate/out-of-order events idempotently, and cancels the fake timer and prevents reconnect after user stop. The `reconnect-manager` CTest uses a fake clock/network; its requirement matrix is `requirements/network-reconnect.yml`.

### Positive symbolization from a real ELF

On a Linux GNU/Clang ELF build, the following target reads the real GNU build ID and `status_led_set` address from the newly built `status_led_tests`, writes `build/minimal-firmware/artifacts/matched-crash.log`, and verifies the function and source line with `addr2line` or `llvm-addr2line`. The log contains no handwritten or pre-seeded address.

```sh
cmake --build build/minimal-firmware --target symbolization-fixture
```

The regular CTest run includes `symbolization-positive` and a mismatched negative case. To collect evidence separately, invoke the Skill script directly. Cross toolchains can pass `--readelf`, `--nm`, and `--addr2line` explicitly:

```sh
python .github/skills/firmware-log-analysis/scripts/artifact_evidence.py roundtrip \
  --elf build/minimal-firmware/status_led_tests \
  --log build/minimal-firmware/artifacts/matched-crash.log \
  --symbol status_led_set
python .github/skills/firmware-log-analysis/scripts/artifact_evidence.py symbolize \
  --elf build/minimal-firmware/status_led_tests \
  --log build/minimal-firmware/artifacts/matched-crash.log
```

The helper emits JSON `status: COMPLETE` and `symbolization` only when the log build ID, current ELF build ID, logged address, current symbol address, and source line all agree. A mismatch returns `INSUFFICIENT_EVIDENCE` with exit code `3`. MSVC/PE builds still run the regular unit test and explicitly skip this ELF-only positive fixture.

`artifacts/sample-crash.log` is the deliberately mismatched negative fixture and contains no invented address. When it is paired with any built ELF, the expected Reviewer status is `INSUFFICIENT_EVIDENCE`; symbol guesses are not acceptable.

### Defect review fixture

`fixtures/defects/seeded_isr_overrun.c` intentionally contains an out-of-bounds defect. Its target is absent from normal configuration. Even with `BUILD_DEFECT_FIXTURES=ON`, `EXCLUDE_FROM_ALL` keeps it out of normal firmware builds and requires an explicit target build.
