#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "stm32g031xx.h"

#ifdef FEETECH_NATIVE
#include "ft_fast_sync.h"
#include "ft_imu.h"
#include "ft_led_status.h"
#define BUS_MAX_PACKET FT_MAX_PACKET
#define IMU_BLOCK_SIZE FT_IMU_BLOCK_LENGTH
#else
#include "dxl_protocol.h"
#include "id200_app.h"
#define BUS_MAX_PACKET DXL2_MAX_PACKET
#define IMU_BLOCK_SIZE ID200_DATA_LENGTH
#endif
#include "lsm6dsv16x_reg.h"

#define SYSCLK_HZ              16000000u
#define DXL_BAUD               1000000u
#define RX_PACKET_TIMEOUT_MS   3u
#define IMU_POLL_PERIOD_MS     5u
#define IMU_WHO_AM_I_EXPECTED  LSM6DSV16X_ID
#define FIFO_DRAIN_LIMIT       2u
#ifdef FEETECH_NATIVE
/* A 15-servo native position SyncWrite is 128 bytes. Keep it off the IMU TX
   path but receive it without overflowing the old 63-byte ring. */
#define UART_RX_RING_SIZE      256u
#else
#define UART_RX_RING_SIZE      64u
#endif

static volatile uint32_t millisecond_tick;
static volatile uint8_t uart_rx_ring[UART_RX_RING_SIZE];
static volatile uint8_t uart_rx_head;
static volatile uint8_t uart_rx_tail;
static volatile bool uart_rx_overflow;

#ifdef FEETECH_NATIVE
static ft_fast_sync_detector_t fast_sync_detector;
static ft_imu_state_t app;
static ft_fast_sync_response_t fast_sync_responses[2];
static volatile uint8_t fast_sync_active_index;
static volatile bool fast_sync_enabled;
static volatile bool fast_sync_consumed;
static volatile bool fast_activity_pending;

static void uart_send_fast_sync_response(const uint8_t *packet, size_t length);

typedef ft_stream_t rx_stream_t;
#else
typedef struct {
    uint8_t bytes[DXL2_MAX_PACKET];
    size_t count;
    size_t expected;
    uint8_t header_state;
    uint32_t last_byte_tick;
} rx_stream_t;
#endif

void SysTick_Handler(void)
{
    ++millisecond_tick;
}

void USART2_IRQHandler(void)
{
    const uint32_t status = USART2->ISR;
    if ((status & (USART_ISR_ORE | USART_ISR_FE | USART_ISR_NE |
                   USART_ISR_PE)) != 0u) {
        USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF |
                      USART_ICR_NECF | USART_ICR_PECF;
        uart_rx_overflow = true;
#ifdef FEETECH_NATIVE
        ft_fast_sync_detector_reset(&fast_sync_detector);
#endif
    }

    while ((USART2->ISR & USART_ISR_RXNE_RXFNE) != 0u) {
        const uint8_t byte = (uint8_t)USART2->RDR;
#ifdef FEETECH_NATIVE
        if (fast_sync_enabled && ft_fast_sync_detector_push(
                &fast_sync_detector, byte, millisecond_tick)) {
            /*
             * The next native servo owns the slot immediately after this
             * 21-byte reply. Reply here instead of waiting for a main-loop
             * IMU SPI transfer to finish.
             */
            uart_rx_tail = uart_rx_head;
            ft_fast_sync_response_t *response =
                &fast_sync_responses[fast_sync_active_index & 1u];
            ft_fast_sync_response_finalize(response, millisecond_tick, &app);
            uart_send_fast_sync_response(
                response->bytes, FT_FAST_SYNC_RESPONSE_LENGTH);
            ft_imu_note_read(&app, response->sequence);
            uart_rx_overflow = false;
            fast_sync_consumed = true;
            fast_activity_pending = true;
            continue;
        }
#endif
        const uint8_t next =
            (uint8_t)((uart_rx_head + 1u) & (UART_RX_RING_SIZE - 1u));
        if (next == uart_rx_tail) {
            uart_rx_overflow = true;
        } else {
            uart_rx_ring[uart_rx_head] = byte;
            uart_rx_head = next;
        }
    }
}

