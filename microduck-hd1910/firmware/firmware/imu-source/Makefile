PROJECT := imu_to_dxl_ReVA_M8A5_UART_IRQ_v1
BUILD := build
TOOLCHAIN ?= ../toolchains/arm-gnu-toolchain-14.3.rel1-x86_64-arm-none-eabi/bin/arm-none-eabi-
CUBE ?= ../third_party/STM32CubeG0
CMSIS_CORE := $(CUBE)/Drivers/CMSIS/Core/Include
CMSIS_DEVICE := $(CUBE)/Drivers/CMSIS/Device/ST/STM32G0xx

CC := $(TOOLCHAIN)gcc
OBJCOPY := $(TOOLCHAIN)objcopy
SIZE := $(TOOLCHAIN)size
HOST_CC ?= cc

CPU_FLAGS := -mcpu=cortex-m0plus -mthumb
CFLAGS := $(CPU_FLAGS) -std=c11 -Os -g3 -ffunction-sections -fdata-sections \
          -Wall -Wextra -Werror -DSTM32G031xx \
          -Iinclude -Ivendor/lsm6dsv16x \
          -I$(CMSIS_CORE) -I$(CMSIS_DEVICE)/Include
LDFLAGS := $(CPU_FLAGS) -Tlinker/STM32G031F8PX_FLASH.ld \
           -Wl,--gc-sections,-Map=$(BUILD)/$(PROJECT).map \
           --specs=nano.specs --specs=nosys.specs

APP_SOURCES := src/dxl_protocol.c src/id200_app.c src/main.c \
               vendor/lsm6dsv16x/lsm6dsv16x_reg.c
STARTUP := $(CMSIS_DEVICE)/Source/Templates/gcc/startup_stm32g031xx.s
SYSTEM := $(CMSIS_DEVICE)/Source/Templates/system_stm32g0xx.c
OBJECTS := $(patsubst %.c,$(BUILD)/%.o,$(APP_SOURCES)) \
           $(BUILD)/system_stm32g0xx.o $(BUILD)/startup_stm32g031xx.o

.PHONY: all clean test check

all: test $(BUILD)/$(PROJECT).bin

$(BUILD)/$(PROJECT).elf: $(OBJECTS) linker/STM32G031F8PX_FLASH.ld
	@mkdir -p $(dir $@)
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SIZE) $@

$(BUILD)/$(PROJECT).bin: $(BUILD)/$(PROJECT).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/system_stm32g0xx.o: $(SYSTEM)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/startup_stm32g031xx.o: $(STARTUP)
	@mkdir -p $(dir $@)
	$(CC) $(CPU_FLAGS) -x assembler-with-cpp -c $< -o $@

$(BUILD)/test_protocol: tests/test_protocol.c src/dxl_protocol.c src/id200_app.c
	@mkdir -p $(dir $@)
	$(HOST_CC) -std=c11 -O2 -Wall -Wextra -Werror -Iinclude $^ -o $@

test: $(BUILD)/test_protocol
	./$(BUILD)/test_protocol
	python3 -m py_compile tools/imu_live_mac.py
	python3 tools/imu_live_mac.py --self-test

check: all
	$(TOOLCHAIN)objdump -h -f $(BUILD)/$(PROJECT).elf
	$(TOOLCHAIN)nm -n $(BUILD)/$(PROJECT).elf | tail -20

clean:
	rm -rf $(BUILD)
