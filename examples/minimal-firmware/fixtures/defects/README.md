# Seeded Review Defect

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

`seeded_isr_overrun.c` 故意缺少接收缓冲区边界检查，用于验证 `QualityReviewer` 能否定位 ISR 与主循环共享状态、越界写入和计数器回绕风险。该文件不是生产代码，也不进入默认构建。

## English

`seeded_isr_overrun.c` intentionally omits the receive-buffer bounds check. It verifies that `QualityReviewer` identifies ISR/main-loop shared state, out-of-bounds writes, and counter-wrap risks. The file is not production code and is excluded from the default build.