static bool uart_rx_pop(uint8_t *byte)
{
    if (uart_rx_tail == uart_rx_head) {
        return false;
    }
    *byte = uart_rx_ring[uart_rx_tail];
    uart_rx_tail =
        (uint8_t)((uart_rx_tail + 1u) & (UART_RX_RING_SIZE - 1u));
    return true;
}

static void clock_init(void)
{
    RCC->CR = (RCC->CR | RCC_CR_HSION) & ~RCC_CR_HSIDIV;
    while ((RCC->CR & RCC_CR_HSIRDY) == 0u) {
    }

    RCC->CFGR &= ~(RCC_CFGR_SW | RCC_CFGR_HPRE | RCC_CFGR_PPRE);
    while ((RCC->CFGR & RCC_CFGR_SWS) != 0u) {
    }
    SystemCoreClock = SYSCLK_HZ;
}

static void delay_ms(uint32_t duration)
{
    const uint32_t start = millisecond_tick;
    while ((uint32_t)(millisecond_tick - start) < duration) {
    }
}

static void led_on(void)
{
    GPIOA->BSRR = GPIO_BSRR_BS0;
}

static void led_off(void)
{
    GPIOA->BSRR = GPIO_BSRR_BR0;
}

static void startup_signature(void)
{
    for (uint32_t i = 0u; i < 2u; ++i) {
        led_on();
        delay_ms(200u);
        led_off();
        delay_ms(200u);
    }
}

static void gpio_uart_spi_init(void)
{
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN;
    (void)RCC->IOPENR;

    /*
     * PA0 DEBUG_LED, PA1 active-low DXL_TX_EN, PA4 active-low IMU_CS.
     * PA2/PA3 USART2 TX/RX (AF1).
     * PA5/PA6/PA7 SPI1 SCK/MISO/MOSI (AF0).
     */
    GPIOA->BSRR = GPIO_BSRR_BR0 | GPIO_BSRR_BS1 | GPIO_BSRR_BS4;
    GPIOA->MODER = (GPIOA->MODER &
                    ~(GPIO_MODER_MODE0 | GPIO_MODER_MODE1 |
                      GPIO_MODER_MODE2 | GPIO_MODER_MODE3 |
                      GPIO_MODER_MODE4 | GPIO_MODER_MODE5 |
                      GPIO_MODER_MODE6 | GPIO_MODER_MODE7)) |
                   GPIO_MODER_MODE0_0 | GPIO_MODER_MODE1_0 |
                   GPIO_MODER_MODE2_1 | GPIO_MODER_MODE3_1 |
                   GPIO_MODER_MODE4_0 | GPIO_MODER_MODE5_1 |
                   GPIO_MODER_MODE6_1 | GPIO_MODER_MODE7_1;
    GPIOA->OTYPER &= ~(GPIO_OTYPER_OT0 | GPIO_OTYPER_OT1 |
                       GPIO_OTYPER_OT2 | GPIO_OTYPER_OT3 |
                       GPIO_OTYPER_OT4 | GPIO_OTYPER_OT5 |
                       GPIO_OTYPER_OT6 | GPIO_OTYPER_OT7);
    GPIOA->OSPEEDR = (GPIOA->OSPEEDR &
                      ~(GPIO_OSPEEDR_OSPEED0 | GPIO_OSPEEDR_OSPEED1 |
                        GPIO_OSPEEDR_OSPEED2 | GPIO_OSPEEDR_OSPEED3 |
                        GPIO_OSPEEDR_OSPEED4 | GPIO_OSPEEDR_OSPEED5 |
                        GPIO_OSPEEDR_OSPEED6 | GPIO_OSPEEDR_OSPEED7)) |
                     GPIO_OSPEEDR_OSPEED0_0 | GPIO_OSPEEDR_OSPEED1 |
                     GPIO_OSPEEDR_OSPEED2 | GPIO_OSPEEDR_OSPEED3 |
                     GPIO_OSPEEDR_OSPEED4_0 | GPIO_OSPEEDR_OSPEED5 |
                     GPIO_OSPEEDR_OSPEED6 | GPIO_OSPEEDR_OSPEED7;
    GPIOA->PUPDR &= ~(GPIO_PUPDR_PUPD0 | GPIO_PUPDR_PUPD1 |
                      GPIO_PUPDR_PUPD2 | GPIO_PUPDR_PUPD3 |
                      GPIO_PUPDR_PUPD4 | GPIO_PUPDR_PUPD5 |
                      GPIO_PUPDR_PUPD6 | GPIO_PUPDR_PUPD7);

    GPIOA->AFR[0] = (GPIOA->AFR[0] &
                     ~(GPIO_AFRL_AFSEL2 | GPIO_AFRL_AFSEL3 |
                       GPIO_AFRL_AFSEL5 | GPIO_AFRL_AFSEL6 |
                       GPIO_AFRL_AFSEL7)) |
                    GPIO_AFRL_AFSEL2_0 | GPIO_AFRL_AFSEL3_0;

    RCC->APBENR1 |= RCC_APBENR1_USART2EN;
    (void)RCC->APBENR1;
    USART2->CR1 = 0u;
    USART2->CR2 = 0u;
    USART2->CR3 = 0u;
    USART2->PRESC = 0u;
    USART2->BRR = SYSCLK_HZ / DXL_BAUD;
    USART2->ICR = 0xFFFFFFFFu;
    USART2->CR1 = USART_CR1_FIFOEN | USART_CR1_RXNEIE_RXFNEIE |
                  USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
    while ((USART2->ISR & (USART_ISR_TEACK | USART_ISR_REACK)) !=
           (USART_ISR_TEACK | USART_ISR_REACK)) {
    }
    NVIC_SetPriority(USART2_IRQn, 0u);
    NVIC_EnableIRQ(USART2_IRQn);

    RCC->APBENR2 |= RCC_APBENR2_SPI1EN;
    (void)RCC->APBENR2;
    SPI1->CR1 = 0u;
    SPI1->CR2 = (7u << SPI_CR2_DS_Pos) | SPI_CR2_FRXTH;
    /* SPI mode 0, master, software NSS, 16 MHz / 2 = 8 MHz. */
    SPI1->CR1 = SPI_CR1_MSTR | SPI_CR1_SSM | SPI_CR1_SSI;
    SPI1->CR1 |= SPI_CR1_SPE;
}

