# Self-check Agent Test Cases

Use these two files from `articles/` to test the tagging self-check flow. Upload only the article files, not this note.

## article_21_symphony_rehearsal_stage_schedule.md

Expected behavior: tagging should fail as out of business scope.

Reason: the article is about symphony rehearsal, stage scheduling, ticketing, and performance operations. It does not fit the active taxonomy built around troubleshooting, customer service, billing, accounts, and product training. Handling it would require a new top-level or second-level business category, so the self-check flow should not add a tag.

## article_22_barcode_scanner_receipt_printer_fault.md

Expected behavior: self-check should allow a new leaf under an existing second-level category.

Suggested path to observe: `硬件故障 / 输入外设 / 键盘背光异常`

Reason: the article clearly belongs to the existing second-level category `硬件故障 / 输入外设`, but the current leaves cover keyboard input, touch components, interface damage/recognition, external input devices, and fingerprint modules. The content focuses on built-in keyboard backlight zones, brightness, color, and lighting-control firmware, so it is a good candidate for a new third-level label under the existing input-peripherals second-level category.