static uint8_t spi_transfer(uint8_t value)
{
    while ((SPI1->SR & SPI_SR_TXE) == 0u) {
    }
    *(__IO uint8_t *)&SPI1->DR = value;
    while ((SPI1->SR & SPI_SR_RXNE) == 0u) {
    }
    return *(__IO uint8_t *)&SPI1->DR;
}

static int32_t imu_write(void *handle, uint8_t reg,
                         const uint8_t *data, uint16_t length)
{
    (void)handle;
    GPIOA->BSRR = GPIO_BSRR_BR4;
    (void)spi_transfer((uint8_t)(reg & 0x7Fu));
    for (uint16_t i = 0u; i < length; ++i) {
        (void)spi_transfer(data[i]);
    }
    while ((SPI1->SR & SPI_SR_BSY) != 0u) {
    }
    GPIOA->BSRR = GPIO_BSRR_BS4;
    return 0;
}

static int32_t imu_read(void *handle, uint8_t reg,
                        uint8_t *data, uint16_t length)
{
    (void)handle;
    GPIOA->BSRR = GPIO_BSRR_BR4;
    (void)spi_transfer((uint8_t)(reg | 0x80u));
    for (uint16_t i = 0u; i < length; ++i) {
        data[i] = spi_transfer(0x00u);
    }
    while ((SPI1->SR & SPI_SR_BSY) != 0u) {
    }
    GPIOA->BSRR = GPIO_BSRR_BS4;
    return 0;
}

static void imu_delay(uint32_t duration)
{
    delay_ms(duration);
}

static bool imu_init(stmdev_ctx_t *ctx)
{
    uint8_t who_am_i = 0u;
    const lsm6dsv16x_fifo_sflp_raw_t fifo_sflp = {
        .game_rotation = 1u,
        .gravity = 0u,
        .gbias = 0u
    };
    const lsm6dsv16x_sflp_gbias_t zero_bias = {
        .gbias_x = 0.0f,
        .gbias_y = 0.0f,
        .gbias_z = 0.0f
    };

    ctx->write_reg = imu_write;
    ctx->read_reg = imu_read;
    ctx->mdelay = imu_delay;
    ctx->handle = NULL;
    ctx->priv_data = NULL;

    delay_ms(20u);
    if (lsm6dsv16x_device_id_get(ctx, &who_am_i) != 0 ||
        who_am_i != IMU_WHO_AM_I_EXPECTED) {
        return false;
    }

    if (lsm6dsv16x_sw_por(ctx) != 0 ||
        lsm6dsv16x_auto_increment_set(ctx, PROPERTY_ENABLE) != 0 ||
        lsm6dsv16x_block_data_update_set(ctx, PROPERTY_ENABLE) != 0 ||
        lsm6dsv16x_xl_full_scale_set(ctx, LSM6DSV16X_4g) != 0 ||
        lsm6dsv16x_gy_full_scale_set(ctx, LSM6DSV16X_500dps) != 0 ||
        lsm6dsv16x_fifo_watermark_set(ctx, 1u) != 0 ||
        lsm6dsv16x_fifo_sflp_batch_set(ctx, fifo_sflp) != 0 ||
        lsm6dsv16x_fifo_mode_set(ctx, LSM6DSV16X_STREAM_MODE) != 0 ||
        lsm6dsv16x_xl_data_rate_set(ctx, LSM6DSV16X_ODR_AT_120Hz) != 0 ||
        lsm6dsv16x_gy_data_rate_set(ctx, LSM6DSV16X_ODR_AT_120Hz) != 0 ||
        lsm6dsv16x_sflp_data_rate_set(ctx, LSM6DSV16X_SFLP_120Hz) != 0 ||
        lsm6dsv16x_sflp_game_rotation_set(ctx, PROPERTY_ENABLE) != 0 ||
        lsm6dsv16x_sflp_game_gbias_set(ctx, &zero_bias) != 0) {
        return false;
    }
    return true;
}

static bool imu_refresh(const stmdev_ctx_t *ctx,
                        uint8_t block[IMU_BLOCK_SIZE])
{
    int16_t gyro[3];
    lsm6dsv16x_fifo_status_t fifo_status;
    bool new_quaternion = false;

    if (lsm6dsv16x_angular_rate_raw_get(ctx, gyro) == 0) {
        for (uint32_t axis = 0u; axis < 3u; ++axis) {
            const uint16_t raw = (uint16_t)gyro[axis];
            block[axis * 2u] = (uint8_t)raw;
            block[axis * 2u + 1u] = (uint8_t)(raw >> 8);
        }
    }

    if (lsm6dsv16x_fifo_status_get(ctx, &fifo_status) == 0) {
        uint16_t count = fifo_status.fifo_level;
        if (count > FIFO_DRAIN_LIMIT) {
            count = FIFO_DRAIN_LIMIT;
        }
        while (count-- != 0u) {
            lsm6dsv16x_fifo_out_raw_t sample;
            if (lsm6dsv16x_fifo_out_raw_get(ctx, &sample) != 0) {
                break;
            }
            if (sample.tag ==
                (uint8_t)LSM6DSV16X_SFLP_GAME_ROTATION_VECTOR_TAG) {
                for (uint32_t i = 0u; i < 6u; ++i) {
                    block[6u + i] = sample.data[i];
                }
                new_quaternion = true;
            }
        }
    }
    return new_quaternion;
}

static void tx_enable(void)
{
    GPIOA->BSRR = GPIO_BSRR_BR1;
}

static void tx_disable(void)
{
    GPIOA->BSRR = GPIO_BSRR_BS1;
}

#ifdef FEETECH_NATIVE
static void uart_send_fast_sync_response(const uint8_t *packet, size_t length)
{
    /* Already in USART2_IRQHandler, so USART2 cannot re-enter this section. */
    USART2->CR1 &= ~USART_CR1_RE;
    while ((USART2->ISR & USART_ISR_REACK) != 0u) {
    }
    while ((USART2->ISR & USART_ISR_RXNE_RXFNE) != 0u) {
        (void)USART2->RDR;
    }
    USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF |
                  USART_ICR_NECF | USART_ICR_PECF;

    tx_enable();
    USART2->ICR = USART_ICR_TCCF;
    for (size_t i = 0u; i < length; ++i) {
        while ((USART2->ISR & USART_ISR_TXE_TXFNF) == 0u) {
        }
        USART2->TDR = packet[i];
    }
    while ((USART2->ISR & USART_ISR_TC) == 0u) {
    }

    USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF |
                  USART_ICR_NECF | USART_ICR_PECF;
    USART2->CR1 |= USART_CR1_RE;
    while ((USART2->ISR & USART_ISR_REACK) == 0u) {
    }
    /* Arm RX before releasing the half-duplex driver to the next responder. */
    tx_disable();
}

static void fast_sync_response_publish(const ft_imu_state_t *state)
{
    const uint8_t next = (uint8_t)(fast_sync_active_index ^ 1u);
    ft_fast_sync_response_prepare(&fast_sync_responses[next], state);
    __DMB();
    NVIC_DisableIRQ(USART2_IRQn);
    fast_sync_active_index = next;
    __DMB();
    NVIC_EnableIRQ(USART2_IRQn);
}
#endif

static void uart_send_packet(const uint8_t *packet, size_t length)
{
    /*
     * U4 leaves the physical RX path connected while PA1 enables the bus TX
     * driver.  FT2 merely masked RXNE interrupts during TX, so the USART FIFO
     * filled with our own echo.  It then released the bus before draining that
     * FIFO.  The first following Sync Read responder could already be sending,
     * and its leading bytes were occasionally drained with the echo.
     *
     * Disable the USART receiver itself while transmitting, then arm it and
     * its IRQ while the TX driver still holds the idle level.  Releasing PA1 is
     * the final operation, so there is no post-release blind/flush window.
     */
    NVIC_DisableIRQ(USART2_IRQn);
    USART2->CR1 &= ~(USART_CR1_RXNEIE_RXFNEIE | USART_CR1_RE);
    while ((USART2->ISR & USART_ISR_REACK) != 0u) {
    }
    while ((USART2->ISR & USART_ISR_RXNE_RXFNE) != 0u) {
        (void)USART2->RDR;
    }
    USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF |
                  USART_ICR_NECF | USART_ICR_PECF;
    uart_rx_tail = uart_rx_head;
    uart_rx_overflow = false;

    tx_enable();
    USART2->ICR = USART_ICR_TCCF;
    for (size_t i = 0u; i < length; ++i) {
        while ((USART2->ISR & USART_ISR_TXE_TXFNF) == 0u) {
        }
        USART2->TDR = packet[i];
    }
    while ((USART2->ISR & USART_ISR_TC) == 0u) {
    }
    USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF |
                  USART_ICR_NECF | USART_ICR_PECF;
    USART2->CR1 |= USART_CR1_RE;
    while ((USART2->ISR & USART_ISR_REACK) == 0u) {
    }
    USART2->CR1 |= USART_CR1_RXNEIE_RXFNEIE;
    NVIC_ClearPendingIRQ(USART2_IRQn);
    NVIC_EnableIRQ(USART2_IRQn);
    tx_disable();
}

static void stream_reset(rx_stream_t *stream)
{
    stream->count = 0u;
    stream->expected = 0u;
    stream->header_state = 0u;
}

static bool stream_push(rx_stream_t *stream, uint8_t byte)
{
#ifdef FEETECH_NATIVE
    return ft_stream_push(stream, byte, millisecond_tick);
#else
    stream->last_byte_tick = millisecond_tick;

    if (stream->count == 0u) {
        switch (stream->header_state) {
        case 0u:
            stream->header_state = (byte == 0xFFu) ? 1u : 0u;
            break;
        case 1u:
            stream->header_state = (byte == 0xFFu) ? 2u : 0u;
            break;
        case 2u:
            if (byte == 0xFDu) {
                stream->header_state = 3u;
            } else {
                stream->header_state = (byte == 0xFFu) ? 2u : 0u;
            }
            break;
        default:
            if (byte == 0x00u) {
                stream->bytes[0] = 0xFFu;
                stream->bytes[1] = 0xFFu;
                stream->bytes[2] = 0xFDu;
                stream->bytes[3] = 0x00u;
                stream->count = 4u;
                stream->header_state = 0u;
            } else {
                stream->header_state = (byte == 0xFFu) ? 1u : 0u;
            }
            break;
        }
        return false;
    }

    if (stream->count >= sizeof(stream->bytes)) {
        stream_reset(stream);
        return false;
    }
    stream->bytes[stream->count++] = byte;

    if (stream->count == 7u) {
        const size_t length_field = (size_t)stream->bytes[5] |
                                    ((size_t)stream->bytes[6] << 8);
        stream->expected = 7u + length_field;
        if (length_field < 3u || stream->expected > sizeof(stream->bytes)) {
            stream_reset(stream);
            return false;
        }
    }
    return stream->expected != 0u && stream->count == stream->expected;
#endif
}

static void imu_fault_forever(void)
{
    led_on();
    for (;;) {
    }
}

int main(void)
{
    uint8_t response[BUS_MAX_PACKET];
    uint8_t live_block[IMU_BLOCK_SIZE] = {0};
#ifndef FEETECH_NATIVE
    id200_state_t app;
#endif
    rx_stream_t stream = {0};
    stmdev_ctx_t imu;
    uint32_t last_imu_poll = 0u;
#ifdef FEETECH_NATIVE
    ft_led_status_t led_status;
#endif

    clock_init();
    gpio_uart_spi_init();
    SysTick_Config(SYSCLK_HZ / 1000u);
#ifdef FEETECH_NATIVE
    ft_imu_init(&app);
#else
    id200_init(&app);
#endif

    startup_signature();
    if (!imu_init(&imu)) {
        imu_fault_forever();
    }
    led_off();
#ifdef FEETECH_NATIVE
    ft_led_status_init(&led_status, millisecond_tick);
    fast_sync_response_publish(&app);
    NVIC_DisableIRQ(USART2_IRQn);
    ft_fast_sync_detector_reset(&fast_sync_detector);
    uart_rx_tail = uart_rx_head;
    uart_rx_overflow = false;
    fast_sync_consumed = false;
    fast_activity_pending = false;
    fast_sync_enabled = true;
    NVIC_EnableIRQ(USART2_IRQn);
#endif

    for (;;) {
#ifdef FEETECH_NATIVE
        if (fast_sync_consumed) {
            fast_sync_consumed = false;
            stream_reset(&stream);
        }
        if (fast_activity_pending) {
            fast_activity_pending = false;
            ft_led_status_note_response(&led_status, millisecond_tick);
        }
#endif
        if (uart_rx_overflow) {
            uart_rx_overflow = false;
            uart_rx_tail = uart_rx_head;
            stream_reset(&stream);
        }

        uint8_t byte;
        while (uart_rx_pop(&byte)) {
#ifdef FEETECH_NATIVE
            if (fast_sync_consumed) {
                fast_sync_consumed = false;
                stream_reset(&stream);
                continue;
            }
#endif
            if (stream_push(&stream, byte)) {
                const size_t request_length = stream.count;
                stream_reset(&stream);
                size_t response_length;
#ifdef FEETECH_NATIVE
                response_length = ft_imu_handle(
                    &app, stream.bytes, request_length,
                    response, sizeof(response), millisecond_tick);
#else
                response_length = id200_handle_packet(
                    &app, stream.bytes, request_length,
                    response, sizeof(response));
#endif
                if (response_length != 0u) {
                    uart_send_packet(response, response_length);
#ifdef FEETECH_NATIVE
                    ft_led_status_note_response(
                        &led_status, millisecond_tick);
#endif
                }
            }
        }

        if (stream.count != 0u &&
            (uint32_t)(millisecond_tick - stream.last_byte_tick) >
                RX_PACKET_TIMEOUT_MS) {
            stream_reset(&stream);
        }

        if (stream.count == 0u &&
            (uint32_t)(millisecond_tick - last_imu_poll) >=
                IMU_POLL_PERIOD_MS) {
            last_imu_poll = millisecond_tick;
            const bool new_quaternion = imu_refresh(&imu, live_block);
            if (new_quaternion) {
#ifdef FEETECH_NATIVE
                ft_led_status_note_quaternion(&led_status, millisecond_tick);
#endif
            }
#ifdef FEETECH_NATIVE
            ft_imu_set(&app, live_block, new_quaternion, millisecond_tick);
            fast_sync_response_publish(&app);
#else
            id200_set_imu_block(&app, live_block);
#endif
        }

#ifdef FEETECH_NATIVE
        if (ft_led_status_output(&led_status, millisecond_tick) == FT_LED_OFF) {
            led_off();
        } else {
            led_on();
        }
#endif
    }
}
