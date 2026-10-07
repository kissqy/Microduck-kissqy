/**
  ******************************************************************************
  * @file    lsm6dsv16x_reg.h
  * @author  Sensors Software Solution Team
  * @brief   This file contains all the functions prototypes for the
  *          lsm6dsv16x_reg.c driver.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2024 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef LSM6DSV16X_REGS_H
#define LSM6DSV16X_REGS_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include <stdint.h>
#include <stddef.h>
#include <math.h>

/** @addtogroup LSM6DSV16X
  * @{
  *
  */

/** @defgroup endiannes_def Endianness definitions
  * @{
  *
  */

#ifndef DRV_BYTE_ORDER
#ifndef __BYTE_ORDER__

#define DRV_LITTLE_ENDIAN 1234
#define DRV_BIG_ENDIAN    4321

/** if _BYTE_ORDER is not defined, choose the endianness of your architecture
  * by uncommenting the define which fits your platform endianness
  */
//#define DRV_BYTE_ORDER    DRV_BIG_ENDIAN
#define DRV_BYTE_ORDER    DRV_LITTLE_ENDIAN

#else /* defined __BYTE_ORDER__ */

#define DRV_LITTLE_ENDIAN  __ORDER_LITTLE_ENDIAN__
#define DRV_BIG_ENDIAN     __ORDER_BIG_ENDIAN__
#define DRV_BYTE_ORDER     __BYTE_ORDER__

#endif /* __BYTE_ORDER__*/
#endif /* DRV_BYTE_ORDER */

/**
  * @}
  *
  */

/** @defgroup st_common_types STMicroelectronics sensors common types
  * @{
  *
  */

#ifndef MEMS_SHARED_TYPES
#define MEMS_SHARED_TYPES

typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t bit0       : 1;
  uint8_t bit1       : 1;
  uint8_t bit2       : 1;
  uint8_t bit3       : 1;
  uint8_t bit4       : 1;
  uint8_t bit5       : 1;
  uint8_t bit6       : 1;
  uint8_t bit7       : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t bit7       : 1;
  uint8_t bit6       : 1;
  uint8_t bit5       : 1;
  uint8_t bit4       : 1;
  uint8_t bit3       : 1;
  uint8_t bit2       : 1;
  uint8_t bit1       : 1;
  uint8_t bit0       : 1;
#endif /* DRV_BYTE_ORDER */
} bitwise_t;

#define PROPERTY_DISABLE                (0U)
#define PROPERTY_ENABLE                 (1U)

/** @addtogroup  Interfaces_Functions
  * @brief       This section provide a set of functions used to read and
  *              write a generic register of the device.
  *              MANDATORY: return 0 -> no Error.
  * @{
  *
  */

typedef int32_t (*stmdev_write_ptr)(
  void *handle,
  uint8_t reg,
  const uint8_t *buf,
  uint16_t len);

typedef int32_t (*stmdev_read_ptr)(
  void *handle,
  uint8_t reg,
  uint8_t *buf,
  uint16_t len);

typedef void (*stmdev_mdelay_ptr)(uint32_t millisec);

typedef struct
{
  /** Component mandatory fields **/
  stmdev_write_ptr  write_reg;
  stmdev_read_ptr   read_reg;
  /** Component optional fields **/
  stmdev_mdelay_ptr   mdelay;
  /** Customizable optional pointer **/
  void *handle;

  /** private data **/
  void *priv_data;
} stmdev_ctx_t;

/**
  * @}
  *
  */

#endif /* MEMS_SHARED_TYPES */

#ifndef MEMS_UCF_SHARED_TYPES
#define MEMS_UCF_SHARED_TYPES

/** @defgroup    Generic_structs Generic address-data structure definition
  * @brief       This structure is useful to load a predefined configuration
  *              of a sensor.
  *              You can create a sensor configuration by your own or using
  *              Unico / Unicleo tools available on STMicroelectronics
  *              web site.
  *
  * @{
  *
  */

typedef struct
{
  uint8_t address;
  uint8_t data;
} ucf_line_t;

/**
  * @}
  *
  */

#endif /* MEMS_UCF_SHARED_TYPES */

/**
  * @}
  *
  */

/** @defgroup LSM6DSV16X_Infos Infos
  * @{
  *
  */

/** I2C Device Address 8 bit format  if SA0=0 -> D5 if SA0=1 -> D7 **/
#define LSM6DSV16X_I2C_ADD_L                    0xD5U
#define LSM6DSV16X_I2C_ADD_H                    0xD7U

/** Device Identification (Who am I) **/
#define LSM6DSV16X_ID                           0x70U

/**
  * @}
  *
  */

/** @defgroup bitfields_page_main Bitfields Page Main
  * @{
  *
  */

#define LSM6DSV16X_FUNC_CFG_ACCESS              0x1U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ois_ctrl_from_ui     : 1;
  uint8_t spi2_reset           : 1;
  uint8_t sw_por               : 1;
  uint8_t fsm_wr_ctrl_en       : 1;
  uint8_t not_used0            : 2;
  uint8_t shub_reg_access      : 1;
  uint8_t emb_func_reg_access  : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t emb_func_reg_access  : 1;
  uint8_t shub_reg_access      : 1;
  uint8_t not_used0            : 2;
  uint8_t fsm_wr_ctrl_en       : 1;
  uint8_t sw_por               : 1;
  uint8_t spi2_reset           : 1;
  uint8_t ois_ctrl_from_ui     : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_func_cfg_access_t;

#define LSM6DSV16X_PIN_CTRL                     0x2U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 5;
  uint8_t ibhr_por_en          : 1;
  uint8_t sdo_pu_en            : 1;
  uint8_t ois_pu_dis           : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ois_pu_dis           : 1;
  uint8_t sdo_pu_en            : 1;
  uint8_t ibhr_por_en          : 1;
  uint8_t not_used0            : 5;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_pin_ctrl_t;

#define LSM6DSV16X_IF_CFG                       0x3U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t i2c_i3c_disable      : 1;
  uint8_t not_used0            : 1;
  uint8_t sim                  : 1;
  uint8_t pp_od                : 1;
  uint8_t h_lactive            : 1;
  uint8_t asf_ctrl             : 1;
  uint8_t shub_pu_en           : 1;
  uint8_t sda_pu_en            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sda_pu_en            : 1;
  uint8_t shub_pu_en           : 1;
  uint8_t asf_ctrl             : 1;
  uint8_t h_lactive            : 1;
  uint8_t pp_od                : 1;
  uint8_t sim                  : 1;
  uint8_t not_used0            : 1;
  uint8_t i2c_i3c_disable      : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_if_cfg_t;

#define LSM6DSV16X_ODR_TRIG_CFG                 0x6U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t odr_trig_nodr        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t odr_trig_nodr        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_odr_trig_cfg_t;

#define LSM6DSV16X_FIFO_CTRL1                   0x7U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t wtm                  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t wtm                  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_ctrl1_t;

#define LSM6DSV16X_FIFO_CTRL2                   0x8U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t xl_dualc_batch_from_fsm       : 1;
  uint8_t uncompr_rate                  : 2;
  uint8_t not_used0                     : 1;
  uint8_t odr_chg_en                    : 1;
  uint8_t not_used1                     : 1;
  uint8_t fifo_compr_rt_en              : 1;
  uint8_t stop_on_wtm                   : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t stop_on_wtm                   : 1;
  uint8_t fifo_compr_rt_en              : 1;
  uint8_t not_used1                     : 1;
  uint8_t odr_chg_en                    : 1;
  uint8_t not_used0                     : 1;
  uint8_t uncompr_rate                  : 2;
  uint8_t xl_dualc_batch_from_fsm       : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_ctrl2_t;

#define LSM6DSV16X_FIFO_CTRL3                  0x9U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t bdr_xl               : 4;
  uint8_t bdr_gy               : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t bdr_gy               : 4;
  uint8_t bdr_xl               : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_ctrl3_t;

#define LSM6DSV16X_FIFO_CTRL4                  0x0AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_mode            : 3;
  uint8_t g_eis_fifo_en        : 1;
  uint8_t odr_t_batch          : 2;
  uint8_t dec_ts_batch         : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t dec_ts_batch         : 2;
  uint8_t odr_t_batch          : 2;
  uint8_t g_eis_fifo_en        : 1;
  uint8_t fifo_mode            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_ctrl4_t;

#define LSM6DSV16X_COUNTER_BDR_REG1            0x0BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t cnt_bdr_th           : 2;
  uint8_t not_used0            : 3;
  uint8_t trig_counter_bdr     : 2;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t trig_counter_bdr     : 2;
  uint8_t not_used0            : 3;
  uint8_t cnt_bdr_th           : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_counter_bdr_reg1_t;

#define LSM6DSV16X_COUNTER_BDR_REG2            0x0CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t cnt_bdr_th           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t cnt_bdr_th           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_counter_bdr_reg2_t;

#define LSM6DSV16X_INT1_CTRL                   0x0DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int1_drdy_xl         : 1;
  uint8_t int1_drdy_g          : 1;
  uint8_t not_used0            : 1;
  uint8_t int1_fifo_th         : 1;
  uint8_t int1_fifo_ovr        : 1;
  uint8_t int1_fifo_full       : 1;
  uint8_t int1_cnt_bdr         : 1;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t int1_cnt_bdr         : 1;
  uint8_t int1_fifo_full       : 1;
  uint8_t int1_fifo_ovr        : 1;
  uint8_t int1_fifo_th         : 1;
  uint8_t not_used0            : 1;
  uint8_t int1_drdy_g          : 1;
  uint8_t int1_drdy_xl         : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_int1_ctrl_t;

#define LSM6DSV16X_INT2_CTRL                   0x0EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int2_drdy_xl         : 1;
  uint8_t int2_drdy_g          : 1;
  uint8_t int2_drdy_g_eis      : 1;
  uint8_t int2_fifo_th         : 1;
  uint8_t int2_fifo_ovr        : 1;
  uint8_t int2_fifo_full       : 1;
  uint8_t int2_cnt_bdr         : 1;
  uint8_t int2_emb_func_endop  : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int2_emb_func_endop  : 1;
  uint8_t int2_cnt_bdr         : 1;
  uint8_t int2_fifo_full       : 1;
  uint8_t int2_fifo_ovr        : 1;
  uint8_t int2_fifo_th         : 1;
  uint8_t int2_drdy_g_eis      : 1;
  uint8_t int2_drdy_g          : 1;
  uint8_t int2_drdy_xl         : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_int2_ctrl_t;

#define LSM6DSV16X_WHO_AM_I                    0x0FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t id                   : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t id                   : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_who_am_i_t;

#define LSM6DSV16X_CTRL1                       0x10U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t odr_xl               : 4;
  uint8_t op_mode_xl           : 3;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t op_mode_xl           : 3;
  uint8_t odr_xl               : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl1_t;

#define LSM6DSV16X_CTRL2                       0x11U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t odr_g                : 4;
  uint8_t op_mode_g            : 3;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t op_mode_g            : 3;
  uint8_t odr_g                : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl2_t;

#define LSM6DSV16X_CTRL3                       0x12U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sw_reset             : 1;
  uint8_t not_used0            : 1;
  uint8_t if_inc               : 1;
  uint8_t not_used1            : 3;
  uint8_t bdu                  : 1;
  uint8_t boot                 : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t boot                 : 1;
  uint8_t bdu                  : 1;
  uint8_t not_used1            : 3;
  uint8_t if_inc               : 1;
  uint8_t not_used0            : 1;
  uint8_t sw_reset             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl3_t;

#define LSM6DSV16X_CTRL4                       0x13U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int2_in_lh           : 1;
  uint8_t drdy_pulsed          : 1;
  uint8_t int2_drdy_temp       : 1;
  uint8_t drdy_mask            : 1;
  uint8_t int2_on_int1         : 1;
  uint8_t not_used0            : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t int2_on_int1         : 1;
  uint8_t drdy_mask            : 1;
  uint8_t int2_drdy_temp       : 1;
  uint8_t drdy_pulsed          : 1;
  uint8_t int2_in_lh           : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl4_t;

#define LSM6DSV16X_CTRL5                       0x14U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int_en_i3c           : 1;
  uint8_t bus_act_sel          : 2;
  uint8_t not_used0            : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 5;
  uint8_t bus_act_sel          : 2;
  uint8_t int_en_i3c           : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl5_t;

#define LSM6DSV16X_CTRL6                       0x15U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_g                 : 4;
  uint8_t lpf1_g_bw            : 3;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t lpf1_g_bw            : 3;
  uint8_t fs_g                 : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl6_t;

#define LSM6DSV16X_CTRL7                       0x16U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t lpf1_g_en            : 1;
  uint8_t not_used0            : 3;
  uint8_t ah_qvar_c_zin        : 2;
  uint8_t int2_drdy_ah_qvar    : 1;
  uint8_t ah_qvar_en           : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ah_qvar_en           : 1;
  uint8_t int2_drdy_ah_qvar    : 1;
  uint8_t ah_qvar_c_zin        : 2;
  uint8_t not_used0            : 3;
  uint8_t lpf1_g_en            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl7_t;

#define LSM6DSV16X_CTRL8                       0x17U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_xl                : 2;
  uint8_t not_used0            : 1;
  uint8_t xl_dualc_en          : 1;
  uint8_t not_used1            : 1;
  uint8_t hp_lpf2_xl_bw        : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t hp_lpf2_xl_bw        : 3;
  uint8_t not_used1            : 1;
  uint8_t xl_dualc_en          : 1;
  uint8_t not_used0            : 1;
  uint8_t fs_xl                : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl8_t;

#define LSM6DSV16X_CTRL9                       0x18U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t usr_off_on_out       : 1;
  uint8_t usr_off_w            : 1;
  uint8_t not_used0            : 1;
  uint8_t lpf2_xl_en           : 1;
  uint8_t hp_slope_xl_en       : 1;
  uint8_t xl_fastsettl_mode    : 1;
  uint8_t hp_ref_mode_xl       : 1;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t hp_ref_mode_xl       : 1;
  uint8_t xl_fastsettl_mode    : 1;
  uint8_t hp_slope_xl_en       : 1;
  uint8_t lpf2_xl_en           : 1;
  uint8_t not_used0            : 1;
  uint8_t usr_off_w            : 1;
  uint8_t usr_off_on_out       : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl9_t;

#define LSM6DSV16X_CTRL10                      0x19U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t st_xl                : 2;
  uint8_t st_g                 : 2;
  uint8_t not_used0            : 2;
  uint8_t emb_func_debug       : 1;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t emb_func_debug       : 1;
  uint8_t not_used0            : 2;
  uint8_t st_g                 : 2;
  uint8_t st_xl                : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl10_t;

#define LSM6DSV16X_CTRL_STATUS                 0x1AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 2;
  uint8_t fsm_wr_ctrl_status   : 1;
  uint8_t not_used1            : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 5;
  uint8_t fsm_wr_ctrl_status   : 1;
  uint8_t not_used0            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl_status_t;

#define LSM6DSV16X_FIFO_STATUS1                0x1BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t diff_fifo            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t diff_fifo            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_status1_t;

#define LSM6DSV16X_FIFO_STATUS2                0x1CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t diff_fifo            : 1;
  uint8_t not_used0            : 2;
  uint8_t fifo_ovr_latched     : 1;
  uint8_t counter_bdr_ia       : 1;
  uint8_t fifo_full_ia         : 1;
  uint8_t fifo_ovr_ia          : 1;
  uint8_t fifo_wtm_ia          : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_wtm_ia          : 1;
  uint8_t fifo_ovr_ia          : 1;
  uint8_t fifo_full_ia         : 1;
  uint8_t counter_bdr_ia       : 1;
  uint8_t fifo_ovr_latched     : 1;
  uint8_t not_used0            : 2;
  uint8_t diff_fifo            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_status2_t;

#define LSM6DSV16X_ALL_INT_SRC                 0x1DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ff_ia                : 1;
  uint8_t wu_ia                : 1;
  uint8_t tap_ia               : 1;
  uint8_t not_used0            : 1;
  uint8_t d6d_ia               : 1;
  uint8_t sleep_change_ia      : 1;
  uint8_t shub_ia              : 1;
  uint8_t emb_func_ia          : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t emb_func_ia          : 1;
  uint8_t shub_ia              : 1;
  uint8_t sleep_change_ia      : 1;
  uint8_t d6d_ia               : 1;
  uint8_t not_used0            : 1;
  uint8_t tap_ia               : 1;
  uint8_t wu_ia                : 1;
  uint8_t ff_ia                : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_all_int_src_t;

#define LSM6DSV16X_STATUS_REG                  0x1EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t xlda                 : 1;
  uint8_t gda                  : 1;
  uint8_t tda                  : 1;
  uint8_t ah_qvarda            : 1;
  uint8_t gda_eis              : 1;
  uint8_t ois_drdy             : 1;
  uint8_t not_used0            : 1;
  uint8_t timestamp_endcount   : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t timestamp_endcount   : 1;
  uint8_t not_used0            : 1;
  uint8_t ois_drdy             : 1;
  uint8_t gda_eis              : 1;
  uint8_t ah_qvarda            : 1;
  uint8_t tda                  : 1;
  uint8_t gda                  : 1;
  uint8_t xlda                 : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_status_reg_t;

#define LSM6DSV16X_OUT_TEMP_L                  0x20U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t temp                 : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t temp                 : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_out_temp_l_t;

#define LSM6DSV16X_OUT_TEMP_H                  0x21U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t temp                 : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t temp                 : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_out_temp_h_t;

#define LSM6DSV16X_OUTX_L_G                    0x22U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outx_g               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outx_g               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outx_l_g_t;

#define LSM6DSV16X_OUTX_H_G                    0x23U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outx_g               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outx_g               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outx_h_g_t;

#define LSM6DSV16X_OUTY_L_G                    0x24U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outy_g               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outy_g               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outy_l_g_t;

#define LSM6DSV16X_OUTY_H_G                    0x25U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outy_g               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outy_g               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outy_h_g_t;

#define LSM6DSV16X_OUTZ_L_G                    0x26U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outz_g               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outz_g               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outz_l_g_t;

#define LSM6DSV16X_OUTZ_H_G                    0x27U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outz_g               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outz_g               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outz_h_g_t;

#define LSM6DSV16X_OUTX_L_A                    0x28U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outx_a               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outx_a               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outx_l_a_t;

#define LSM6DSV16X_OUTX_H_A                    0x29U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outx_a               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outx_a               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outx_h_a_t;

#define LSM6DSV16X_OUTY_L_A                    0x2AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outy_a               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outy_a               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outy_l_a_t;

#define LSM6DSV16X_OUTY_H_A                    0x2BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outy_a               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outy_a               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outy_h_a_t;

#define LSM6DSV16X_OUTZ_L_A                    0x2CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outz_a               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outz_a               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outz_l_a_t;

#define LSM6DSV16X_OUTZ_H_A                    0x2DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t outz_a               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t outz_a               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_outz_h_a_t;

#define LSM6DSV16X_UI_OUTX_L_G_OIS_EIS         0x2EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outx_g_ois_eis    : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outx_g_ois_eis    : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outx_l_g_ois_eis_t;

#define LSM6DSV16X_UI_OUTX_H_G_OIS_EIS         0x2FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outx_g_ois_eis    : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outx_g_ois_eis    : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outx_h_g_ois_eis_t;

#define LSM6DSV16X_UI_OUTY_L_G_OIS_EIS         0x30U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outy_g_ois_eis    : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outy_g_ois_eis    : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outy_l_g_ois_eis_t;

#define LSM6DSV16X_UI_OUTY_H_G_OIS_EIS         0x31U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outy_g_ois_eis    : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outy_g_ois_eis    : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outy_h_g_ois_eis_t;

#define LSM6DSV16X_UI_OUTZ_L_G_OIS_EIS         0x32U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outz_g_ois_eis    : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outz_g_ois_eis    : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outz_l_g_ois_eis_t;

#define LSM6DSV16X_UI_OUTZ_H_G_OIS_EIS         0x33U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outz_g_ois_eis    : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outz_g_ois_eis    : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outz_h_g_ois_eis_t;

#define LSM6DSV16X_UI_OUTX_L_A_OIS_DUALC       0x34U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outx_a_ois_dualc  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outx_a_ois_dualc  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outx_l_a_ois_dualc_t;

#define LSM6DSV16X_UI_OUTX_H_A_OIS_DUALC       0x35U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outx_a_ois_dualc  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outx_a_ois_dualc  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outx_h_a_ois_dualc_t;

#define LSM6DSV16X_UI_OUTY_L_A_OIS_DUALC       0x36U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outy_a_ois_dualc  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outy_a_ois_dualc  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outy_l_a_ois_dualc_t;

#define LSM6DSV16X_UI_OUTY_H_A_OIS_DUALC       0x37U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outy_a_ois_dualc  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outy_a_ois_dualc  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outy_h_a_ois_dualc_t;

#define LSM6DSV16X_UI_OUTZ_L_A_OIS_DUALC       0x38U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outz_a_ois_dualc  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outz_a_ois_dualc  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outz_l_a_ois_dualc_t;

#define LSM6DSV16X_UI_OUTZ_H_A_OIS_DUALC       0x39U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_outz_a_ois_dualc  : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_outz_a_ois_dualc  : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_outz_h_a_ois_dualc_t;

#define LSM6DSV16X_AH_QVAR_OUT_L               0x3AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ah_qvar              : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ah_qvar              : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ah_qvar_out_l_t;

#define LSM6DSV16X_AH_QVAR_OUT_H               0x3BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ah_qvar              : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ah_qvar              : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ah_qvar_out_h_t;

#define LSM6DSV16X_TIMESTAMP0                  0x40U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t timestamp            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t timestamp            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_timestamp0_t;

#define LSM6DSV16X_TIMESTAMP1                  0x41U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t timestamp            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t timestamp            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_timestamp1_t;

#define LSM6DSV16X_TIMESTAMP2                  0x42U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t timestamp            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t timestamp            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_timestamp2_t;

#define LSM6DSV16X_TIMESTAMP3                  0x43U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t timestamp            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t timestamp            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_timestamp3_t;

#define LSM6DSV16X_UI_STATUS_REG_OIS           0x44U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t xlda_ois             : 1;
  uint8_t gda_ois              : 1;
  uint8_t gyro_settling        : 1;
  uint8_t not_used0            : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 5;
  uint8_t gyro_settling        : 1;
  uint8_t gda_ois              : 1;
  uint8_t xlda_ois             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_status_reg_ois_t;

#define LSM6DSV16X_WAKE_UP_SRC                 0x45U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t z_wu                 : 1;
  uint8_t y_wu                 : 1;
  uint8_t x_wu                 : 1;
  uint8_t wu_ia                : 1;
  uint8_t sleep_state          : 1;
  uint8_t ff_ia                : 1;
  uint8_t sleep_change_ia      : 1;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t sleep_change_ia      : 1;
  uint8_t ff_ia                : 1;
  uint8_t sleep_state          : 1;
  uint8_t wu_ia                : 1;
  uint8_t x_wu                 : 1;
  uint8_t y_wu                 : 1;
  uint8_t z_wu                 : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_wake_up_src_t;

#define LSM6DSV16X_TAP_SRC                     0x46U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t z_tap                : 1;
  uint8_t y_tap                : 1;
  uint8_t x_tap                : 1;
  uint8_t tap_sign             : 1;
  uint8_t double_tap           : 1;
  uint8_t single_tap           : 1;
  uint8_t tap_ia               : 1;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t tap_ia               : 1;
  uint8_t single_tap           : 1;
  uint8_t double_tap           : 1;
  uint8_t tap_sign             : 1;
  uint8_t x_tap                : 1;
  uint8_t y_tap                : 1;
  uint8_t z_tap                : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_tap_src_t;

#define LSM6DSV16X_D6D_SRC                     0x47U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t xl                   : 1;
  uint8_t xh                   : 1;
  uint8_t yl                   : 1;
  uint8_t yh                   : 1;
  uint8_t zl                   : 1;
  uint8_t zh                   : 1;
  uint8_t d6d_ia               : 1;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t d6d_ia               : 1;
  uint8_t zh                   : 1;
  uint8_t zl                   : 1;
  uint8_t yh                   : 1;
  uint8_t yl                   : 1;
  uint8_t xh                   : 1;
  uint8_t xl                   : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_d6d_src_t;

#define LSM6DSV16X_STATUS_MASTER_MAINPAGE      0x48U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sens_hub_endop       : 1;
  uint8_t not_used0            : 2;
  uint8_t slave0_nack          : 1;
  uint8_t slave1_nack          : 1;
  uint8_t slave2_nack          : 1;
  uint8_t slave3_nack          : 1;
  uint8_t wr_once_done         : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t wr_once_done         : 1;
  uint8_t slave3_nack          : 1;
  uint8_t slave2_nack          : 1;
  uint8_t slave1_nack          : 1;
  uint8_t slave0_nack          : 1;
  uint8_t not_used0            : 2;
  uint8_t sens_hub_endop       : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_status_master_mainpage_t;

#define LSM6DSV16X_EMB_FUNC_STATUS_MAINPAGE    0x49U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t is_step_det          : 1;
  uint8_t is_tilt              : 1;
  uint8_t is_sigmot            : 1;
  uint8_t not_used1            : 1;
  uint8_t is_fsm_lc            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t is_fsm_lc            : 1;
  uint8_t not_used1            : 1;
  uint8_t is_sigmot            : 1;
  uint8_t is_tilt              : 1;
  uint8_t is_step_det          : 1;
  uint8_t not_used0            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_status_mainpage_t;

#define LSM6DSV16X_FSM_STATUS_MAINPAGE         0x4AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t is_fsm1              : 1;
  uint8_t is_fsm2              : 1;
  uint8_t is_fsm3              : 1;
  uint8_t is_fsm4              : 1;
  uint8_t is_fsm5              : 1;
  uint8_t is_fsm6              : 1;
  uint8_t is_fsm7              : 1;
  uint8_t is_fsm8              : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t is_fsm8              : 1;
  uint8_t is_fsm7              : 1;
  uint8_t is_fsm6              : 1;
  uint8_t is_fsm5              : 1;
  uint8_t is_fsm4              : 1;
  uint8_t is_fsm3              : 1;
  uint8_t is_fsm2              : 1;
  uint8_t is_fsm1              : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_status_mainpage_t;

#define LSM6DSV16X_MLC_STATUS_MAINPAGE         0x4BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t is_mlc1              : 1;
  uint8_t is_mlc2              : 1;
  uint8_t is_mlc3              : 1;
  uint8_t is_mlc4              : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t is_mlc4              : 1;
  uint8_t is_mlc3              : 1;
  uint8_t is_mlc2              : 1;
  uint8_t is_mlc1              : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_status_mainpage_t;

#define LSM6DSV16X_INTERNAL_FREQ               0x4FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t freq_fine            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t freq_fine            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_internal_freq_t;

#define LSM6DSV16X_FUNCTIONS_ENABLE            0x50U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t inact_en             : 2;
  uint8_t not_used0            : 1;
  uint8_t dis_rst_lir_all_int  : 1;
  uint8_t not_used1            : 2;
  uint8_t timestamp_en         : 1;
  uint8_t interrupts_enable    : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t interrupts_enable    : 1;
  uint8_t timestamp_en         : 1;
  uint8_t not_used1            : 2;
  uint8_t dis_rst_lir_all_int  : 1;
  uint8_t not_used0            : 1;
  uint8_t inact_en             : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_functions_enable_t;

#define LSM6DSV16X_DEN                         0x51U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t den_xl_g             : 1;
  uint8_t den_z                : 1;
  uint8_t den_y                : 1;
  uint8_t den_x                : 1;
  uint8_t den_xl_en            : 1;
  uint8_t lvl2_en              : 1;
  uint8_t lvl1_en              : 1;
  uint8_t not_used0            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t lvl1_en              : 1;
  uint8_t lvl2_en              : 1;
  uint8_t den_xl_en            : 1;
  uint8_t den_x                : 1;
  uint8_t den_y                : 1;
  uint8_t den_z                : 1;
  uint8_t den_xl_g             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_den_t;

#define LSM6DSV16X_INACTIVITY_DUR              0x54U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t inact_dur            : 2;
  uint8_t xl_inact_odr         : 2;
  uint8_t wu_inact_ths_w       : 3;
  uint8_t sleep_status_on_int  : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sleep_status_on_int  : 1;
  uint8_t wu_inact_ths_w       : 3;
  uint8_t xl_inact_odr         : 2;
  uint8_t inact_dur            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_inactivity_dur_t;

#define LSM6DSV16X_INACTIVITY_THS              0x55U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t inact_ths            : 6;
  uint8_t not_used0            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 2;
  uint8_t inact_ths            : 6;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_inactivity_ths_t;

#define LSM6DSV16X_TAP_CFG0                    0x56U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t lir                  : 1;
  uint8_t tap_z_en             : 1;
  uint8_t tap_y_en             : 1;
  uint8_t tap_x_en             : 1;
  uint8_t slope_fds            : 1;
  uint8_t hw_func_mask_xl_settl  : 1;
  uint8_t low_pass_on_6d       : 1;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t low_pass_on_6d       : 1;
  uint8_t hw_func_mask_xl_settl  : 1;
  uint8_t slope_fds            : 1;
  uint8_t tap_x_en             : 1;
  uint8_t tap_y_en             : 1;
  uint8_t tap_z_en             : 1;
  uint8_t lir                  : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_tap_cfg0_t;

#define LSM6DSV16X_TAP_CFG1                    0x57U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t tap_ths_x            : 5;
  uint8_t tap_priority         : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t tap_priority         : 3;
  uint8_t tap_ths_x            : 5;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_tap_cfg1_t;

#define LSM6DSV16X_TAP_CFG2                    0x58U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t tap_ths_y            : 5;
  uint8_t not_used0            : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t tap_ths_y            : 5;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_tap_cfg2_t;

#define LSM6DSV16X_TAP_THS_6D                  0x59U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t tap_ths_z            : 5;
  uint8_t sixd_ths             : 2;
  uint8_t d4d_en               : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t d4d_en               : 1;
  uint8_t sixd_ths             : 2;
  uint8_t tap_ths_z            : 5;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_tap_ths_6d_t;

#define LSM6DSV16X_TAP_DUR                     0x5AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t shock                : 2;
  uint8_t quiet                : 2;
  uint8_t dur                  : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t dur                  : 4;
  uint8_t quiet                : 2;
  uint8_t shock                : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_tap_dur_t;

#define LSM6DSV16X_WAKE_UP_THS                 0x5BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t wk_ths               : 6;
  uint8_t usr_off_on_wu        : 1;
  uint8_t single_double_tap    : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t single_double_tap    : 1;
  uint8_t usr_off_on_wu        : 1;
  uint8_t wk_ths               : 6;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_wake_up_ths_t;

#define LSM6DSV16X_WAKE_UP_DUR                 0x5CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sleep_dur            : 4;
  uint8_t not_used0            : 1;
  uint8_t wake_dur             : 2;
  uint8_t ff_dur               : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ff_dur               : 1;
  uint8_t wake_dur             : 2;
  uint8_t not_used0            : 1;
  uint8_t sleep_dur            : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_wake_up_dur_t;

#define LSM6DSV16X_FREE_FALL                   0x5DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ff_ths               : 3;
  uint8_t ff_dur               : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ff_dur               : 5;
  uint8_t ff_ths               : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_free_fall_t;

#define LSM6DSV16X_MD1_CFG                    0x5EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int1_shub            : 1;
  uint8_t int1_emb_func        : 1;
  uint8_t int1_6d              : 1;
  uint8_t int1_double_tap      : 1;
  uint8_t int1_ff              : 1;
  uint8_t int1_wu              : 1;
  uint8_t int1_single_tap      : 1;
  uint8_t int1_sleep_change    : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int1_sleep_change    : 1;
  uint8_t int1_single_tap      : 1;
  uint8_t int1_wu              : 1;
  uint8_t int1_ff              : 1;
  uint8_t int1_double_tap      : 1;
  uint8_t int1_6d              : 1;
  uint8_t int1_emb_func        : 1;
  uint8_t int1_shub            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_md1_cfg_t;

#define LSM6DSV16X_MD2_CFG                    0x5FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int2_timestamp       : 1;
  uint8_t int2_emb_func        : 1;
  uint8_t int2_6d              : 1;
  uint8_t int2_double_tap      : 1;
  uint8_t int2_ff              : 1;
  uint8_t int2_wu              : 1;
  uint8_t int2_single_tap      : 1;
  uint8_t int2_sleep_change    : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int2_sleep_change    : 1;
  uint8_t int2_single_tap      : 1;
  uint8_t int2_wu              : 1;
  uint8_t int2_ff              : 1;
  uint8_t int2_double_tap      : 1;
  uint8_t int2_6d              : 1;
  uint8_t int2_emb_func        : 1;
  uint8_t int2_timestamp       : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_md2_cfg_t;

#define LSM6DSV16X_HAODR_CFG                  0x62U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t haodr_sel            : 2;
  uint8_t not_used0            : 6;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 6;
  uint8_t haodr_sel            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_haodr_cfg_t;

#define LSM6DSV16X_EMB_FUNC_CFG               0x63U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0                  : 3;
  uint8_t emb_func_disable           : 1;
  uint8_t emb_func_irq_mask_xl_settl : 1;
  uint8_t emb_func_irq_mask_g_settl  : 1;
  uint8_t not_used1                  : 1;
  uint8_t xl_dualc_batch_from_if     : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t xl_dualc_batch_from_if     : 1;
  uint8_t not_used1                  : 1;
  uint8_t emb_func_irq_mask_g_settl  : 1;
  uint8_t emb_func_irq_mask_xl_settl : 1;
  uint8_t emb_func_disable           : 1;
  uint8_t not_used0                  : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_cfg_t;

#define LSM6DSV16X_UI_HANDSHAKE_CTRL          0x64U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_shared_req        : 1;
  uint8_t ui_shared_ack        : 1;
  uint8_t not_used0            : 6;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 6;
  uint8_t ui_shared_ack        : 1;
  uint8_t ui_shared_req        : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_handshake_ctrl_t;

#define LSM6DSV16X_UI_SPI2_SHARED_0           0x65U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_spi2_shared_0_t;

#define LSM6DSV16X_UI_SPI2_SHARED_1           0x66U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_spi2_shared_1_t;

#define LSM6DSV16X_UI_SPI2_SHARED_2           0x67U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_spi2_shared_2_t;

#define LSM6DSV16X_UI_SPI2_SHARED_3           0x68U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_spi2_shared_3_t;

#define LSM6DSV16X_UI_SPI2_SHARED_4           0x69U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_spi2_shared_4_t;

#define LSM6DSV16X_UI_SPI2_SHARED_5           0x6AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ui_spi2_shared       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_spi2_shared_5_t;

#define LSM6DSV16X_CTRL_EIS                   0x6BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_g_eis             : 3;
  uint8_t g_eis_on_g_ois_out_reg : 1;
  uint8_t lpf_g_eis_bw         : 1;
  uint8_t not_used0            : 1;
  uint8_t odr_g_eis            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t odr_g_eis            : 2;
  uint8_t not_used0            : 1;
  uint8_t lpf_g_eis_bw         : 1;
  uint8_t g_eis_on_g_ois_out_reg : 1;
  uint8_t fs_g_eis             : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ctrl_eis_t;

#define LSM6DSV16X_UI_INT_OIS                 0x6FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t st_ois_clampdis      : 1;
  uint8_t not_used1            : 1;
  uint8_t drdy_mask_ois        : 1;
  uint8_t int2_drdy_ois        : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int2_drdy_ois        : 1;
  uint8_t drdy_mask_ois        : 1;
  uint8_t not_used1            : 1;
  uint8_t st_ois_clampdis      : 1;
  uint8_t not_used0            : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_int_ois_t;

#define LSM6DSV16X_UI_CTRL1_OIS               0x70U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_read_en         : 1;
  uint8_t ois_g_en             : 1;
  uint8_t ois_xl_en            : 1;
  uint8_t not_used0            : 2;
  uint8_t sim_ois              : 1;
  uint8_t not_used1            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 2;
  uint8_t sim_ois              : 1;
  uint8_t not_used0            : 2;
  uint8_t ois_xl_en            : 1;
  uint8_t ois_g_en             : 1;
  uint8_t spi2_read_en         : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_ctrl1_ois_t;

#define LSM6DSV16X_UI_CTRL2_OIS               0x71U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_g_ois             : 3;
  uint8_t lpf1_g_ois_bw        : 2;
  uint8_t not_used0            : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t lpf1_g_ois_bw        : 2;
  uint8_t fs_g_ois             : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_ctrl2_ois_t;

#define LSM6DSV16X_UI_CTRL3_OIS               0x72U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_xl_ois            : 2;
  uint8_t not_used0            : 1;
  uint8_t lpf_xl_ois_bw        : 3;
  uint8_t not_used1            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 2;
  uint8_t lpf_xl_ois_bw        : 3;
  uint8_t not_used0            : 1;
  uint8_t fs_xl_ois            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ui_ctrl3_ois_t;

#define LSM6DSV16X_X_OFS_USR                  0x73U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t x_ofs_usr            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t x_ofs_usr            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_x_ofs_usr_t;

#define LSM6DSV16X_Y_OFS_USR                  0x74U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t y_ofs_usr            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t y_ofs_usr            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_y_ofs_usr_t;

#define LSM6DSV16X_Z_OFS_USR                  0x75U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t z_ofs_usr            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t z_ofs_usr            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_z_ofs_usr_t;

#define LSM6DSV16X_FIFO_DATA_OUT_TAG          0x78U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t tag_cnt              : 2;
  uint8_t tag_sensor           : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t tag_sensor           : 5;
  uint8_t tag_cnt              : 2;
  uint8_t not_used0            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_tag_t;

#define LSM6DSV16X_FIFO_DATA_OUT_X_L          0x79U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_data_out        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_data_out        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_x_l_t;

#define LSM6DSV16X_FIFO_DATA_OUT_X_H          0x7AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_data_out        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_data_out        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_x_h_t;

#define LSM6DSV16X_FIFO_DATA_OUT_Y_L          0x7BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_data_out        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_data_out        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_y_l_t;

#define LSM6DSV16X_FIFO_DATA_OUT_Y_H          0x7CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_data_out        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_data_out        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_y_h_t;

#define LSM6DSV16X_FIFO_DATA_OUT_Z_L          0x7DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_data_out        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_data_out        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_z_l_t;

#define LSM6DSV16X_FIFO_DATA_OUT_Z_H          0x7EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fifo_data_out        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fifo_data_out        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fifo_data_out_z_h_t;

/**
  * @}
  *
  */

/** @defgroup bitfields_page_if2 Bitfields Page if2
  * @{
  *
  */

#define LSM6DSV16X_SPI2_WHO_AM_I              0x0FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t id                   : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t id                   : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_who_am_i_t;

#define LSM6DSV16X_SPI2_STATUS_REG_OIS        0x1EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t xlda                 : 1;
  uint8_t gda                  : 1;
  uint8_t gyro_settling        : 1;
  uint8_t not_used0            : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 5;
  uint8_t gyro_settling        : 1;
  uint8_t gda                  : 1;
  uint8_t xlda                 : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_status_reg_ois_t;

#define LSM6DSV16X_SPI2_OUT_TEMP_L            0x20U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t temp                 : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t temp                 : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_out_temp_l_t;

#define LSM6DSV16X_SPI2_OUT_TEMP_H            0x21U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t temp                 : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t temp                 : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_out_temp_h_t;

#define LSM6DSV16X_SPI2_OUTX_L_G_OIS          0x22U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outx_g_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outx_g_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outx_l_g_ois_t;

#define LSM6DSV16X_SPI2_OUTX_H_G_OIS          0x23U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outx_g_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outx_g_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outx_h_g_ois_t;

#define LSM6DSV16X_SPI2_OUTY_L_G_OIS          0x24U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outy_g_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outy_g_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outy_l_g_ois_t;

#define LSM6DSV16X_SPI2_OUTY_H_G_OIS          0x25U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outy_g_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outy_g_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outy_h_g_ois_t;

#define LSM6DSV16X_SPI2_OUTZ_L_G_OIS          0x26U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outz_g_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outz_g_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outz_l_g_ois_t;

#define LSM6DSV16X_SPI2_OUTZ_H_G_OIS          0x27U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outz_g_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outz_g_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outz_h_g_ois_t;

#define LSM6DSV16X_SPI2_OUTX_L_A_OIS          0x28U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outx_a_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outx_a_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outx_l_a_ois_t;

#define LSM6DSV16X_SPI2_OUTX_H_A_OIS          0x29U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outx_a_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outx_a_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outx_h_a_ois_t;

#define LSM6DSV16X_SPI2_OUTY_L_A_OIS          0x2AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outy_a_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outy_a_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outy_l_a_ois_t;

#define LSM6DSV16X_SPI2_OUTY_H_A_OIS          0x2BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outy_a_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outy_a_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outy_h_a_ois_t;

#define LSM6DSV16X_SPI2_OUTZ_L_A_OIS          0x2CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outz_a_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outz_a_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outz_l_a_ois_t;

#define LSM6DSV16X_SPI2_OUTZ_H_A_OIS          0x2DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_outz_a_ois      : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t spi2_outz_a_ois      : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_outz_h_a_ois_t;

#define LSM6DSV16X_SPI2_HANDSHAKE_CTRL        0x6EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_shared_ack      : 1;
  uint8_t spi2_shared_req      : 1;
  uint8_t not_used0            : 6;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 6;
  uint8_t spi2_shared_req      : 1;
  uint8_t spi2_shared_ack      : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_handshake_ctrl_t;

#define LSM6DSV16X_SPI2_INT_OIS               0x6FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t st_xl_ois            : 2;
  uint8_t st_g_ois             : 2;
  uint8_t st_ois_clampdis      : 1;
  uint8_t not_used0            : 1;
  uint8_t drdy_mask_ois        : 1;
  uint8_t int2_drdy_ois        : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int2_drdy_ois        : 1;
  uint8_t drdy_mask_ois        : 1;
  uint8_t not_used0            : 1;
  uint8_t st_ois_clampdis      : 1;
  uint8_t st_g_ois             : 2;
  uint8_t st_xl_ois            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_int_ois_t;

#define LSM6DSV16X_SPI2_CTRL1_OIS             0x70U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t spi2_read_en         : 1;
  uint8_t ois_g_en             : 1;
  uint8_t ois_xl_en            : 1;
  uint8_t not_used0            : 2;
  uint8_t sim_ois              : 1;
  uint8_t not_used1            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 2;
  uint8_t sim_ois              : 1;
  uint8_t not_used0            : 2;
  uint8_t ois_xl_en            : 1;
  uint8_t ois_g_en             : 1;
  uint8_t spi2_read_en         : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_ctrl1_ois_t;

#define LSM6DSV16X_SPI2_CTRL2_OIS             0x71U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_g_ois             : 3;
  uint8_t lpf1_g_ois_bw        : 2;
  uint8_t not_used0            : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t lpf1_g_ois_bw        : 2;
  uint8_t fs_g_ois             : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_ctrl2_ois_t;

#define LSM6DSV16X_SPI2_CTRL3_OIS             0x72U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fs_xl_ois            : 2;
  uint8_t not_used0            : 1;
  uint8_t lpf_xl_ois_bw        : 3;
  uint8_t not_used1            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 2;
  uint8_t lpf_xl_ois_bw        : 3;
  uint8_t not_used0            : 1;
  uint8_t fs_xl_ois            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_spi2_ctrl3_ois_t;

/**
  * @}
  *
  */

/** @defgroup bitfields_page_embedded Bitfields Page Embedded
  * @{
  *
  */

#define LSM6DSV16X_PAGE_SEL                   0x2U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t page_sel             : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t page_sel             : 4;
  uint8_t not_used0            : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_page_sel_t;

#define LSM6DSV16X_EMB_FUNC_EN_A              0x4U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t sflp_game_en         : 1;
  uint8_t not_used2            : 1;
  uint8_t pedo_en              : 1;
  uint8_t tilt_en              : 1;
  uint8_t sign_motion_en       : 1;
  uint8_t not_used1            : 1;
  uint8_t mlc_before_fsm_en    : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc_before_fsm_en    : 1;
  uint8_t not_used1            : 1;
  uint8_t sign_motion_en       : 1;
  uint8_t tilt_en              : 1;
  uint8_t pedo_en              : 1;
  uint8_t not_used2            : 1;
  uint8_t sflp_game_en         : 1;
  uint8_t not_used0            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_en_a_t;

#define LSM6DSV16X_EMB_FUNC_EN_B              0x5U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_en               : 1;
  uint8_t not_used0            : 2;
  uint8_t fifo_compr_en        : 1;
  uint8_t mlc_en               : 1;
  uint8_t not_used1            : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 3;
  uint8_t mlc_en               : 1;
  uint8_t fifo_compr_en        : 1;
  uint8_t not_used0            : 2;
  uint8_t fsm_en               : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_en_b_t;

#define LSM6DSV16X_EMB_FUNC_EXEC_STATUS       0x7U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t emb_func_endop       : 1;
  uint8_t emb_func_exec_ovr    : 1;
  uint8_t not_used0            : 6;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 6;
  uint8_t emb_func_exec_ovr    : 1;
  uint8_t emb_func_endop       : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_exec_status_t;

#define LSM6DSV16X_PAGE_ADDRESS               0x8U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t page_addr            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t page_addr            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_page_address_t;

#define LSM6DSV16X_PAGE_VALUE                 0x9U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t page_value           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t page_value           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_page_value_t;

#define LSM6DSV16X_EMB_FUNC_INT1              0x0AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t int1_step_detector   : 1;
  uint8_t int1_tilt            : 1;
  uint8_t int1_sig_mot         : 1;
  uint8_t not_used1            : 1;
  uint8_t int1_fsm_lc          : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int1_fsm_lc          : 1;
  uint8_t not_used1            : 1;
  uint8_t int1_sig_mot         : 1;
  uint8_t int1_tilt            : 1;
  uint8_t int1_step_detector   : 1;
  uint8_t not_used0            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_int1_t;

#define LSM6DSV16X_FSM_INT1                   0x0BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int1_fsm1            : 1;
  uint8_t int1_fsm2            : 1;
  uint8_t int1_fsm3            : 1;
  uint8_t int1_fsm4            : 1;
  uint8_t int1_fsm5            : 1;
  uint8_t int1_fsm6            : 1;
  uint8_t int1_fsm7            : 1;
  uint8_t int1_fsm8            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int1_fsm8            : 1;
  uint8_t int1_fsm7            : 1;
  uint8_t int1_fsm6            : 1;
  uint8_t int1_fsm5            : 1;
  uint8_t int1_fsm4            : 1;
  uint8_t int1_fsm3            : 1;
  uint8_t int1_fsm2            : 1;
  uint8_t int1_fsm1            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_int1_t;

#define LSM6DSV16X_MLC_INT1                   0x0DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int1_mlc1            : 1;
  uint8_t int1_mlc2            : 1;
  uint8_t int1_mlc3            : 1;
  uint8_t int1_mlc4            : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t int1_mlc4            : 1;
  uint8_t int1_mlc3            : 1;
  uint8_t int1_mlc2            : 1;
  uint8_t int1_mlc1            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_int1_t;

#define LSM6DSV16X_EMB_FUNC_INT2              0x0EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t int2_step_detector   : 1;
  uint8_t int2_tilt            : 1;
  uint8_t int2_sig_mot         : 1;
  uint8_t not_used1            : 1;
  uint8_t int2_fsm_lc          : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int2_fsm_lc          : 1;
  uint8_t not_used1            : 1;
  uint8_t int2_sig_mot         : 1;
  uint8_t int2_tilt            : 1;
  uint8_t int2_step_detector   : 1;
  uint8_t not_used0            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_int2_t;

#define LSM6DSV16X_FSM_INT2                   0x0FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int2_fsm1            : 1;
  uint8_t int2_fsm2            : 1;
  uint8_t int2_fsm3            : 1;
  uint8_t int2_fsm4            : 1;
  uint8_t int2_fsm5            : 1;
  uint8_t int2_fsm6            : 1;
  uint8_t int2_fsm7            : 1;
  uint8_t int2_fsm8            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t int2_fsm8            : 1;
  uint8_t int2_fsm7            : 1;
  uint8_t int2_fsm6            : 1;
  uint8_t int2_fsm5            : 1;
  uint8_t int2_fsm4            : 1;
  uint8_t int2_fsm3            : 1;
  uint8_t int2_fsm2            : 1;
  uint8_t int2_fsm1            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_int2_t;

#define LSM6DSV16X_MLC_INT2                   0x11U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t int2_mlc1            : 1;
  uint8_t int2_mlc2            : 1;
  uint8_t int2_mlc3            : 1;
  uint8_t int2_mlc4            : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t int2_mlc4            : 1;
  uint8_t int2_mlc3            : 1;
  uint8_t int2_mlc2            : 1;
  uint8_t int2_mlc1            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_int2_t;

#define LSM6DSV16X_EMB_FUNC_STATUS            0x12U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t is_step_det          : 1;
  uint8_t is_tilt              : 1;
  uint8_t is_sigmot            : 1;
  uint8_t not_used1            : 1;
  uint8_t is_fsm_lc            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t is_fsm_lc            : 1;
  uint8_t not_used1            : 1;
  uint8_t is_sigmot            : 1;
  uint8_t is_tilt              : 1;
  uint8_t is_step_det          : 1;
  uint8_t not_used0            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_status_t;

#define LSM6DSV16X_FSM_STATUS                 0x13U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t is_fsm1              : 1;
  uint8_t is_fsm2              : 1;
  uint8_t is_fsm3              : 1;
  uint8_t is_fsm4              : 1;
  uint8_t is_fsm5              : 1;
  uint8_t is_fsm6              : 1;
  uint8_t is_fsm7              : 1;
  uint8_t is_fsm8              : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t is_fsm8              : 1;
  uint8_t is_fsm7              : 1;
  uint8_t is_fsm6              : 1;
  uint8_t is_fsm5              : 1;
  uint8_t is_fsm4              : 1;
  uint8_t is_fsm3              : 1;
  uint8_t is_fsm2              : 1;
  uint8_t is_fsm1              : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_status_t;

#define LSM6DSV16X_MLC_STATUS                 0x15U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t is_mlc1              : 1;
  uint8_t is_mlc2              : 1;
  uint8_t is_mlc3              : 1;
  uint8_t is_mlc4              : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t is_mlc4              : 1;
  uint8_t is_mlc3              : 1;
  uint8_t is_mlc2              : 1;
  uint8_t is_mlc1              : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_status_t;

#define LSM6DSV16X_PAGE_RW                    0x17U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 5;
  uint8_t page_read            : 1;
  uint8_t page_write           : 1;
  uint8_t emb_func_lir         : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t emb_func_lir         : 1;
  uint8_t page_write           : 1;
  uint8_t page_read            : 1;
  uint8_t not_used0            : 5;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_page_rw_t;

#define LSM6DSV16X_EMB_FUNC_FIFO_EN_A         0x44U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t sflp_game_fifo_en    : 1;
  uint8_t not_used1            : 2;
  uint8_t sflp_gravity_fifo_en : 1;
  uint8_t sflp_gbias_fifo_en   : 1;
  uint8_t step_counter_fifo_en : 1;
  uint8_t mlc_fifo_en          : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc_fifo_en          : 1;
  uint8_t step_counter_fifo_en : 1;
  uint8_t sflp_gbias_fifo_en   : 1;
  uint8_t sflp_gravity_fifo_en : 1;
  uint8_t not_used1            : 2;
  uint8_t sflp_game_fifo_en    : 1;
  uint8_t not_used0            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_fifo_en_a_t;

#define LSM6DSV16X_EMB_FUNC_FIFO_EN_B         0x45U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0                     : 1;
  uint8_t mlc_filter_feature_fifo_en    : 1;
  uint8_t not_used1                     : 6;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1                     : 6;
  uint8_t mlc_filter_feature_fifo_en    : 1;
  uint8_t not_used0                     : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_fifo_en_b_t;

#define LSM6DSV16X_FSM_ENABLE                 0x46U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm1_en              : 1;
  uint8_t fsm2_en              : 1;
  uint8_t fsm3_en              : 1;
  uint8_t fsm4_en              : 1;
  uint8_t fsm5_en              : 1;
  uint8_t fsm6_en              : 1;
  uint8_t fsm7_en              : 1;
  uint8_t fsm8_en              : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm8_en              : 1;
  uint8_t fsm7_en              : 1;
  uint8_t fsm6_en              : 1;
  uint8_t fsm5_en              : 1;
  uint8_t fsm4_en              : 1;
  uint8_t fsm3_en              : 1;
  uint8_t fsm2_en              : 1;
  uint8_t fsm1_en              : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_enable_t;

#define LSM6DSV16X_FSM_LONG_COUNTER_L         0x48U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_lc               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_lc               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_long_counter_l_t;

#define LSM6DSV16X_FSM_LONG_COUNTER_H         0x49U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_lc               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_lc               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_long_counter_h_t;

#define LSM6DSV16X_INT_ACK_MASK               0x4BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t iack_mask            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t iack_mask            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_int_ack_mask_t;

#define LSM6DSV16X_FSM_OUTS1                  0x4CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm1_n_v             : 1;
  uint8_t fsm1_p_v             : 1;
  uint8_t fsm1_n_z             : 1;
  uint8_t fsm1_p_z             : 1;
  uint8_t fsm1_n_y             : 1;
  uint8_t fsm1_p_y             : 1;
  uint8_t fsm1_n_x             : 1;
  uint8_t fsm1_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm1_p_x             : 1;
  uint8_t fsm1_n_x             : 1;
  uint8_t fsm1_p_y             : 1;
  uint8_t fsm1_n_y             : 1;
  uint8_t fsm1_p_z             : 1;
  uint8_t fsm1_n_z             : 1;
  uint8_t fsm1_p_v             : 1;
  uint8_t fsm1_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs1_t;

#define LSM6DSV16X_FSM_OUTS2                  0x4DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm2_n_v             : 1;
  uint8_t fsm2_p_v             : 1;
  uint8_t fsm2_n_z             : 1;
  uint8_t fsm2_p_z             : 1;
  uint8_t fsm2_n_y             : 1;
  uint8_t fsm2_p_y             : 1;
  uint8_t fsm2_n_x             : 1;
  uint8_t fsm2_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm2_p_x             : 1;
  uint8_t fsm2_n_x             : 1;
  uint8_t fsm2_p_y             : 1;
  uint8_t fsm2_n_y             : 1;
  uint8_t fsm2_p_z             : 1;
  uint8_t fsm2_n_z             : 1;
  uint8_t fsm2_p_v             : 1;
  uint8_t fsm2_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs2_t;

#define LSM6DSV16X_FSM_OUTS3                  0x4EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm3_n_v             : 1;
  uint8_t fsm3_p_v             : 1;
  uint8_t fsm3_n_z             : 1;
  uint8_t fsm3_p_z             : 1;
  uint8_t fsm3_n_y             : 1;
  uint8_t fsm3_p_y             : 1;
  uint8_t fsm3_n_x             : 1;
  uint8_t fsm3_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm3_p_x             : 1;
  uint8_t fsm3_n_x             : 1;
  uint8_t fsm3_p_y             : 1;
  uint8_t fsm3_n_y             : 1;
  uint8_t fsm3_p_z             : 1;
  uint8_t fsm3_n_z             : 1;
  uint8_t fsm3_p_v             : 1;
  uint8_t fsm3_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs3_t;

#define LSM6DSV16X_FSM_OUTS4                  0x4FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm4_n_v             : 1;
  uint8_t fsm4_p_v             : 1;
  uint8_t fsm4_n_z             : 1;
  uint8_t fsm4_p_z             : 1;
  uint8_t fsm4_n_y             : 1;
  uint8_t fsm4_p_y             : 1;
  uint8_t fsm4_n_x             : 1;
  uint8_t fsm4_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm4_p_x             : 1;
  uint8_t fsm4_n_x             : 1;
  uint8_t fsm4_p_y             : 1;
  uint8_t fsm4_n_y             : 1;
  uint8_t fsm4_p_z             : 1;
  uint8_t fsm4_n_z             : 1;
  uint8_t fsm4_p_v             : 1;
  uint8_t fsm4_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs4_t;

#define LSM6DSV16X_FSM_OUTS5                  0x50U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm5_n_v             : 1;
  uint8_t fsm5_p_v             : 1;
  uint8_t fsm5_n_z             : 1;
  uint8_t fsm5_p_z             : 1;
  uint8_t fsm5_n_y             : 1;
  uint8_t fsm5_p_y             : 1;
  uint8_t fsm5_n_x             : 1;
  uint8_t fsm5_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm5_p_x             : 1;
  uint8_t fsm5_n_x             : 1;
  uint8_t fsm5_p_y             : 1;
  uint8_t fsm5_n_y             : 1;
  uint8_t fsm5_p_z             : 1;
  uint8_t fsm5_n_z             : 1;
  uint8_t fsm5_p_v             : 1;
  uint8_t fsm5_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs5_t;

#define LSM6DSV16X_FSM_OUTS6                  0x51U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm6_n_v             : 1;
  uint8_t fsm6_p_v             : 1;
  uint8_t fsm6_n_z             : 1;
  uint8_t fsm6_p_z             : 1;
  uint8_t fsm6_n_y             : 1;
  uint8_t fsm6_p_y             : 1;
  uint8_t fsm6_n_x             : 1;
  uint8_t fsm6_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm6_p_x             : 1;
  uint8_t fsm6_n_x             : 1;
  uint8_t fsm6_p_y             : 1;
  uint8_t fsm6_n_y             : 1;
  uint8_t fsm6_p_z             : 1;
  uint8_t fsm6_n_z             : 1;
  uint8_t fsm6_p_v             : 1;
  uint8_t fsm6_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs6_t;

#define LSM6DSV16X_FSM_OUTS7                  0x52U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm7_n_v             : 1;
  uint8_t fsm7_p_v             : 1;
  uint8_t fsm7_n_z             : 1;
  uint8_t fsm7_p_z             : 1;
  uint8_t fsm7_n_y             : 1;
  uint8_t fsm7_p_y             : 1;
  uint8_t fsm7_n_x             : 1;
  uint8_t fsm7_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm7_p_x             : 1;
  uint8_t fsm7_n_x             : 1;
  uint8_t fsm7_p_y             : 1;
  uint8_t fsm7_n_y             : 1;
  uint8_t fsm7_p_z             : 1;
  uint8_t fsm7_n_z             : 1;
  uint8_t fsm7_p_v             : 1;
  uint8_t fsm7_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs7_t;

#define LSM6DSV16X_FSM_OUTS8                  0x53U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm8_n_v             : 1;
  uint8_t fsm8_p_v             : 1;
  uint8_t fsm8_n_z             : 1;
  uint8_t fsm8_p_z             : 1;
  uint8_t fsm8_n_y             : 1;
  uint8_t fsm8_p_y             : 1;
  uint8_t fsm8_n_x             : 1;
  uint8_t fsm8_p_x             : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm8_p_x             : 1;
  uint8_t fsm8_n_x             : 1;
  uint8_t fsm8_p_y             : 1;
  uint8_t fsm8_n_y             : 1;
  uint8_t fsm8_p_z             : 1;
  uint8_t fsm8_n_z             : 1;
  uint8_t fsm8_p_v             : 1;
  uint8_t fsm8_n_v             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_outs8_t;

#define LSM6DSV16X_SFLP_ODR                   0x5EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t sflp_game_odr        : 3;
  uint8_t not_used1            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 2;
  uint8_t sflp_game_odr        : 3;
  uint8_t not_used0            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_odr_t;

#define LSM6DSV16X_FSM_ODR                    0x5FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 3;
  uint8_t fsm_odr              : 3;
  uint8_t not_used1            : 2;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 2;
  uint8_t fsm_odr              : 3;
  uint8_t not_used0            : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_odr_t;

#define LSM6DSV16X_MLC_ODR                    0x60U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t mlc_odr              : 3;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t mlc_odr              : 3;
  uint8_t not_used0            : 4;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_odr_t;

#define LSM6DSV16X_STEP_COUNTER_L             0x62U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t step                 : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t step                 : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_step_counter_l_t;

#define LSM6DSV16X_STEP_COUNTER_H             0x63U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t step                 : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t step                 : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_step_counter_h_t;

#define LSM6DSV16X_EMB_FUNC_SRC               0x64U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 2;
  uint8_t stepcounter_bit_set  : 1;
  uint8_t step_overflow        : 1;
  uint8_t step_count_delta_ia  : 1;
  uint8_t step_detected        : 1;
  uint8_t not_used1            : 1;
  uint8_t pedo_rst_step        : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t pedo_rst_step        : 1;
  uint8_t not_used1            : 1;
  uint8_t step_detected        : 1;
  uint8_t step_count_delta_ia  : 1;
  uint8_t step_overflow        : 1;
  uint8_t stepcounter_bit_set  : 1;
  uint8_t not_used0            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_src_t;

#define LSM6DSV16X_EMB_FUNC_INIT_A            0x66U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t sflp_game_init       : 1;
  uint8_t not_used2            : 1;
  uint8_t step_det_init        : 1;
  uint8_t tilt_init            : 1;
  uint8_t sig_mot_init         : 1;
  uint8_t not_used1            : 1;
  uint8_t mlc_before_fsm_init  : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc_before_fsm_init  : 1;
  uint8_t not_used1            : 1;
  uint8_t sig_mot_init         : 1;
  uint8_t tilt_init            : 1;
  uint8_t step_det_init        : 1;
  uint8_t not_used2            : 1;
  uint8_t sflp_game_init       : 1;
  uint8_t not_used0            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_init_a_t;

#define LSM6DSV16X_EMB_FUNC_INIT_B            0x67U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_init             : 1;
  uint8_t not_used0            : 2;
  uint8_t fifo_compr_init      : 1;
  uint8_t mlc_init             : 1;
  uint8_t not_used1            : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 3;
  uint8_t mlc_init             : 1;
  uint8_t fifo_compr_init      : 1;
  uint8_t not_used0            : 2;
  uint8_t fsm_init             : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_emb_func_init_b_t;

#define LSM6DSV16X_MLC1_SRC                   0x70U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t mlc1_src             : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc1_src             : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc1_src_t;

#define LSM6DSV16X_MLC2_SRC                   0x71U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t mlc2_src             : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc2_src             : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc2_src_t;

#define LSM6DSV16X_MLC3_SRC                   0x72U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t mlc3_src             : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc3_src             : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc3_src_t;

#define LSM6DSV16X_MLC4_SRC                   0x73U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t mlc4_src             : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc4_src             : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc4_src_t;

/**
  * @}
  *
  */

/** @defgroup bitfields_page_pg0_emb_adv Bitfields Page pg0_emb_adv
  * @{
  *
  */
#define LSM6DSV16X_EMB_ADV_PG_0              0x000U

#define LSM6DSV16X_SFLP_GAME_GBIASX_L        0x6EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t gbiasx               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t gbiasx               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_game_gbiasx_l_t;

#define LSM6DSV16X_SFLP_GAME_GBIASX_H        0x6FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t gbiasx               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t gbiasx               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_game_gbiasx_h_t;

#define LSM6DSV16X_SFLP_GAME_GBIASY_L        0x70U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t gbiasy               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t gbiasy               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_game_gbiasy_l_t;

#define LSM6DSV16X_SFLP_GAME_GBIASY_H        0x71U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t gbiasy               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t gbiasy               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_game_gbiasy_h_t;

#define LSM6DSV16X_SFLP_GAME_GBIASZ_L        0x72U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t gbiasz               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t gbiasz               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_game_gbiasz_l_t;

#define LSM6DSV16X_SFLP_GAME_GBIASZ_H        0x73U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t gbiasz               : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t gbiasz               : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sflp_game_gbiasz_h_t;

#define LSM6DSV16X_FSM_EXT_SENSITIVITY_L     0xBAU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_s            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_s            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_sensitivity_l_t;

#define LSM6DSV16X_FSM_EXT_SENSITIVITY_H     0xBBU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_s            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_s            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_sensitivity_h_t;

#define LSM6DSV16X_FSM_EXT_OFFX_L            0xC0U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_offx         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_offx         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_offx_l_t;

#define LSM6DSV16X_FSM_EXT_OFFX_H            0xC1U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_offx         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_offx         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_offx_h_t;

#define LSM6DSV16X_FSM_EXT_OFFY_L            0xC2U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_offy         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_offy         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_offy_l_t;

#define LSM6DSV16X_FSM_EXT_OFFY_H            0xC3U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_offy         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_offy         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_offy_h_t;

#define LSM6DSV16X_FSM_EXT_OFFZ_L            0xC4U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_offz         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_offz         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_offz_l_t;

#define LSM6DSV16X_FSM_EXT_OFFZ_H            0xC5U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_offz         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_offz         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_offz_h_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_XX_L       0xC6U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_xx       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_xx       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_xx_l_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_XX_H       0xC7U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_xx       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_xx       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_xx_h_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_XY_L       0xC8U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_xy       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_xy       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_xy_l_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_XY_H       0xC9U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_xy       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_xy       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_xy_h_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_XZ_L       0xCAU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_xz       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_xz       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_xz_l_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_XZ_H       0xCBU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_xz       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_xz       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_xz_h_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_YY_L       0xCCU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_yy       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_yy       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_yy_l_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_YY_H       0xCDU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_yy       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_yy       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_yy_h_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_YZ_L       0xCEU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_yz       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_yz       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_yz_l_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_YZ_H       0xCFU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_yz       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_yz       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_yz_h_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_ZZ_L       0xD0U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_zz       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_zz       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_zz_l_t;

#define LSM6DSV16X_FSM_EXT_MATRIX_ZZ_H       0xD1U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_ext_mat_zz       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_ext_mat_zz       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_ext_matrix_zz_h_t;

#define LSM6DSV16X_EXT_CFG_A                 0xD4U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_z_axis           : 3;
  uint8_t not_used0            : 1;
  uint8_t ext_y_axis           : 3;
  uint8_t not_used1            : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 1;
  uint8_t ext_y_axis           : 3;
  uint8_t not_used0            : 1;
  uint8_t ext_z_axis           : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_cfg_a_t;

#define LSM6DSV16X_EXT_CFG_B                 0xD5U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_x_axis           : 3;
  uint8_t not_used0            : 5;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 5;
  uint8_t ext_x_axis           : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_cfg_b_t;

/**
  * @}
  *
  */

/** @defgroup bitfields_page_pg1_emb_adv Bitfields Page pg1_emb_adv
  * @{
  *
  */
#define LSM6DSV16X_EMB_ADV_PG_1             0x100U

#define LSM6DSV16X_FSM_LC_TIMEOUT_L         0x7AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_lc_timeout       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_lc_timeout       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_lc_timeout_l_t;

#define LSM6DSV16X_FSM_LC_TIMEOUT_H         0x7BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_lc_timeout       : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_lc_timeout       : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_lc_timeout_h_t;

#define LSM6DSV16X_FSM_PROGRAMS             0x7CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_n_prog           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_n_prog           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_programs_t;

#define LSM6DSV16X_FSM_START_ADD_L          0x7EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_start            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_start            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_start_add_l_t;

#define LSM6DSV16X_FSM_START_ADD_H          0x7FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t fsm_start            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t fsm_start            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_fsm_start_add_h_t;

#define LSM6DSV16X_PEDO_CMD_REG             0x83U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 2;
  uint8_t fp_rejection_en      : 1;
  uint8_t carry_count_en       : 1;
  uint8_t not_used1            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 4;
  uint8_t carry_count_en       : 1;
  uint8_t fp_rejection_en      : 1;
  uint8_t not_used0            : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_pedo_cmd_reg_t;

#define LSM6DSV16X_PEDO_DEB_STEPS_CONF      0x84U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t deb_step             : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t deb_step             : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_pedo_deb_steps_conf_t;

#define LSM6DSV16X_PEDO_SC_DELTAT_L         0xD0U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t pd_sc                : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t pd_sc                : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_pedo_sc_deltat_l_t;

#define LSM6DSV16X_PEDO_SC_DELTAT_H         0xD1U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t pd_sc                : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t pd_sc                : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_pedo_sc_deltat_h_t;

#define LSM6DSV16X_MLC_EXT_SENSITIVITY_L    0xE8U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t mlc_ext_s            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc_ext_s            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_ext_sensitivity_l_t;

#define LSM6DSV16X_MLC_EXT_SENSITIVITY_H    0xE9U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t mlc_ext_s            : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t mlc_ext_s            : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_mlc_ext_sensitivity_h_t;

/** @defgroup bitfields_page_pg2_emb_adv Bitfields Page pg2_emb_adv
  * @{
  *
  */
#define LSM6DSV16X_EMB_ADV_PG_2             0x200U

#define LSM6DSV16X_EXT_FORMAT               0x00
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t not_used0            : 1;
  uint8_t ext_format_sel       : 1;
  uint8_t not_used1            : 6;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used1            : 6;
  uint8_t ext_format_sel       : 1;
  uint8_t not_used0            : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_format_t;

#define LSM6DSV16X_EXT_3BYTE_SENSITIVITY_L  0x02U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_3byte_s          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ext_3byte_s          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_3byte_sensitivity_l_t;

#define LSM6DSV16X_EXT_3BYTE_SENSITIVITY_H  0x03U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_3byte_s          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ext_3byte_s          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_3byte_sensitivity_h_t;

#define LSM6DSV16X_EXT_3BYTE_OFFSET_XL      0x06U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_3byte_off        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ext_3byte_off        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_3byte_offset_xl_t;

#define LSM6DSV16X_EXT_3BYTE_OFFSET_L       0x07U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_3byte_off        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ext_3byte_off        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_3byte_offset_l_t;

#define LSM6DSV16X_EXT_3BYTE_OFFSET_H       0x08U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t ext_3byte_off        : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t ext_3byte_off        : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_ext_3byte_offset_h_t;

/**
  * @}
  *
  */

/** @defgroup bitfields_page_sensor_hub Bitfields Page sensor_hub
  * @{
  *
  */

#define LSM6DSV16X_SENSOR_HUB_1             0x2U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub1           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub1           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_1_t;

#define LSM6DSV16X_SENSOR_HUB_2             0x3U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub2           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub2           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_2_t;

#define LSM6DSV16X_SENSOR_HUB_3             0x4U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub3           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub3           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_3_t;

#define LSM6DSV16X_SENSOR_HUB_4             0x5U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub4           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub4           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_4_t;

#define LSM6DSV16X_SENSOR_HUB_5             0x6U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub5           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub5           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_5_t;

#define LSM6DSV16X_SENSOR_HUB_6             0x7U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub6           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub6           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_6_t;

#define LSM6DSV16X_SENSOR_HUB_7             0x8U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub7           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub7           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_7_t;

#define LSM6DSV16X_SENSOR_HUB_8             0x9U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub8           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub8           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_8_t;

#define LSM6DSV16X_SENSOR_HUB_9             0x0AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub9           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub9           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_9_t;

#define LSM6DSV16X_SENSOR_HUB_10            0x0BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub10          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub10          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_10_t;

#define LSM6DSV16X_SENSOR_HUB_11            0x0CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub11          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub11          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_11_t;

#define LSM6DSV16X_SENSOR_HUB_12            0x0DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub12          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub12          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_12_t;

#define LSM6DSV16X_SENSOR_HUB_13            0x0EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub13          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub13          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_13_t;

#define LSM6DSV16X_SENSOR_HUB_14            0x0FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub14          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub14          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_14_t;

#define LSM6DSV16X_SENSOR_HUB_15            0x10U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub15          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub15          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_15_t;

#define LSM6DSV16X_SENSOR_HUB_16            0x11U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub16          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub16          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_16_t;

#define LSM6DSV16X_SENSOR_HUB_17            0x12U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub17          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub17          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_17_t;

#define LSM6DSV16X_SENSOR_HUB_18            0x13U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sensorhub18          : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t sensorhub18          : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_sensor_hub_18_t;

#define LSM6DSV16X_MASTER_CONFIG            0x14U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t aux_sens_on          : 2;
  uint8_t master_on            : 1;
  uint8_t not_used0            : 1;
  uint8_t pass_through_mode    : 1;
  uint8_t start_config         : 1;
  uint8_t write_once           : 1;
  uint8_t rst_master_regs      : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t rst_master_regs      : 1;
  uint8_t write_once           : 1;
  uint8_t start_config         : 1;
  uint8_t pass_through_mode    : 1;
  uint8_t not_used0            : 1;
  uint8_t master_on            : 1;
  uint8_t aux_sens_on          : 2;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_master_config_t;

#define LSM6DSV16X_SLV0_ADD                 0x15U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t rw_0                 : 1;
  uint8_t slave0_add           : 7;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave0_add           : 7;
  uint8_t rw_0                 : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv0_add_t;

#define LSM6DSV16X_SLV0_SUBADD              0x16U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave0_reg           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave0_reg           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv0_subadd_t;

#define LSM6DSV16X_SLV0_CONFIG              0x17U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave0_numop         : 3;
  uint8_t batch_ext_sens_0_en  : 1;
  uint8_t not_used0            : 1;
  uint8_t shub_odr             : 3;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t shub_odr             : 3;
  uint8_t not_used0            : 1;
  uint8_t batch_ext_sens_0_en  : 1;
  uint8_t slave0_numop         : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv0_config_t;

#define LSM6DSV16X_SLV1_ADD                 0x18U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t r_1                  : 1;
  uint8_t slave1_add           : 7;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave1_add           : 7;
  uint8_t r_1                  : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv1_add_t;

#define LSM6DSV16X_SLV1_SUBADD              0x19U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave1_reg           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave1_reg           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv1_subadd_t;

#define LSM6DSV16X_SLV1_CONFIG              0x1AU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave1_numop         : 3;
  uint8_t batch_ext_sens_1_en  : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t batch_ext_sens_1_en  : 1;
  uint8_t slave1_numop         : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv1_config_t;

#define LSM6DSV16X_SLV2_ADD                 0x1BU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t r_2                  : 1;
  uint8_t slave2_add           : 7;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave2_add           : 7;
  uint8_t r_2                  : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv2_add_t;

#define LSM6DSV16X_SLV2_SUBADD              0x1CU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave2_reg           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave2_reg           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv2_subadd_t;

#define LSM6DSV16X_SLV2_CONFIG              0x1DU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave2_numop         : 3;
  uint8_t batch_ext_sens_2_en  : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t batch_ext_sens_2_en  : 1;
  uint8_t slave2_numop         : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv2_config_t;

#define LSM6DSV16X_SLV3_ADD                 0x1EU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t r_3                  : 1;
  uint8_t slave3_add           : 7;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave3_add           : 7;
  uint8_t r_3                  : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv3_add_t;

#define LSM6DSV16X_SLV3_SUBADD              0x1FU
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave3_reg           : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave3_reg           : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv3_subadd_t;

#define LSM6DSV16X_SLV3_CONFIG              0x20U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave3_numop         : 3;
  uint8_t batch_ext_sens_3_en  : 1;
  uint8_t not_used0            : 4;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t not_used0            : 4;
  uint8_t batch_ext_sens_3_en  : 1;
  uint8_t slave3_numop         : 3;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_slv3_config_t;

#define LSM6DSV16X_DATAWRITE_SLV0           0x21U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t slave0_dataw         : 8;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t slave0_dataw         : 8;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_datawrite_slv0_t;

#define LSM6DSV16X_STATUS_MASTER            0x22U
typedef struct
{
#if DRV_BYTE_ORDER == DRV_LITTLE_ENDIAN
  uint8_t sens_hub_endop       : 1;
  uint8_t not_used0            : 2;
  uint8_t slave0_nack          : 1;
  uint8_t slave1_nack          : 1;
  uint8_t slave2_nack          : 1;
  uint8_t slave3_nack          : 1;
  uint8_t wr_once_done         : 1;
#elif DRV_BYTE_ORDER == DRV_BIG_ENDIAN
  uint8_t wr_once_done         : 1;
  uint8_t slave3_nack          : 1;
  uint8_t slave2_nack          : 1;
  uint8_t slave1_nack          : 1;
  uint8_t slave0_nack          : 1;
  uint8_t not_used0            : 2;
  uint8_t sens_hub_endop       : 1;
#endif /* DRV_BYTE_ORDER */
} lsm6dsv16x_status_master_t;

/**
  * @}
  *
  */

/**
  * @defgroup LSM6DSV_Register_Union Register Union
  * @brief    This union group all the registers having a bit-field
  *           description.
  *           This union is useful but it's not needed by the driver.
  *
  *           REMOVING this union you are compliant with:
  *           MISRA-C 2012 [Rule 19.2] -> " Union are not allowed "
  *
  * @{
  *
  */
typedef union
{
  lsm6dsv16x_func_cfg_access_t          func_cfg_access;
  lsm6dsv16x_pin_ctrl_t                 pin_ctrl;
  lsm6dsv16x_if_cfg_t                   if_cfg;
  lsm6dsv16x_odr_trig_cfg_t             odr_trig_cfg;
  lsm6dsv16x_fifo_ctrl1_t               fifo_ctrl1;
  lsm6dsv16x_fifo_ctrl2_t               fifo_ctrl2;
  lsm6dsv16x_fifo_ctrl3_t               fifo_ctrl3;
  lsm6dsv16x_fifo_ctrl4_t               fifo_ctrl4;
  lsm6dsv16x_counter_bdr_reg1_t         counter_bdr_reg1;
  lsm6dsv16x_counter_bdr_reg2_t         counter_bdr_reg2;
  lsm6dsv16x_int1_ctrl_t                int1_ctrl;
  lsm6dsv16x_int2_ctrl_t                int2_ctrl;
  lsm6dsv16x_who_am_i_t                 who_am_i;
  lsm6dsv16x_ctrl1_t                    ctrl1;
  lsm6dsv16x_ctrl2_t                    ctrl2;
  lsm6dsv16x_ctrl3_t                    ctrl3;
  lsm6dsv16x_ctrl4_t                    ctrl4;
  lsm6dsv16x_ctrl5_t                    ctrl5;
  lsm6dsv16x_ctrl6_t                    ctrl6;
  lsm6dsv16x_ctrl7_t                    ctrl7;
  lsm6dsv16x_ctrl8_t                    ctrl8;
  lsm6dsv16x_ctrl9_t                    ctrl9;
  lsm6dsv16x_ctrl10_t                   ctrl10;
  lsm6dsv16x_ctrl_status_t              ctrl_status;
  lsm6dsv16x_fifo_status1_t             fifo_status1;
  lsm6dsv16x_fifo_status2_t             fifo_status2;
  lsm6dsv16x_all_int_src_t              all_int_src;
  lsm6dsv16x_status_reg_t               status_reg;
  lsm6dsv16x_out_temp_l_t               out_temp_l;
  lsm6dsv16x_out_temp_h_t               out_temp_h;
  lsm6dsv16x_outx_l_g_t                 outx_l_g;
  lsm6dsv16x_outx_h_g_t                 outx_h_g;
  lsm6dsv16x_outy_l_g_t                 outy_l_g;
  lsm6dsv16x_outy_h_g_t                 outy_h_g;
  lsm6dsv16x_outz_l_g_t                 outz_l_g;
  lsm6dsv16x_outz_h_g_t                 outz_h_g;
  lsm6dsv16x_outx_l_a_t                 outx_l_a;
  lsm6dsv16x_outx_h_a_t                 outx_h_a;
  lsm6dsv16x_outy_l_a_t                 outy_l_a;
  lsm6dsv16x_outy_h_a_t                 outy_h_a;
  lsm6dsv16x_outz_l_a_t                 outz_l_a;
  lsm6dsv16x_outz_h_a_t                 outz_h_a;
  lsm6dsv16x_ui_outx_l_g_ois_eis_t      ui_outx_l_g_ois_eis;
  lsm6dsv16x_ui_outx_h_g_ois_eis_t      ui_outx_h_g_ois_eis;
  lsm6dsv16x_ui_outy_l_g_ois_eis_t      ui_outy_l_g_ois_eis;
  lsm6dsv16x_ui_outy_h_g_ois_eis_t      ui_outy_h_g_ois_eis;
  lsm6dsv16x_ui_outz_l_g_ois_eis_t      ui_outz_l_g_ois_eis;
  lsm6dsv16x_ui_outz_h_g_ois_eis_t      ui_outz_h_g_ois_eis;
  lsm6dsv16x_ui_outx_l_a_ois_dualc_t    ui_outx_l_a_ois_dualc;
  lsm6dsv16x_ui_outx_h_a_ois_dualc_t    ui_outx_h_a_ois_dualc;
  lsm6dsv16x_ui_outy_l_a_ois_dualc_t    ui_outy_l_a_ois_dualc;
  lsm6dsv16x_ui_outy_h_a_ois_dualc_t    ui_outy_h_a_ois_dualc;
  lsm6dsv16x_ui_outz_l_a_ois_dualc_t    ui_outz_l_a_ois_dualc;
  lsm6dsv16x_ui_outz_h_a_ois_dualc_t    ui_outz_h_a_ois_dualc;
  lsm6dsv16x_ah_qvar_out_l_t            ah_qvar_out_l;
  lsm6dsv16x_ah_qvar_out_h_t            ah_qvar_out_h;
  lsm6dsv16x_timestamp0_t               timestamp0;
  lsm6dsv16x_timestamp1_t               timestamp1;
  lsm6dsv16x_timestamp2_t               timestamp2;
  lsm6dsv16x_timestamp3_t               timestamp3;
  lsm6dsv16x_ui_status_reg_ois_t        ui_status_reg_ois;
  lsm6dsv16x_wake_up_src_t              wake_up_src;
  lsm6dsv16x_tap_src_t                  tap_src;
  lsm6dsv16x_d6d_src_t                  d6d_src;
  lsm6dsv16x_status_master_mainpage_t   status_master_mainpage;
  lsm6dsv16x_emb_func_status_mainpage_t emb_func_status_mainpage;
  lsm6dsv16x_fsm_status_mainpage_t      fsm_status_mainpage;
  lsm6dsv16x_mlc_status_mainpage_t      mlc_status_mainpage;
  lsm6dsv16x_internal_freq_t            internal_freq;
  lsm6dsv16x_functions_enable_t         functions_enable;
  lsm6dsv16x_den_t                      den;
  lsm6dsv16x_inactivity_dur_t           inactivity_dur;
  lsm6dsv16x_inactivity_ths_t           inactivity_ths;
  lsm6dsv16x_tap_cfg0_t                 tap_cfg0;
  lsm6dsv16x_tap_cfg1_t                 tap_cfg1;
  lsm6dsv16x_tap_cfg2_t                 tap_cfg2;
  lsm6dsv16x_tap_ths_6d_t               tap_ths_6d;
  lsm6dsv16x_tap_dur_t                  tap_dur;
  lsm6dsv16x_wake_up_ths_t              wake_up_ths;
  lsm6dsv16x_wake_up_dur_t              wake_up_dur;
  lsm6dsv16x_free_fall_t                free_fall;
  lsm6dsv16x_md1_cfg_t                  md1_cfg;
  lsm6dsv16x_md2_cfg_t                  md2_cfg;
  lsm6dsv16x_emb_func_cfg_t             emb_func_cfg;
  lsm6dsv16x_ui_handshake_ctrl_t        ui_handshake_ctrl;
  lsm6dsv16x_ui_spi2_shared_0_t         ui_spi2_shared_0;
  lsm6dsv16x_ui_spi2_shared_1_t         ui_spi2_shared_1;
  lsm6dsv16x_ui_spi2_shared_2_t         ui_spi2_shared_2;
  lsm6dsv16x_ui_spi2_shared_3_t         ui_spi2_shared_3;
  lsm6dsv16x_ui_spi2_shared_4_t         ui_spi2_shared_4;
  lsm6dsv16x_ui_spi2_shared_5_t         ui_spi2_shared_5;
  lsm6dsv16x_ctrl_eis_t                 ctrl_eis;
  lsm6dsv16x_ui_int_ois_t               ui_int_ois;
  lsm6dsv16x_ui_ctrl1_ois_t             ui_ctrl1_ois;
  lsm6dsv16x_ui_ctrl2_ois_t             ui_ctrl2_ois;
  lsm6dsv16x_ui_ctrl3_ois_t             ui_ctrl3_ois;
  lsm6dsv16x_x_ofs_usr_t                x_ofs_usr;
  lsm6dsv16x_y_ofs_usr_t                y_ofs_usr;
  lsm6dsv16x_z_ofs_usr_t                z_ofs_usr;
  lsm6dsv16x_fifo_data_out_tag_t        fifo_data_out_tag;
  lsm6dsv16x_fifo_data_out_x_l_t        fifo_data_out_x_l;
  lsm6dsv16x_fifo_data_out_x_h_t        fifo_data_out_x_h;
  lsm6dsv16x_fifo_data_out_y_l_t        fifo_data_out_y_l;
  lsm6dsv16x_fifo_data_out_y_h_t        fifo_data_out_y_h;
  lsm6dsv16x_fifo_data_out_z_l_t        fifo_data_out_z_l;
  lsm6dsv16x_fifo_data_out_z_h_t        fifo_data_out_z_h;
  lsm6dsv16x_spi2_who_am_i_t            spi2_who_am_i;
  lsm6dsv16x_spi2_status_reg_ois_t      spi2_status_reg_ois;
  lsm6dsv16x_spi2_out_temp_l_t          spi2_out_temp_l;
  lsm6dsv16x_spi2_out_temp_h_t          spi2_out_temp_h;
  lsm6dsv16x_spi2_outx_l_g_ois_t        spi2_outx_l_g_ois;
  lsm6dsv16x_spi2_outx_h_g_ois_t        spi2_outx_h_g_ois;
  lsm6dsv16x_spi2_outy_l_g_ois_t        spi2_outy_l_g_ois;
  lsm6dsv16x_spi2_outy_h_g_ois_t        spi2_outy_h_g_ois;
  lsm6dsv16x_spi2_outz_l_g_ois_t        spi2_outz_l_g_ois;
  lsm6dsv16x_spi2_outz_h_g_ois_t        spi2_outz_h_g_ois;
  lsm6dsv16x_spi2_outx_l_a_ois_t        spi2_outx_l_a_ois;
  lsm6dsv16x_spi2_outx_h_a_ois_t        spi2_outx_h_a_ois;
  lsm6dsv16x_spi2_outy_l_a_ois_t        spi2_outy_l_a_ois;
  lsm6dsv16x_spi2_outy_h_a_ois_t        spi2_outy_h_a_ois;
  lsm6dsv16x_spi2_outz_l_a_ois_t        spi2_outz_l_a_ois;
  lsm6dsv16x_spi2_outz_h_a_ois_t        spi2_outz_h_a_ois;
  lsm6dsv16x_spi2_handshake_ctrl_t      spi2_handshake_ctrl;
  lsm6dsv16x_spi2_int_ois_t             spi2_int_ois;
  lsm6dsv16x_spi2_ctrl1_ois_t           spi2_ctrl1_ois;
  lsm6dsv16x_spi2_ctrl2_ois_t           spi2_ctrl2_ois;
  lsm6dsv16x_spi2_ctrl3_ois_t           spi2_ctrl3_ois;
  lsm6dsv16x_page_sel_t                 page_sel;
  lsm6dsv16x_emb_func_en_a_t            emb_func_en_a;
  lsm6dsv16x_emb_func_en_b_t            emb_func_en_b;
  lsm6dsv16x_emb_func_exec_status_t     emb_func_exec_status;
  lsm6dsv16x_page_address_t             page_address;
  lsm6dsv16x_page_value_t               page_value;
  lsm6dsv16x_emb_func_int1_t            emb_func_int1;
  lsm6dsv16x_fsm_int1_t                 fsm_int1;
  lsm6dsv16x_mlc_int1_t                 mlc_int1;
  lsm6dsv16x_emb_func_int2_t            emb_func_int2;
  lsm6dsv16x_fsm_int2_t                 fsm_int2;
  lsm6dsv16x_mlc_int2_t                 mlc_int2;
  lsm6dsv16x_emb_func_status_t          emb_func_status;
  lsm6dsv16x_fsm_status_t               fsm_status;
  lsm6dsv16x_mlc_status_t               mlc_status;
  lsm6dsv16x_page_rw_t                  page_rw;
  lsm6dsv16x_emb_func_fifo_en_a_t       emb_func_fifo_en_a;
  lsm6dsv16x_emb_func_fifo_en_b_t       emb_func_fifo_en_b;
  lsm6dsv16x_fsm_enable_t               fsm_enable;
  lsm6dsv16x_fsm_long_counter_l_t       fsm_long_counter_l;
  lsm6dsv16x_fsm_long_counter_h_t       fsm_long_counter_h;
  lsm6dsv16x_int_ack_mask_t             int_ack_mask;
  lsm6dsv16x_fsm_outs1_t                fsm_outs1;
  lsm6dsv16x_fsm_outs2_t                fsm_outs2;
  lsm6dsv16x_fsm_outs3_t                fsm_outs3;
  lsm6dsv16x_fsm_outs4_t                fsm_outs4;
  lsm6dsv16x_fsm_outs5_t                fsm_outs5;
  lsm6dsv16x_fsm_outs6_t                fsm_outs6;
  lsm6dsv16x_fsm_outs7_t                fsm_outs7;
  lsm6dsv16x_fsm_outs8_t                fsm_outs8;
  lsm6dsv16x_fsm_odr_t                  fsm_odr;
  lsm6dsv16x_mlc_odr_t                  mlc_odr;
  lsm6dsv16x_step_counter_l_t           step_counter_l;
  lsm6dsv16x_step_counter_h_t           step_counter_h;
  lsm6dsv16x_emb_func_src_t             emb_func_src;
  lsm6dsv16x_emb_func_init_a_t          emb_func_init_a;
  lsm6dsv16x_emb_func_init_b_t          emb_func_init_b;
  lsm6dsv16x_mlc1_src_t                 mlc1_src;
  lsm6dsv16x_mlc2_src_t                 mlc2_src;
  lsm6dsv16x_mlc3_src_t                 mlc3_src;
  lsm6dsv16x_mlc4_src_t                 mlc4_src;
  lsm6dsv16x_fsm_ext_sensitivity_l_t    fsm_ext_sensitivity_l;
  lsm6dsv16x_fsm_ext_sensitivity_h_t    fsm_ext_sensitivity_h;
  lsm6dsv16x_fsm_ext_offx_l_t           fsm_ext_offx_l;
  lsm6dsv16x_fsm_ext_offx_h_t           fsm_ext_offx_h;
  lsm6dsv16x_fsm_ext_offy_l_t           fsm_ext_offy_l;
  lsm6dsv16x_fsm_ext_offy_h_t           fsm_ext_offy_h;
  lsm6dsv16x_fsm_ext_offz_l_t           fsm_ext_offz_l;
  lsm6dsv16x_fsm_ext_offz_h_t           fsm_ext_offz_h;
  lsm6dsv16x_fsm_ext_matrix_xx_l_t      fsm_ext_matrix_xx_l;
  lsm6dsv16x_fsm_ext_matrix_xx_h_t      fsm_ext_matrix_xx_h;
  lsm6dsv16x_fsm_ext_matrix_xy_l_t      fsm_ext_matrix_xy_l;
  lsm6dsv16x_fsm_ext_matrix_xy_h_t      fsm_ext_matrix_xy_h;
  lsm6dsv16x_fsm_ext_matrix_xz_l_t      fsm_ext_matrix_xz_l;
  lsm6dsv16x_fsm_ext_matrix_xz_h_t      fsm_ext_matrix_xz_h;
  lsm6dsv16x_fsm_ext_matrix_yy_l_t      fsm_ext_matrix_yy_l;
  lsm6dsv16x_fsm_ext_matrix_yy_h_t      fsm_ext_matrix_yy_h;
  lsm6dsv16x_fsm_ext_matrix_yz_l_t      fsm_ext_matrix_yz_l;
  lsm6dsv16x_fsm_ext_matrix_yz_h_t      fsm_ext_matrix_yz_h;
  lsm6dsv16x_fsm_ext_matrix_zz_l_t      fsm_ext_matrix_zz_l;
  lsm6dsv16x_fsm_ext_matrix_zz_h_t      fsm_ext_matrix_zz_h;
  lsm6dsv16x_ext_cfg_a_t                ext_cfg_a;
  lsm6dsv16x_ext_cfg_b_t                ext_cfg_b;
  lsm6dsv16x_fsm_lc_timeout_l_t         fsm_lc_timeout_l;
  lsm6dsv16x_fsm_lc_timeout_h_t         fsm_lc_timeout_h;
  lsm6dsv16x_fsm_programs_t             fsm_programs;
  lsm6dsv16x_fsm_start_add_l_t          fsm_start_add_l;
  lsm6dsv16x_fsm_start_add_h_t          fsm_start_add_h;
  lsm6dsv16x_pedo_cmd_reg_t             pedo_cmd_reg;
  lsm6dsv16x_pedo_deb_steps_conf_t      pedo_deb_steps_conf;
  lsm6dsv16x_pedo_sc_deltat_l_t         pedo_sc_deltat_l;
  lsm6dsv16x_pedo_sc_deltat_h_t         pedo_sc_deltat_h;
  lsm6dsv16x_mlc_ext_sensitivity_l_t    mlc_ext_sensitivity_l;
  lsm6dsv16x_mlc_ext_sensitivity_h_t    mlc_ext_sensitivity_h;
  lsm6dsv16x_sensor_hub_1_t             sensor_hub_1;
  lsm6dsv16x_sensor_hub_2_t             sensor_hub_2;
  lsm6dsv16x_sensor_hub_3_t             sensor_hub_3;
  lsm6dsv16x_sensor_hub_4_t             sensor_hub_4;
  lsm6dsv16x_sensor_hub_5_t             sensor_hub_5;
  lsm6dsv16x_sensor_hub_6_t             sensor_hub_6;
  lsm6dsv16x_sensor_hub_7_t             sensor_hub_7;
  lsm6dsv16x_sensor_hub_8_t             sensor_hub_8;
  lsm6dsv16x_sensor_hub_9_t             sensor_hub_9;
  lsm6dsv16x_sensor_hub_10_t            sensor_hub_10;
  lsm6dsv16x_sensor_hub_11_t            sensor_hub_11;
  lsm6dsv16x_sensor_hub_12_t            sensor_hub_12;
  lsm6dsv16x_sensor_hub_13_t            sensor_hub_13;
  lsm6dsv16x_sensor_hub_14_t            sensor_hub_14;
  lsm6dsv16x_sensor_hub_15_t            sensor_hub_15;
  lsm6dsv16x_sensor_hub_16_t            sensor_hub_16;
  lsm6dsv16x_sensor_hub_17_t            sensor_hub_17;
  lsm6dsv16x_sensor_hub_18_t            sensor_hub_18;
  lsm6dsv16x_master_config_t            master_config;
  lsm6dsv16x_slv0_add_t                 slv0_add;
  lsm6dsv16x_slv0_subadd_t              slv0_subadd;
  lsm6dsv16x_slv0_config_t              slv0_config;
  lsm6dsv16x_slv1_add_t                 slv1_add;
  lsm6dsv16x_slv1_subadd_t              slv1_subadd;
  lsm6dsv16x_slv1_config_t              slv1_config;
  lsm6dsv16x_slv2_add_t                 slv2_add;
  lsm6dsv16x_slv2_subadd_t              slv2_subadd;
  lsm6dsv16x_slv2_config_t              slv2_config;
  lsm6dsv16x_slv3_add_t                 slv3_add;
  lsm6dsv16x_slv3_subadd_t              slv3_subadd;
  lsm6dsv16x_slv3_config_t              slv3_config;
  lsm6dsv16x_datawrite_slv0_t           datawrite_slv0;
  lsm6dsv16x_status_master_t            status_master;
  bitwise_t                             bitwise;
  uint8_t                               byte;
} lsm6dsv16x_reg_t;

/**
  * @}
  *
  */

#ifndef __weak
#define __weak __attribute__((weak))
#endif /* __weak */

/**
  * @defgroup  LSM6DSV16X LSM6DSV16X
  * @brief     This file provides a set of functions needed to drive the
  *            lsm6dsv16x enhanced inertial module.
  * @{
  *
  */

/**
  * @defgroup  Interface Interfaces functions
  * @brief     This section provide a set of functions used to read and
  *            write a generic register of the device.
  *            MANDATORY: return 0 -> no Error.
  * @{
  *
  */

/*
 * These are the basic platform dependent I/O routines to read
 * and write device registers connected on a standard bus.
 * The driver keeps offering a default implementation based on function
 * pointers to read/write routines for backward compatibility.
 * The __weak directive allows the final application to overwrite
 * them with a custom implementation.
 */

/**
  * @brief  Read generic device register
  *
  * @param  ctx   communication interface handler.(ptr)
  * @param  reg   first register address to read.
  * @param  data  buffer for data read.(ptr)
  * @param  len   number of consecutive register to read.
  * @retval       interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_read_reg(const stmdev_ctx_t *ctx, uint8_t reg,
                            uint8_t *data,
                            uint16_t len);

/**
  * @brief  Write generic device register
  *
  * @param  ctx   communication interface handler.(ptr)
  * @param  reg   first register address to write.
  * @param  data  the buffer contains data to be written.(ptr)
  * @param  len   number of consecutive register to write.
  * @retval       interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_write_reg(const stmdev_ctx_t *ctx, uint8_t reg,
                             uint8_t *data,
                             uint16_t len);
/**
  * @}
  *
  */

/**
  * @defgroup  Sensitivity Sensitivity Functions
  * @brief     These functions convert raw-data into engineering units.
  * @{
  *
  */

/**
  * @brief  Convert Accelerometer SFLP lsb into mg (full-scale @2g)
  *
  * @param  lsb   Accelerometer raw data in SFLP mode (full-scale is 2g)
  * @retval       Accelerometer value in mg unit
  *
  */
float_t lsm6dsv16x_from_sflp_to_mg(int16_t lsb);

/**
  * @brief  Convert Accelerometer lsb into mg (full-scale @2g)
  *
  * @param  lsb   Accelerometer raw data when full-scale is 2g
  * @retval       Accelerometer value in mg unit
  *
  */
float_t lsm6dsv16x_from_fs2_to_mg(int16_t lsb);

/**
  * @brief  Convert Accelerometer lsb into mg (full-scale @4g)
  *
  * @param  lsb   Accelerometer raw data when full-scale is 4g
  * @retval       Accelerometer value in mg unit
  *
  */
float_t lsm6dsv16x_from_fs4_to_mg(int16_t lsb);

/**
  * @brief  Convert Accelerometer lsb into mg (full-scale @8g)
  *
  * @param  lsb   Accelerometer raw data when full-scale is 8g
  * @retval       Accelerometer value in mg unit
  *
  */
float_t lsm6dsv16x_from_fs8_to_mg(int16_t lsb);

/**
  * @brief  Convert Accelerometer lsb into mg (full-scale @16g)
  *
  * @param  lsb   Accelerometer raw data when full-scale is 16g
  * @retval       Accelerometer value in mg unit
  *
  */
float_t lsm6dsv16x_from_fs16_to_mg(int16_t lsb);

/**
  * @brief  Convert Gyroscope lsb into mdps (full-scale @125dps)
  *
  * @param  lsb   Gyroscope raw data when full-scale is 125dps
  * @retval       Gyroscope value in mdps unit
  *
  */
float_t lsm6dsv16x_from_fs125_to_mdps(int16_t lsb);

/**
  * @brief  Convert Gyroscope lsb into mdps (full-scale @250dps)
  *
  * @param  lsb   Gyroscope raw data when full-scale is 250dps
  * @retval       Gyroscope value in mdps unit
  *
  */
float_t lsm6dsv16x_from_fs250_to_mdps(int16_t lsb);

/**
  * @brief  Convert Gyroscope lsb into mdps (full-scale @500dps)
  *
  * @param  lsb   Gyroscope raw data when full-scale is 500dps
  * @retval       Gyroscope value in mdps unit
  *
  */
float_t lsm6dsv16x_from_fs500_to_mdps(int16_t lsb);

/**
  * @brief  Convert Gyroscope lsb into mdps (full-scale @1000dps)
  *
  * @param  lsb   Gyroscope raw data when full-scale is 1000dps
  * @retval       Gyroscope value in mdps unit
  *
  */
float_t lsm6dsv16x_from_fs1000_to_mdps(int16_t lsb);

/**
  * @brief  Convert Gyroscope lsb into mdps (full-scale @2000dps)
  *
  * @param  lsb   Gyroscope raw data when full-scale is 2000dps
  * @retval       Gyroscope value in mdps unit
  *
  */
float_t lsm6dsv16x_from_fs2000_to_mdps(int16_t lsb);

/**
  * @brief  Convert Gyroscope lsb into mdps (full-scale @4000dps)
  *
  * @param  lsb   Gyroscope raw data when full-scale is 4000dps
  * @retval       Gyroscope value in mdps unit
  *
  */
float_t lsm6dsv16x_from_fs4000_to_mdps(int16_t lsb);

/**
  * @brief  Convert Temperature lsb into Celsius
  *
  * @param  lsb   Temperature raw data
  * @retval       Temperature value in Celsius unit
  *
  */
float_t lsm6dsv16x_from_lsb_to_celsius(int16_t lsb);

/**
  * @brief  Convert Timestamp lsb into nsec
  *
  * @param  lsb   Timestamp raw data
  * @retval       Timestamp value in nsec unit
  *
  */
float_t lsm6dsv16x_from_lsb_to_nsec(uint32_t lsb);

/**
  * @brief  Convert QVAR raw value into milli-volt
  *
  * @param  val      QVAR raw data
  * @retval          QVAR value in mv units
  *
  */
float_t lsm6dsv16x_from_lsb_to_mv(int16_t lsb);

/**
  * @brief  Convert from FP16 to FP32 numbers (e.g. quaternions)
  *
  * @param  val      half-precision (16-bit) float number
  * @retval          single-precision (32-bit) float number
  *
  */
uint32_t lsm6dsv16x_from_f16_to_f32(uint16_t val);

/**
  * @brief  Convert from FP32 to FP16 numbers (e.g. quaternions)
  *
  * @param  val      single-precision (32-bit) float number
  * @retval          half-precision (16-bit) float number
  *
  */
uint16_t lsm6dsv16x_from_f32_to_f16(float_t val);

/**
  * @}
  *
  */


/**
  * @defgroup  XL_Offset Accelerometer user offset correction
  * @brief      This section groups all the functions concerning the
  *             usage of Accelerometer user offset correction
  * @{
  *
  */

/**
  * @brief  Enables accelerometer user offset correction block; it is valid for the low-pass path.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables accelerometer user offset correction block; it is valid for the low-pass path.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_offset_on_out_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables accelerometer user offset correction block; it is valid for the low-pass path.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables accelerometer user offset correction block; it is valid for the low-pass path.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_offset_on_out_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  float_t z_mg;
  float_t y_mg;
  float_t x_mg;
} lsm6dsv16x_xl_offset_mg_t;

/**
  * @brief  Accelerometer user offset correction values in mg.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Accelerometer user offset correction values in mg.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_offset_mg_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_xl_offset_mg_t val);

/**
  * @brief  Accelerometer user offset correction values in mg.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Accelerometer user offset correction values in mg.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_offset_mg_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_xl_offset_mg_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  Reset Reset functions
  * @brief      This section groups all the functions concerning the
  *             reset and power on routines.
  * @{
  *
  */

/**
  * @brief Perform reboot of the device.
  *
  * @param  ctx      read / write interface definitions
  * @retval          0: reboot has been performed, -1: error
  *
  */
int32_t lsm6dsv16x_reboot(const stmdev_ctx_t *ctx);
/**
  * @brief  Perform power-on-reset of the device.
  *
  * @param  ctx      read / write interface definitions
  * @retval          0: power-on-reset has been performed, -1: error
  *
  */
int32_t lsm6dsv16x_sw_por(const stmdev_ctx_t *ctx);
/**
  * @brief  Perform s/w reset of the device.
  *
  * @param  ctx      read / write interface definitions
  * @retval          0: s/w reset has been performed, -1: error
  *
  */
int32_t lsm6dsv16x_sw_reset(const stmdev_ctx_t *ctx);

/**
  * @}
  *
  */

typedef enum
{
  LSM6DSV16X_MAIN_MEM_BANK       = 0x0,
  LSM6DSV16X_EMBED_FUNC_MEM_BANK = 0x1,
  LSM6DSV16X_SENSOR_HUB_MEM_BANK = 0x2,
} lsm6dsv16x_mem_bank_t;
/**
  * @brief  Change memory bank.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      MAIN_MEM_BANK, EMBED_FUNC_MEM_BANK,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mem_bank_set(const stmdev_ctx_t *ctx, lsm6dsv16x_mem_bank_t val);
/**
  * @brief  Change memory bank.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      MAIN_MEM_BANK, SENSOR_HUB_MEM_BANK, EMBED_FUNC_MEM_BANK,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mem_bank_get(const stmdev_ctx_t *ctx, lsm6dsv16x_mem_bank_t *val);

/**
  * @brief  Device ID.[get] THis function works also for OIS
  *        (WHO_AM_I and SPI2_WHO_AM_I have same address)
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Device ID.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_device_id_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_ODR_OFF              = 0x0,
  LSM6DSV16X_ODR_AT_1Hz875        = 0x1,
  LSM6DSV16X_ODR_AT_7Hz5          = 0x2,
  LSM6DSV16X_ODR_AT_15Hz          = 0x3,
  LSM6DSV16X_ODR_AT_30Hz          = 0x4,
  LSM6DSV16X_ODR_AT_60Hz          = 0x5,
  LSM6DSV16X_ODR_AT_120Hz         = 0x6,
  LSM6DSV16X_ODR_AT_240Hz         = 0x7,
  LSM6DSV16X_ODR_AT_480Hz         = 0x8,
  LSM6DSV16X_ODR_AT_960Hz         = 0x9,
  LSM6DSV16X_ODR_AT_1920Hz        = 0xA,
  LSM6DSV16X_ODR_AT_3840Hz        = 0xB,
  LSM6DSV16X_ODR_AT_7680Hz        = 0xC,
  LSM6DSV16X_ODR_HA01_AT_15Hz625  = 0x13,
  LSM6DSV16X_ODR_HA01_AT_31Hz25   = 0x14,
  LSM6DSV16X_ODR_HA01_AT_62Hz5    = 0x15,
  LSM6DSV16X_ODR_HA01_AT_125Hz    = 0x16,
  LSM6DSV16X_ODR_HA01_AT_250Hz    = 0x17,
  LSM6DSV16X_ODR_HA01_AT_500Hz    = 0x18,
  LSM6DSV16X_ODR_HA01_AT_1000Hz   = 0x19,
  LSM6DSV16X_ODR_HA01_AT_2000Hz   = 0x1A,
  LSM6DSV16X_ODR_HA01_AT_4000Hz   = 0x1B,
  LSM6DSV16X_ODR_HA01_AT_8000Hz   = 0x1C,
  LSM6DSV16X_ODR_HA02_AT_12Hz5    = 0x23,
  LSM6DSV16X_ODR_HA02_AT_25Hz     = 0x24,
  LSM6DSV16X_ODR_HA02_AT_50Hz     = 0x25,
  LSM6DSV16X_ODR_HA02_AT_100Hz    = 0x26,
  LSM6DSV16X_ODR_HA02_AT_200Hz    = 0x27,
  LSM6DSV16X_ODR_HA02_AT_400Hz    = 0x28,
  LSM6DSV16X_ODR_HA02_AT_800Hz    = 0x29,
  LSM6DSV16X_ODR_HA02_AT_1600Hz   = 0x2A,
  LSM6DSV16X_ODR_HA02_AT_3200Hz   = 0x2B,
  LSM6DSV16X_ODR_HA02_AT_6400Hz   = 0x2C,
} lsm6dsv16x_data_rate_t;

/**
  * @brief  Accelerometer output data rate (ODR) selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_data_rate_t enum
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_data_rate_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_data_rate_t val);

/**
  * @brief  Accelerometer output data rate (ODR) selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_data_rate_t enum
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_data_rate_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_data_rate_t *val);
/**
  * @brief  Gyroscope output data rate (ODR) selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_data_rate_t enum
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_data_rate_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_data_rate_t val);
/**
  * @brief  Gyroscope output data rate (ODR) selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_data_rate_t enum
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_data_rate_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_data_rate_t *val);


typedef enum
{
  LSM6DSV16X_XL_HIGH_PERFORMANCE_MD   = 0x0,
  LSM6DSV16X_XL_HIGH_ACCURACY_ODR_MD  = 0x1,
  LSM6DSV16X_XL_ODR_TRIGGERED_MD      = 0x3,
  LSM6DSV16X_XL_LOW_POWER_2_AVG_MD    = 0x4,
  LSM6DSV16X_XL_LOW_POWER_4_AVG_MD    = 0x5,
  LSM6DSV16X_XL_LOW_POWER_8_AVG_MD    = 0x6,
  LSM6DSV16X_XL_NORMAL_MD             = 0x7,
} lsm6dsv16x_xl_mode_t;
/**
  * @brief  Accelerometer operating mode selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_HIGH_PERFORMANCE_MD, XL_HIGH_ACCURACY_ODR_MD, XL_LOW_POWER_2_AVG_MD, XL_LOW_POWER_4_AVG_MD, XL_LOW_POWER_8_AVG_MD, XL_NORMAL_MD,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_xl_mode_t val);

/**
  * @brief  Accelerometer operating mode selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_HIGH_PERFORMANCE_MD, XL_HIGH_ACCURACY_ODR_MD, XL_LOW_POWER_2_AVG_MD, XL_LOW_POWER_4_AVG_MD, XL_LOW_POWER_8_AVG_MD, XL_NORMAL_MD,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_mode_get(const stmdev_ctx_t *ctx, lsm6dsv16x_xl_mode_t *val);

typedef enum
{
  LSM6DSV16X_GY_HIGH_PERFORMANCE_MD   = 0x0,
  LSM6DSV16X_GY_HIGH_ACCURACY_ODR_MD  = 0x1,
  LSM6DSV16X_GY_SLEEP_MD              = 0x4,
  LSM6DSV16X_GY_LOW_POWER_MD          = 0x5,
} lsm6dsv16x_gy_mode_t;

/**
  * @brief  Gyroscope operating mode selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_HIGH_PERFORMANCE_MD, GY_HIGH_ACCURACY_ODR_MD, GY_SLEEP_MD, GY_LOW_POWER_MD,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_gy_mode_t val);

/**
  * @brief  Gyroscope operating mode selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_HIGH_PERFORMANCE_MD, GY_HIGH_ACCURACY_ODR_MD, GY_SLEEP_MD, GY_LOW_POWER_MD,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_mode_get(const stmdev_ctx_t *ctx, lsm6dsv16x_gy_mode_t *val);

/**
  * @brief  Register address automatically incremented during a multiple byte access with a serial interface (enable by default).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Register address automatically incremented during a multiple byte access with a serial interface (enable by default).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_auto_increment_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Register address automatically incremented during a multiple byte access with a serial interface (enable by default).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Register address automatically incremented during a multiple byte access with a serial interface (enable by default).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_auto_increment_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Block Data Update (BDU): output registers are not updated until LSB and MSB have been read). [set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Block Data Update (BDU): output registers are not updated until LSB and MSB have been read).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_block_data_update_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Block Data Update (BDU): output registers are not updated until LSB and MSB have been read). [get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Block Data Update (BDU): output registers are not updated until LSB and MSB have been read).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_block_data_update_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Configure ODR trigger. [set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      number of data in the reference period.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_odr_trig_cfg_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Configure ODR trigger. [get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      number of data in the reference period.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_odr_trig_cfg_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_DRDY_LATCHED = 0x0,
  LSM6DSV16X_DRDY_PULSED  = 0x1,
} lsm6dsv16x_data_ready_mode_t;

/**
  * @brief  Enables pulsed data-ready mode (~75 us).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      DRDY_LATCHED, DRDY_PULSED,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_data_ready_mode_set(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_data_ready_mode_t val);

/**
  * @brief  Enables pulsed data-ready mode (~75 us).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      DRDY_LATCHED, DRDY_PULSED,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_data_ready_mode_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_data_ready_mode_t *val);

typedef struct
{
  uint8_t enable               : 1; /* interrupt enable */
  uint8_t lir                  : 1; /* interrupt pulsed or latched */
} lsm6dsv16x_interrupt_mode_t;

/**
  * @brief  Enables interrupt.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      enable/disable, latched/pulsed
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_interrupt_enable_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_interrupt_mode_t val);

/**
  * @brief  Enables latched interrupt mode.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      enable/disable, latched/pulsed
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_interrupt_enable_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_interrupt_mode_t *val);

typedef enum
{
  LSM6DSV16X_125dps  = 0x0,
  LSM6DSV16X_250dps  = 0x1,
  LSM6DSV16X_500dps  = 0x2,
  LSM6DSV16X_1000dps = 0x3,
  LSM6DSV16X_2000dps = 0x4,
  LSM6DSV16X_4000dps = 0xc,
} lsm6dsv16x_gy_full_scale_t;

/**
  * @brief  Gyroscope full-scale selection[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      125dps, 250dps, 500dps, 1000dps, 2000dps, 4000dps,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_full_scale_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_gy_full_scale_t val);
/**
  * @brief  Gyroscope full-scale selection[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      125dps, 250dps, 500dps, 1000dps, 2000dps, 4000dps,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_full_scale_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_gy_full_scale_t *val);

typedef enum
{
  LSM6DSV16X_2g  = 0x0,
  LSM6DSV16X_4g  = 0x1,
  LSM6DSV16X_8g  = 0x2,
  LSM6DSV16X_16g = 0x3,
} lsm6dsv16x_xl_full_scale_t;

/**
  * @brief  Accelerometer full-scale selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_xl_full_scale_t
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_full_scale_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_xl_full_scale_t val);

/**
  * @brief  Accelerometer full-scale selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_xl_full_scale_t
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_full_scale_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_xl_full_scale_t *val);

/**
  * @brief  It enables the accelerometer Dual channel mode: data with selected full scale and data with maximum full scale are sent simultaneously to two different set of output registers.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It enables the accelerometer Dual channel mode: data with selected full scale and data with maximum full scale are sent simultaneously to two different set of output registers.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_dual_channel_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  It enables the accelerometer Dual channel mode: data with selected full scale and data with maximum full scale are sent simultaneously to two different set of output registers.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It enables the accelerometer Dual channel mode: data with selected full scale and data with maximum full scale are sent simultaneously to two different set of output registers.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_dual_channel_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_XL_ST_DISABLE  = 0x0,
  LSM6DSV16X_XL_ST_POSITIVE = 0x1,
  LSM6DSV16X_XL_ST_NEGATIVE = 0x2,
} lsm6dsv16x_xl_self_test_t;

/**
  * @brief  Accelerometer self-test selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ST_DISABLE, XL_ST_POSITIVE, XL_ST_NEGATIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_self_test_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_xl_self_test_t val);

/**
  * @brief  Accelerometer self-test selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ST_DISABLE, XL_ST_POSITIVE, XL_ST_NEGATIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_xl_self_test_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_xl_self_test_t *val);

typedef enum
{
  LSM6DSV16X_OIS_XL_ST_DISABLE  = 0x0,
  LSM6DSV16X_OIS_XL_ST_POSITIVE = 0x1,
  LSM6DSV16X_OIS_XL_ST_NEGATIVE = 0x2,
} lsm6dsv16x_ois_xl_self_test_t;

/**
  * @brief  SPI2 Accelerometer self-test selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ST_DISABLE, XL_ST_POSITIVE, XL_ST_NEGATIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_xl_self_test_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_ois_xl_self_test_t val);

/**
  * @brief  SPI2 Accelerometer self-test selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ST_DISABLE, XL_ST_POSITIVE, XL_ST_NEGATIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_xl_self_test_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_ois_xl_self_test_t *val);

typedef enum
{
  LSM6DSV16X_GY_ST_DISABLE  = 0x0,
  LSM6DSV16X_GY_ST_POSITIVE = 0x1,
  LSM6DSV16X_GY_ST_NEGATIVE = 0x2,

} lsm6dsv16x_gy_self_test_t;

/**
  * @brief  Gyroscope self-test selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ST_DISABLE, XL_ST_POSITIVE, XL_ST_NEGATIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_self_test_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_gy_self_test_t val);

/**
  * @brief  Gyroscope self-test selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ST_DISABLE, XL_ST_POSITIVE, XL_ST_NEGATIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_self_test_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_gy_self_test_t *val);

typedef enum
{
  LSM6DSV16X_OIS_GY_ST_DISABLE   = 0x0,
  LSM6DSV16X_OIS_GY_ST_POSITIVE  = 0x1,
  LSM6DSV16X_OIS_GY_ST_NEGATIVE  = 0x2,
  LSM6DSV16X_OIS_GY_ST_CLAMP_POS = 0x5,
  LSM6DSV16X_OIS_GY_ST_CLAMP_NEG = 0x6,

} lsm6dsv16x_ois_gy_self_test_t;

/**
  * @brief  SPI2 Accelerometer self-test selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_ST_DISABLE, GY_ST_POSITIVE, GY_ST_NEGATIVE, LSM6DSV16X_OIS_GY_ST_CLAMP_POS, LSM6DSV16X_OIS_GY_ST_CLAMP_NEG
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_gy_self_test_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_ois_gy_self_test_t val);

/**
  * @brief  SPI2 Accelerometer self-test selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_ST_DISABLE, GY_ST_POSITIVE, GY_ST_NEGATIVE, LSM6DSV16X_OIS_GY_ST_CLAMP_POS, LSM6DSV16X_OIS_GY_ST_CLAMP_NEG
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_gy_self_test_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_ois_gy_self_test_t *val);

typedef struct
{
  uint8_t drdy_xl              : 1;
  uint8_t drdy_gy              : 1;
  uint8_t drdy_temp            : 1;
  uint8_t drdy_ah_qvar         : 1;
  uint8_t drdy_eis             : 1;
  uint8_t drdy_ois             : 1;
  uint8_t gy_settling          : 1;
  uint8_t timestamp            : 1;
  uint8_t free_fall            : 1;
  uint8_t wake_up              : 1;
  uint8_t wake_up_z            : 1;
  uint8_t wake_up_y            : 1;
  uint8_t wake_up_x            : 1;
  uint8_t single_tap           : 1;
  uint8_t double_tap           : 1;
  uint8_t tap_z                : 1;
  uint8_t tap_y                : 1;
  uint8_t tap_x                : 1;
  uint8_t tap_sign             : 1;
  uint8_t six_d                : 1;
  uint8_t six_d_xl             : 1;
  uint8_t six_d_xh             : 1;
  uint8_t six_d_yl             : 1;
  uint8_t six_d_yh             : 1;
  uint8_t six_d_zl             : 1;
  uint8_t six_d_zh             : 1;
  uint8_t sleep_change         : 1;
  uint8_t sleep_state          : 1;
  uint8_t step_detector        : 1;
  uint8_t step_count_inc       : 1;
  uint8_t step_count_overflow  : 1;
  uint8_t step_on_delta_time   : 1;
  uint8_t emb_func_stand_by    : 1;
  uint8_t emb_func_time_exceed : 1;
  uint8_t tilt                 : 1;
  uint8_t sig_mot              : 1;
  uint8_t fsm_lc               : 1;
  uint8_t fsm1                 : 1;
  uint8_t fsm2                 : 1;
  uint8_t fsm3                 : 1;
  uint8_t fsm4                 : 1;
  uint8_t fsm5                 : 1;
  uint8_t fsm6                 : 1;
  uint8_t fsm7                 : 1;
  uint8_t fsm8                 : 1;
  uint8_t mlc1                 : 1;
  uint8_t mlc2                 : 1;
  uint8_t mlc3                 : 1;
  uint8_t mlc4                 : 1;
  uint8_t sh_endop             : 1;
  uint8_t sh_slave0_nack       : 1;
  uint8_t sh_slave1_nack       : 1;
  uint8_t sh_slave2_nack       : 1;
  uint8_t sh_slave3_nack       : 1;
  uint8_t sh_wr_once           : 1;
  uint8_t fifo_bdr             : 1;
  uint8_t fifo_full            : 1;
  uint8_t fifo_ovr             : 1;
  uint8_t fifo_th              : 1;
} lsm6dsv16x_all_sources_t;

/**
  * @brief  Get the status of all the interrupt sources.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Get the status of all the interrupt sources.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_all_sources_get(const stmdev_ctx_t *ctx,
                                   lsm6dsv16x_all_sources_t *val);

/**
  * @defgroup   interrupt_pins Interrupt Pins Configuration
  * @brief      This section groups all the functions that manage
  *             interrupt pins
  * @{
  *
  */

typedef struct
{
  uint8_t drdy_xl              : 1;
  uint8_t drdy_g               : 1;
  uint8_t drdy_g_eis           : 1;
  uint8_t drdy_temp            : 1;
  uint8_t drdy_ah_qvar         : 1;
  uint8_t fifo_th              : 1;
  uint8_t fifo_ovr             : 1;
  uint8_t fifo_full            : 1;
  uint8_t cnt_bdr              : 1;
  uint8_t emb_func_endop       : 1;
  uint8_t timestamp            : 1;
  uint8_t shub                 : 1;
  uint8_t emb_func             : 1;
  uint8_t sixd                 : 1;
  uint8_t single_tap           : 1;
  uint8_t double_tap           : 1;
  uint8_t wakeup               : 1;
  uint8_t freefall             : 1;
  uint8_t sleep_change         : 1;
} lsm6dsv16x_pin_int_route_t;

/**
  * @brief   Select the signal that need to route on int1 pad[set]
  *
  * @param  ctx    Read / write interface definitions.(ptr)
  * @param  val    the signals to route on int1 pin.
  * @retval        Interface status (MANDATORY: return 0 -> no Error).
  *
  */
int32_t lsm6dsv16x_pin_int1_route_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_pin_int_route_t *val);

/**
  * @brief  Select the signal that need to route on int1 pad.[get]
  *
  * @param  ctx    Read / write interface definitions.(ptr)
  * @param  val    the signals that are routed on int1 pin.(ptr)
  * @retval        Interface status (MANDATORY: return 0 -> no Error).
  *
  */
int32_t lsm6dsv16x_pin_int1_route_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_pin_int_route_t *val);

/**
  * @brief   Select the signal that need to route on int2 pad[set]
  *
  * @param  ctx    Read / write interface definitions.(ptr)
  * @param  val    the signals to route on int2 pin.
  * @retval        Interface status (MANDATORY: return 0 -> no Error).
  *
  */
int32_t lsm6dsv16x_pin_int2_route_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_pin_int_route_t *val);

/**
  * @brief  Select the signal that need to route on int2 pad.[get]
  *
  * @param  ctx    Read / write interface definitions.(ptr)
  * @param  val    the signals that are routed on int2 pin.(ptr)
  * @retval        Interface status (MANDATORY: return 0 -> no Error).
  *
  */
int32_t lsm6dsv16x_pin_int2_route_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_pin_int_route_t *val);

typedef struct
{
  uint8_t step_det                     : 1; /* route step detection event on INT pad */
  uint8_t tilt                         : 1; /* route tilt event on INT pad */
  uint8_t sig_mot                      : 1; /* route significant motion event on INT pad */
  uint8_t fsm_lc                       : 1; /* route FSM long counter event on INT pad */
} lsm6dsv16x_emb_pin_int_route_t;

/**
  * @brief  routes embedded func interrupt signals on INT 1 pin.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      routes embedded func interrupt signals on INT 1 pin.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_emb_pin_int1_route_set(const stmdev_ctx_t *ctx,
                                          const lsm6dsv16x_emb_pin_int_route_t *val);

/**
  * @brief  routes embedded func interrupt signals on INT 1 pin.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      routes embedded func interrupt signals on INT 1 pin.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_emb_pin_int1_route_get(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_emb_pin_int_route_t *val);

/**
  * @brief  routes embedded func interrupt signals on INT 2 pin.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      routes embedded func interrupt signals on INT 2 pin.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_emb_pin_int2_route_set(const stmdev_ctx_t *ctx,
                                          const lsm6dsv16x_emb_pin_int_route_t *val);

/**
  * @brief  routes embedded func interrupt signals on INT 2 pin.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      routes embedded func interrupt signals on INT 2 pin.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_emb_pin_int2_route_get(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_emb_pin_int_route_t *val);

typedef enum
{
  LSM6DSV16X_INT_LATCH_DISABLE         = 0x0,
  LSM6DSV16X_INT_LATCH_ENABLE          = 0x1,
} lsm6dsv16x_embedded_int_config_t;

/**
  * @brief  Embedded Interrupt configuration mode.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      INT_PULSED, INT_LATCHED
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_embedded_int_cfg_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_embedded_int_config_t val);

/**
  * @brief  Interrupt configuration mode.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      INT_DISABLED, INT_PULSED, INT_LATCHED
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_embedded_int_cfg_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_embedded_int_config_t *val);

typedef struct
{
  uint8_t tilt                 : 1;
  uint8_t sig_mot              : 1;
  uint8_t fsm_lc               : 1;
  uint8_t step_detector        : 1;
  uint8_t step_count_inc       : 1;
  uint8_t step_count_overflow  : 1;
  uint8_t step_on_delta_time   : 1;
} lsm6dsv16x_embedded_status_t;

/**
  * @brief  Get the status of embedded functions.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_embedded_status_t ptr
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_embedded_status_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_embedded_status_t *val);

/**
  * @}
  *
  */

typedef struct
{
  uint8_t drdy_xl              : 1;
  uint8_t drdy_gy              : 1;
  uint8_t drdy_temp            : 1;
} lsm6dsv16x_data_ready_t;
int32_t lsm6dsv16x_flag_data_ready_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_data_ready_t *val);

/**
  * @brief  Mask status bit reset[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Mask to prevent status bit being reset
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_int_ack_mask_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Mask status bit reset[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Mask to prevent status bit being reset
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_int_ack_mask_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Temperature data output register[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Temperature data output register
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_temperature_raw_get(const stmdev_ctx_t *ctx, int16_t *val);

/**
  * @brief  Angular rate sensor.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Angular rate sensor.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_angular_rate_raw_get(const stmdev_ctx_t *ctx, int16_t *val);

/**
  * @brief  Angular rate sensor.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS Angular rate sensor (thru SPI2).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_angular_rate_raw_get(const stmdev_ctx_t *ctx, int16_t *val);

/**
  * @brief  Angular rate sensor for OIS gyro or the EIS gyro channel.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Angular rate sensor for OIS gyro or the EIS gyro channel.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_eis_angular_rate_raw_get(const stmdev_ctx_t *ctx,
                                                int16_t *val);

/**
  * @brief  Linear acceleration sensor.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Linear acceleration sensor.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_acceleration_raw_get(const stmdev_ctx_t *ctx, int16_t *val);

/**
  * @brief  Linear acceleration sensor for Dual channel mode.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Linear acceleration sensor or Dual channel mode.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_dual_acceleration_raw_get(const stmdev_ctx_t *ctx, int16_t *val);

int32_t lsm6dsv16x_ois_dual_acceleration_raw_get(const stmdev_ctx_t *ctx,
                                                 int16_t *val);

/**
  * @brief  ah_qvar data output register.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      ah_qvar data output register.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ah_qvar_raw_get(const stmdev_ctx_t *ctx, int16_t *val);

/**
  * @brief  Difference in percentage of the effective ODR (and timestamp rate) with respect to the typical. Step: 0.13%. 8-bit format, 2's complement.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Difference in percentage of the effective ODR (and timestamp rate) with respect to the typical. Step: 0.13%. 8-bit format, 2's complement.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_odr_cal_reg_get(const stmdev_ctx_t *ctx, int8_t *val);

/**
  * @defgroup  Common Common Functions
  * @brief     This section groups common useful functions.
  * @{/
  *
  */

/**
  * @brief  Write buffer in a page.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Write buffer in a page.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ln_pg_write(const stmdev_ctx_t *ctx, uint16_t address,
                               uint8_t *buf, uint8_t len);

/**
  * @brief  Read buffer in a page.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Write buffer in a page.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ln_pg_read(const stmdev_ctx_t *ctx, uint16_t address, uint8_t *buf,
                              uint8_t len);

/**
  * @brief  Enable debug mode for embedded functions [set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0, 1
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_emb_function_dbg_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enable debug mode for embedded functions [get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0, 1
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_emb_function_dbg_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  DEN Data Enable (DEN) Configuration
  * @brief     This section groups all the functions concerning
  *            DEN functionality.
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_DEN_ACT_LOW  = 0x0,
  LSM6DSV16X_DEN_ACT_HIGH = 0x1,
} lsm6dsv16x_den_polarity_t;

/**
  * @brief  It changes the polarity of INT2 pin input trigger for data enable (DEN) or embedded functions.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      DEN_ACT_LOW, DEN_ACT_HIGH,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_den_polarity_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_den_polarity_t val);

/**
  * @brief  It changes the polarity of INT2 pin input trigger for data enable (DEN) or embedded functions.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      DEN_ACT_LOW, DEN_ACT_HIGH,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_den_polarity_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_den_polarity_t *val);

typedef struct
{
  uint8_t stamp_in_gy_data     : 1;
  uint8_t stamp_in_xl_data     : 1;
  uint8_t den_x                : 1;
  uint8_t den_y                : 1;
  uint8_t den_z                : 1;
  enum
  {
    LSM6DSV16X_DEN_NOT_DEFINED = 0x00,
    LSM6DSV16X_LEVEL_TRIGGER   = 0x02,
    LSM6DSV16X_LEVEL_LATCHED   = 0x03,
  } mode;
} lsm6dsv16x_den_conf_t;

/**
  * @brief  Data ENable (DEN) configuration.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Data ENable (DEN) configuration.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_den_conf_set(const stmdev_ctx_t *ctx, lsm6dsv16x_den_conf_t val);

/**
  * @brief  Data ENable (DEN) configuration.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Data ENable (DEN) configuration.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_den_conf_get(const stmdev_ctx_t *ctx, lsm6dsv16x_den_conf_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup EIS Electronic Image Stabilization (EIS) Configuration
  * @brief    Electronic Image Stabilization (EIS)
  * @{/
  *
  */

typedef enum
{
  LSM6DSV16X_EIS_125dps  = 0x0,
  LSM6DSV16X_EIS_250dps  = 0x1,
  LSM6DSV16X_EIS_500dps  = 0x2,
  LSM6DSV16X_EIS_1000dps = 0x3,
  LSM6DSV16X_EIS_2000dps = 0x4,
} lsm6dsv16x_eis_gy_full_scale_t;

/**
  * @brief  Gyroscope full-scale selection for EIS channel. WARNING: 4000dps will be available only if also User Interface chain is set to 4000dps[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      125dps, 250dps, 500dps, 1000dps, 2000dps, 4000dps,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_eis_gy_full_scale_set(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_eis_gy_full_scale_t val);

/**
  * @brief  Gyroscope full-scale selection for EIS channel. WARNING: 4000dps will be available only if also User Interface chain is set to 4000dps[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      125dps, 250dps, 500dps, 1000dps, 2000dps
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_eis_gy_full_scale_get(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_eis_gy_full_scale_t *val);

/**
  * @brief  Enables routing of gyroscope EIS outputs on SPI2 (OIS interface). The gyroscope data on SPI2 (OIS interface) cannot be read from User Interface (UI).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables routing of gyroscope EIS outputs on SPI2 (OIS interface). The gyroscope data on SPI2 (OIS interface) cannot be read from User Interface (UI).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_eis_gy_on_spi2_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables routing of gyroscope EIS outputs on SPI2 (OIS interface). The gyroscope data on SPI2 (OIS interface) cannot be read from User Interface (UI).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables routing of gyroscope EIS outputs on SPI2 (OIS interface). The gyroscope data on SPI2 (OIS interface) cannot be read from User Interface (UI).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_eis_gy_on_spi2_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_EIS_ODR_OFF = 0x0,
  LSM6DSV16X_EIS_1920Hz  = 0x1,
  LSM6DSV16X_EIS_960Hz   = 0x2,
} lsm6dsv16x_gy_eis_data_rate_t;

/**
  * @brief  Enables and selects the ODR of the gyroscope EIS channel.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      EIS_1920Hz, EIS_960Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_eis_data_rate_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_gy_eis_data_rate_t val);

/**
  * @brief  Enables and selects the ODR of the gyroscope EIS channel.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      EIS_1920Hz, EIS_960Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_gy_eis_data_rate_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_gy_eis_data_rate_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  FIFO FIFO Configuration
  * @brief     This section group all the functions concerning the FIFO usage
  * @{
  *
  */

/**
  * @brief  FIFO watermark threshold (1 LSb = TAG (1 Byte) + 1 sensor (6 Bytes) written in FIFO).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FIFO watermark threshold (1 LSb = TAG (1 Byte) + 1 sensor (6 Bytes) written in FIFO).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_watermark_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  FIFO watermark threshold (1 LSb = TAG (1 Byte) + 1 sensor (6 Bytes) written in FIFO).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FIFO watermark threshold (1 LSb = TAG (1 Byte) + 1 sensor (6 Bytes) written in FIFO).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_watermark_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  When dual channel mode is enabled, this function enables FSM-triggered batching in FIFO of accelerometer channel 2.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      When dual channel mode is enabled, this function enables FSM-triggered batching in FIFO of accelerometer channel 2.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_xl_dual_fsm_batch_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  When dual channel mode is enabled, this function enables FSM-triggered batching in FIFO of accelerometer channel 2.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      When dual channel mode is enabled, this function enables FSM-triggered batching in FIFO of accelerometer channel 2.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_xl_dual_fsm_batch_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_CMP_DISABLE = 0x0,
  LSM6DSV16X_CMP_8_TO_1  = 0x1,
  LSM6DSV16X_CMP_16_TO_1 = 0x2,
  LSM6DSV16X_CMP_32_TO_1 = 0x3,
} lsm6dsv16x_fifo_compress_algo_t;

/**
  * @brief  It configures the compression algorithm to write non-compressed data at each rate.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      CMP_DISABLE, CMP_ALWAYS, CMP_8_TO_1, CMP_16_TO_1, CMP_32_TO_1,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_compress_algo_set(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_fifo_compress_algo_t val);
/**
  * @brief  It configures the compression algorithm to write non-compressed data at each rate.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      CMP_DISABLE, CMP_ALWAYS, CMP_8_TO_1, CMP_16_TO_1, CMP_32_TO_1,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_compress_algo_get(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_fifo_compress_algo_t *val);

/**
  * @brief  Enables ODR CHANGE virtual sensor to be batched in FIFO.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables ODR CHANGE virtual sensor to be batched in FIFO.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_virtual_sens_odr_chg_set(const stmdev_ctx_t *ctx,
                                                 uint8_t val);
/**
  * @brief  Enables ODR CHANGE virtual sensor to be batched in FIFO.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables ODR CHANGE virtual sensor to be batched in FIFO.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_virtual_sens_odr_chg_get(const stmdev_ctx_t *ctx,
                                                 uint8_t *val);

/**
  * @brief  Enables/Disables compression algorithm runtime.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables/Disables compression algorithm runtime.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_compress_algo_real_time_set(const stmdev_ctx_t *ctx,
                                                    uint8_t val);
/**
  * @brief  Enables/Disables compression algorithm runtime.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables/Disables compression algorithm runtime.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_compress_algo_real_time_get(const stmdev_ctx_t *ctx,
                                                    uint8_t *val);

typedef enum
{
  LSM6DSV16X_FIFO_EV_WTM             = 0x0,
  LSM6DSV16X_FIFO_EV_FULL            = 0x1,
} lsm6dsv16x_fifo_event_t;

/**
  * @brief  Sensing chain FIFO stop values memorization at threshold level.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensing chain FIFO stop values memorization at threshold level.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_stop_on_wtm_set(const stmdev_ctx_t *ctx, lsm6dsv16x_fifo_event_t val);
/**
  * @brief  Sensing chain FIFO stop values memorization at threshold level.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensing chain FIFO stop values memorization at threshold level.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_stop_on_wtm_get(const stmdev_ctx_t *ctx, lsm6dsv16x_fifo_event_t *val);

typedef enum
{
  LSM6DSV16X_XL_NOT_BATCHED       = 0x0,
  LSM6DSV16X_XL_BATCHED_AT_1Hz875 = 0x1,
  LSM6DSV16X_XL_BATCHED_AT_7Hz5   = 0x2,
  LSM6DSV16X_XL_BATCHED_AT_15Hz   = 0x3,
  LSM6DSV16X_XL_BATCHED_AT_30Hz   = 0x4,
  LSM6DSV16X_XL_BATCHED_AT_60Hz   = 0x5,
  LSM6DSV16X_XL_BATCHED_AT_120Hz  = 0x6,
  LSM6DSV16X_XL_BATCHED_AT_240Hz  = 0x7,
  LSM6DSV16X_XL_BATCHED_AT_480Hz  = 0x8,
  LSM6DSV16X_XL_BATCHED_AT_960Hz  = 0x9,
  LSM6DSV16X_XL_BATCHED_AT_1920Hz = 0xa,
  LSM6DSV16X_XL_BATCHED_AT_3840Hz = 0xb,
  LSM6DSV16X_XL_BATCHED_AT_7680Hz = 0xc,
} lsm6dsv16x_fifo_xl_batch_t;
/**
  * @brief  Selects Batch Data Rate (write frequency in FIFO) for accelerometer data.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_NOT_BATCHED, XL_BATCHED_AT_1Hz875, XL_BATCHED_AT_7Hz5, XL_BATCHED_AT_15Hz, XL_BATCHED_AT_30Hz, XL_BATCHED_AT_60Hz, XL_BATCHED_AT_120Hz, XL_BATCHED_AT_240Hz, XL_BATCHED_AT_480Hz, XL_BATCHED_AT_960Hz, XL_BATCHED_AT_1920Hz, XL_BATCHED_AT_3840Hz, XL_BATCHED_AT_7680Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_xl_batch_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_fifo_xl_batch_t val);

/**
  * @brief  Selects Batch Data Rate (write frequency in FIFO) for accelerometer data.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_NOT_BATCHED, XL_BATCHED_AT_1Hz875, XL_BATCHED_AT_7Hz5, XL_BATCHED_AT_15Hz, XL_BATCHED_AT_30Hz, XL_BATCHED_AT_60Hz, XL_BATCHED_AT_120Hz, XL_BATCHED_AT_240Hz, XL_BATCHED_AT_480Hz, XL_BATCHED_AT_960Hz, XL_BATCHED_AT_1920Hz, XL_BATCHED_AT_3840Hz, XL_BATCHED_AT_7680Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_xl_batch_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_fifo_xl_batch_t *val);

typedef enum
{
  LSM6DSV16X_GY_NOT_BATCHED       = 0x0,
  LSM6DSV16X_GY_BATCHED_AT_1Hz875 = 0x1,
  LSM6DSV16X_GY_BATCHED_AT_7Hz5   = 0x2,
  LSM6DSV16X_GY_BATCHED_AT_15Hz   = 0x3,
  LSM6DSV16X_GY_BATCHED_AT_30Hz   = 0x4,
  LSM6DSV16X_GY_BATCHED_AT_60Hz   = 0x5,
  LSM6DSV16X_GY_BATCHED_AT_120Hz  = 0x6,
  LSM6DSV16X_GY_BATCHED_AT_240Hz  = 0x7,
  LSM6DSV16X_GY_BATCHED_AT_480Hz  = 0x8,
  LSM6DSV16X_GY_BATCHED_AT_960Hz  = 0x9,
  LSM6DSV16X_GY_BATCHED_AT_1920Hz = 0xa,
  LSM6DSV16X_GY_BATCHED_AT_3840Hz = 0xb,
  LSM6DSV16X_GY_BATCHED_AT_7680Hz = 0xc,
} lsm6dsv16x_fifo_gy_batch_t;
/**
  * @brief  Selects Batch Data Rate (write frequency in FIFO) for gyroscope data.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_NOT_BATCHED, GY_BATCHED_AT_1Hz875, GY_BATCHED_AT_7Hz5, GY_BATCHED_AT_15Hz, GY_BATCHED_AT_30Hz, GY_BATCHED_AT_60Hz, GY_BATCHED_AT_120Hz, GY_BATCHED_AT_240Hz, GY_BATCHED_AT_480Hz, GY_BATCHED_AT_960Hz, GY_BATCHED_AT_1920Hz, GY_BATCHED_AT_3840Hz, GY_BATCHED_AT_7680Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_gy_batch_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_fifo_gy_batch_t val);

/**
  * @brief  Selects Batch Data Rate (write frequency in FIFO) for gyroscope data.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_NOT_BATCHED, GY_BATCHED_AT_1Hz875, GY_BATCHED_AT_7Hz5, GY_BATCHED_AT_15Hz, GY_BATCHED_AT_30Hz, GY_BATCHED_AT_60Hz, GY_BATCHED_AT_120Hz, GY_BATCHED_AT_240Hz, GY_BATCHED_AT_480Hz, GY_BATCHED_AT_960Hz, GY_BATCHED_AT_1920Hz, GY_BATCHED_AT_3840Hz, GY_BATCHED_AT_7680Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_gy_batch_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_fifo_gy_batch_t *val);

typedef enum
{
  LSM6DSV16X_BYPASS_MODE             = 0x0,
  LSM6DSV16X_FIFO_MODE               = 0x1,
  LSM6DSV16X_STREAM_WTM_TO_FULL_MODE = 0x2,
  LSM6DSV16X_STREAM_TO_FIFO_MODE     = 0x3,
  LSM6DSV16X_BYPASS_TO_STREAM_MODE   = 0x4,
  LSM6DSV16X_STREAM_MODE             = 0x6,
  LSM6DSV16X_BYPASS_TO_FIFO_MODE     = 0x7,
} lsm6dsv16x_fifo_mode_t;
/**
  * @brief  FIFO mode selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      BYPASS_MODE, FIFO_MODE, STREAM_WTM_TO_FULL_MODE, STREAM_TO_FIFO_MODE, BYPASS_TO_STREAM_MODE, STREAM_MODE, BYPASS_TO_FIFO_MODE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_fifo_mode_t val);
/**
  * @brief  FIFO mode selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      BYPASS_MODE, FIFO_MODE, STREAM_WTM_TO_FULL_MODE, STREAM_TO_FIFO_MODE, BYPASS_TO_STREAM_MODE, STREAM_MODE, BYPASS_TO_FIFO_MODE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_mode_get(const stmdev_ctx_t *ctx,
                                 lsm6dsv16x_fifo_mode_t *val);

/**
  * @brief  Enables FIFO batching of EIS gyroscope output values.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables FIFO batching of EIS gyroscope output values.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_gy_eis_batch_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Enables FIFO batching of EIS gyroscope output values.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables FIFO batching of EIS gyroscope output values.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_gy_eis_batch_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_TEMP_NOT_BATCHED       = 0x0,
  LSM6DSV16X_TEMP_BATCHED_AT_1Hz875 = 0x1,
  LSM6DSV16X_TEMP_BATCHED_AT_15Hz   = 0x2,
  LSM6DSV16X_TEMP_BATCHED_AT_60Hz   = 0x3,
} lsm6dsv16x_fifo_temp_batch_t;

/**
  * @brief  Selects batch data rate (write frequency in FIFO) for temperature data.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      TEMP_NOT_BATCHED, TEMP_BATCHED_AT_1Hz875, TEMP_BATCHED_AT_15Hz, TEMP_BATCHED_AT_60Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_temp_batch_set(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_fifo_temp_batch_t val);

/**
  * @brief  Selects batch data rate (write frequency in FIFO) for temperature data.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      TEMP_NOT_BATCHED, TEMP_BATCHED_AT_1Hz875, TEMP_BATCHED_AT_15Hz, TEMP_BATCHED_AT_60Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_temp_batch_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_fifo_temp_batch_t *val);

typedef enum
{
  LSM6DSV16X_TMSTMP_NOT_BATCHED = 0x0,
  LSM6DSV16X_TMSTMP_DEC_1       = 0x1,
  LSM6DSV16X_TMSTMP_DEC_8       = 0x2,
  LSM6DSV16X_TMSTMP_DEC_32      = 0x3,
} lsm6dsv16x_fifo_timestamp_batch_t;
/**
  * @brief  Selects decimation for timestamp batching in FIFO. Write rate will be the maximum rate between XL and GYRO BDR divided by decimation decoder.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      TMSTMP_NOT_BATCHED, TMSTMP_DEC_1, TMSTMP_DEC_8, TMSTMP_DEC_32,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_timestamp_batch_set(const stmdev_ctx_t *ctx,
                                            lsm6dsv16x_fifo_timestamp_batch_t val);
/**
  * @brief  Selects decimation for timestamp batching in FIFO. Write rate will be the maximum rate between XL and GYRO BDR divided by decimation decoder.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      TMSTMP_NOT_BATCHED, TMSTMP_DEC_1, TMSTMP_DEC_8, TMSTMP_DEC_32,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_timestamp_batch_get(const stmdev_ctx_t *ctx,
                                            lsm6dsv16x_fifo_timestamp_batch_t *val);

/**
  * @brief  The threshold for the internal counter of batch events. When this counter reaches the threshold, the counter is reset and the interrupt flag is set to 1.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      The threshold for the internal counter of batch events. When this counter reaches the threshold, the counter is reset and the interrupt flag is set to 1.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_batch_counter_threshold_set(const stmdev_ctx_t *ctx,
                                                    uint16_t val);
/**
  * @brief  The threshold for the internal counter of batch events. When this counter reaches the threshold, the counter is reset and the interrupt flag is set to 1.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      The threshold for the internal counter of batch events. When this counter reaches the threshold, the counter is reset and the interrupt flag is set to 1.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_batch_counter_threshold_get(const stmdev_ctx_t *ctx,
                                                    uint16_t *val);

typedef enum
{
  LSM6DSV16X_XL_BATCH_EVENT     = 0x0,
  LSM6DSV16X_GY_BATCH_EVENT     = 0x1,
  LSM6DSV16X_GY_EIS_BATCH_EVENT = 0x2,
} lsm6dsv16x_fifo_batch_cnt_event_t;

/**
  * @brief  Selects the trigger for the internal counter of batch events between the accelerometer, gyroscope and EIS gyroscope.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_BATCH_EVENT, GY_BATCH_EVENT, GY_EIS_BATCH_EVENT,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_batch_cnt_event_set(const stmdev_ctx_t *ctx,
                                            lsm6dsv16x_fifo_batch_cnt_event_t val);

/**
  * @brief  Selects the trigger for the internal counter of batch events between the accelerometer, gyroscope and EIS gyroscope.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_BATCH_EVENT, GY_BATCH_EVENT, GY_EIS_BATCH_EVENT,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_batch_cnt_event_get(const stmdev_ctx_t *ctx,
                                            lsm6dsv16x_fifo_batch_cnt_event_t *val);

/**
  * @brief  Sets the batching of the second accelerometer channel to the FIFO.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      PROPERTY_ENABLE, PROPERTY_DISABLE
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_xl_dual_channel_batch_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Gets the batching of the second accelerometer channel to the FIFO.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      PROPERTY_ENABLE, PROPERTY_DISABLE
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_xl_dual_channel_batch_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  uint16_t fifo_level          : 9;
  uint8_t fifo_bdr             : 1;
  uint8_t fifo_full            : 1;
  uint8_t fifo_ovr             : 1;
  uint8_t fifo_th              : 1;
} lsm6dsv16x_fifo_status_t;

/**
  * @brief  FIFO status.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_fifo_status_t struct
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_status_get(const stmdev_ctx_t *ctx,
                                   lsm6dsv16x_fifo_status_t *val);

/* Accel data format in FIFO */
typedef struct
{
  int16_t axis[3];
} lsm6dsv16x_fifo_xl;

/* Temperature data format in FIFO */
typedef struct
{
  uint16_t temperature;
} lsm6dsv16x_fifo_temperature;

/* Timestamp  format in FIFO */
typedef struct
{
  uint32_t timestamp;
} lsm6dsv16x_fifo_timestamp;

/* Step counter data format in FIFO */
typedef struct
{
  uint16_t steps;
  uint32_t timestamp;
} lsm6dsv16x_fifo_step_counter;

typedef enum
{
  LSM6DSV16X_FIFO_EMPTY                    = 0x0,
  LSM6DSV16X_GY_NC_TAG                     = 0x1,
  LSM6DSV16X_XL_NC_TAG                     = 0x2,
  LSM6DSV16X_TEMPERATURE_TAG               = 0x3,
  LSM6DSV16X_TIMESTAMP_TAG                 = 0x4,
  LSM6DSV16X_CFG_CHANGE_TAG                = 0x5,
  LSM6DSV16X_XL_NC_T_2_TAG                 = 0x6,
  LSM6DSV16X_XL_NC_T_1_TAG                 = 0x7,
  LSM6DSV16X_XL_2XC_TAG                    = 0x8,
  LSM6DSV16X_XL_3XC_TAG                    = 0x9,
  LSM6DSV16X_GY_NC_T_2_TAG                 = 0xA,
  LSM6DSV16X_GY_NC_T_1_TAG                 = 0xB,
  LSM6DSV16X_GY_2XC_TAG                    = 0xC,
  LSM6DSV16X_GY_3XC_TAG                    = 0xD,
  LSM6DSV16X_SENSORHUB_SLAVE0_TAG          = 0xE,
  LSM6DSV16X_SENSORHUB_SLAVE1_TAG          = 0xF,
  LSM6DSV16X_SENSORHUB_SLAVE2_TAG          = 0x10,
  LSM6DSV16X_SENSORHUB_SLAVE3_TAG          = 0x11,
  LSM6DSV16X_STEP_COUNTER_TAG              = 0x12,
  LSM6DSV16X_SFLP_GAME_ROTATION_VECTOR_TAG = 0x13,
  LSM6DSV16X_SFLP_GYROSCOPE_BIAS_TAG       = 0x16,
  LSM6DSV16X_SFLP_GRAVITY_VECTOR_TAG       = 0x17,
  LSM6DSV16X_SENSORHUB_NACK_TAG            = 0x19,
  LSM6DSV16X_MLC_RESULT_TAG                = 0x1A,
  LSM6DSV16X_MLC_FILTER                    = 0x1B,
  LSM6DSV16X_MLC_FEATURE                   = 0x1C,
  LSM6DSV16X_XL_DUAL_CORE                  = 0x1D,
  LSM6DSV16X_GY_ENHANCED_EIS               = 0x1E,
} lsm6dsv16x_fifo_tag;

typedef struct
{
  uint8_t tag  : 5;
  uint8_t cnt  : 2;
  uint8_t rsvd : 1;
  uint8_t data[6];
} lsm6dsv16x_fifo_out_raw_t;

/**
  * @brief  FIFO data output[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_fifo_out_raw_t
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_out_raw_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_fifo_out_raw_t *val);

/**
  * @brief  Batching in FIFO buffer of step counter value.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Batching in FIFO buffer of step counter value.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_stpcnt_batch_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Batching in FIFO buffer of step counter value.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Batching in FIFO buffer of step counter value.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_stpcnt_batch_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Batching in FIFO buffer of machine learning core results.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Batching in FIFO buffer of machine learning core results.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_mlc_batch_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Batching in FIFO buffer of machine learning core results.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Batching in FIFO buffer of machine learning core results.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_mlc_batch_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Enables batching in FIFO buffer of machine learning core filters and features.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables batching in FIFO buffer of machine learning core filters and features.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_mlc_filt_batch_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables batching in FIFO buffer of machine learning core filters and features.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables batching in FIFO buffer of machine learning core filters and features.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_mlc_filt_batch_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Enable FIFO data batching of slave idx.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable FIFO data batching of slave idx.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_sh_batch_slave_set(const stmdev_ctx_t *ctx, uint8_t idx, uint8_t val);

/**
  * @brief  Enable FIFO data batching of slave idx.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable FIFO data batching of slave idx.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_sh_batch_slave_get(const stmdev_ctx_t *ctx, uint8_t idx, uint8_t *val);

typedef struct
{
  uint8_t game_rotation        : 1;
  uint8_t gravity              : 1;
  uint8_t gbias                : 1;
} lsm6dsv16x_fifo_sflp_raw_t;

/**
  * @brief  Batching in FIFO buffer of SFLP.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Batching in FIFO buffer of SFLP values.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_sflp_batch_set(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_fifo_sflp_raw_t val);

/**
  * @brief  Batching in FIFO buffer of SFLP.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Batching in FIFO buffer of SFLP values.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fifo_sflp_batch_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_fifo_sflp_raw_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  Filters Filter Configuration
  * @brief     This section group all the functions concerning the
  *            filters configuration
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_AUTO          = 0x0,
  LSM6DSV16X_ALWAYS_ACTIVE = 0x1,
} lsm6dsv16x_filt_anti_spike_t;

/**
  * @brief  Protocol anti-spike filters.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      AUTO, ALWAYS_ACTIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_anti_spike_set(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_filt_anti_spike_t val);

/**
  * @brief  Protocol anti-spike filters.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      AUTO, ALWAYS_ACTIVE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_anti_spike_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_filt_anti_spike_t *val);

typedef struct
{
  uint8_t drdy                 : 1;
  uint8_t ois_drdy             : 1;
  uint8_t irq_xl               : 1;
  uint8_t irq_g                : 1;
} lsm6dsv16x_filt_settling_mask_t;

/**
  * @brief  It masks DRDY and Interrupts RQ until filter settling ends.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It masks DRDY and Interrupts RQ until filter settling ends.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_settling_mask_set(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_filt_settling_mask_t val);

/**
  * @brief  It masks DRDY and Interrupts RQ until filter settling ends.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It masks DRDY and Interrupts RQ until filter settling ends.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_settling_mask_get(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_filt_settling_mask_t *val);

typedef struct
{
  uint8_t ois_drdy             : 1;
} lsm6dsv16x_filt_ois_settling_mask_t;

/**
  * @brief  It masks DRDY and Interrupts RQ until filter settling ends.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It masks DRDY and Interrupts RQ until filter settling ends from OIS interface.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_ois_settling_mask_set(const stmdev_ctx_t *ctx,
                                              lsm6dsv16x_filt_ois_settling_mask_t val);

/**
  * @brief  It masks DRDY and Interrupts RQ until filter settling ends.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It masks DRDY and Interrupts RQ until filter settling ends.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_ois_settling_mask_get(const stmdev_ctx_t *ctx,
                                              lsm6dsv16x_filt_ois_settling_mask_t *val);

typedef enum
{
  LSM6DSV16X_GY_ULTRA_LIGHT   = 0x0,
  LSM6DSV16X_GY_VERY_LIGHT    = 0x1,
  LSM6DSV16X_GY_LIGHT         = 0x2,
  LSM6DSV16X_GY_MEDIUM        = 0x3,
  LSM6DSV16X_GY_STRONG        = 0x4,
  LSM6DSV16X_GY_VERY_STRONG   = 0x5,
  LSM6DSV16X_GY_AGGRESSIVE    = 0x6,
  LSM6DSV16X_GY_XTREME        = 0x7,
} lsm6dsv16x_filt_gy_lp1_bandwidth_t;

/**
  * @brief  Gyroscope low-pass filter (LPF1) bandwidth selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_ULTRA_LIGHT, GY_VERY_LIGHT, GY_LIGHT, GY_MEDIUM, GY_STRONG, GY_VERY_STRONG, GY_AGGRESSIVE, GY_XTREME,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_lp1_bandwidth_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_filt_gy_lp1_bandwidth_t val);

/**
  * @brief  Gyroscope low-pass filter (LPF1) bandwidth selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GY_ULTRA_LIGHT, GY_VERY_LIGHT, GY_LIGHT, GY_MEDIUM, GY_STRONG, GY_VERY_STRONG, GY_AGGRESSIVE, GY_XTREME,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_lp1_bandwidth_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_filt_gy_lp1_bandwidth_t *val);

/**
  * @brief  It enables gyroscope digital LPF1 filter. If the OIS chain is disabled, the bandwidth can be selected through LPF1_G_BW.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It enables gyroscope digital LPF1 filter. If the OIS chain is disabled, the bandwidth can be selected through LPF1_G_BW.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_lp1_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  It enables gyroscope digital LPF1 filter. If the OIS chain is disabled, the bandwidth can be selected through LPF1_G_BW.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      It enables gyroscope digital LPF1 filter. If the OIS chain is disabled, the bandwidth can be selected through LPF1_G_BW.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_lp1_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_XL_ULTRA_LIGHT = 0x0,
  LSM6DSV16X_XL_VERY_LIGHT  = 0x1,
  LSM6DSV16X_XL_LIGHT       = 0x2,
  LSM6DSV16X_XL_MEDIUM      = 0x3,
  LSM6DSV16X_XL_STRONG      = 0x4,
  LSM6DSV16X_XL_VERY_STRONG = 0x5,
  LSM6DSV16X_XL_AGGRESSIVE  = 0x6,
  LSM6DSV16X_XL_XTREME      = 0x7,
} lsm6dsv16x_filt_xl_lp2_bandwidth_t;

/**
  * @brief  Accelerometer LPF2 and high pass filter configuration and cutoff setting.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ULTRA_LIGHT, XL_VERY_LIGHT, XL_LIGHT, XL_MEDIUM, XL_STRONG, XL_VERY_STRONG, XL_AGGRESSIVE, XL_XTREME,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_lp2_bandwidth_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_filt_xl_lp2_bandwidth_t val);

/**
  * @brief  Accelerometer LPF2 and high pass filter configuration and cutoff setting.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_ULTRA_LIGHT, XL_VERY_LIGHT, XL_LIGHT, XL_MEDIUM, XL_STRONG, XL_VERY_STRONG, XL_AGGRESSIVE, XL_XTREME,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_lp2_bandwidth_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_filt_xl_lp2_bandwidth_t *val);

/**
  * @brief  Enable accelerometer LPS2 (Low Pass Filter 2) filtering stage.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable accelerometer LPS2 (Low Pass Filter 2) filtering stage.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_lp2_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enable accelerometer LPS2 (Low Pass Filter 2) filtering stage.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable accelerometer LPS2 (Low Pass Filter 2) filtering stage.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_lp2_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Accelerometer slope filter / high-pass filter selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Accelerometer slope filter / high-pass filter selection.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_hp_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Accelerometer slope filter / high-pass filter selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Accelerometer slope filter / high-pass filter selection.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_hp_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Enables accelerometer LPF2 and HPF fast-settling mode. The filter sets the first sample.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables accelerometer LPF2 and HPF fast-settling mode. The filter sets the first sample.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_fast_settling_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables accelerometer LPF2 and HPF fast-settling mode. The filter sets the first sample.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables accelerometer LPF2 and HPF fast-settling mode. The filter sets the first sample.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_fast_settling_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_HP_MD_NORMAL    = 0x0,
  LSM6DSV16X_HP_MD_REFERENCE = 0x1,
} lsm6dsv16x_filt_xl_hp_mode_t;

/**
  * @brief  Accelerometer high-pass filter mode.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      HP_MD_NORMAL, HP_MD_REFERENCE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_hp_mode_set(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_filt_xl_hp_mode_t val);

/**
  * @brief  Accelerometer high-pass filter mode.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      HP_MD_NORMAL, HP_MD_REFERENCE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_hp_mode_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_filt_xl_hp_mode_t *val);

typedef enum
{
  LSM6DSV16X_WK_FEED_SLOPE          = 0x0,
  LSM6DSV16X_WK_FEED_HIGH_PASS      = 0x1,
  LSM6DSV16X_WK_FEED_LP_WITH_OFFSET = 0x2,
} lsm6dsv16x_filt_wkup_act_feed_t;

/**
  * @brief  HPF or SLOPE filter selection on wake-up and Activity/Inactivity functions.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      WK_FEED_SLOPE, WK_FEED_HIGH_PASS, WK_FEED_LP_WITH_OFFSET,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_wkup_act_feed_set(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_filt_wkup_act_feed_t val);

/**
  * @brief  HPF or SLOPE filter selection on wake-up and Activity/Inactivity functions.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      WK_FEED_SLOPE, WK_FEED_HIGH_PASS, WK_FEED_LP_WITH_OFFSET,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_wkup_act_feed_get(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_filt_wkup_act_feed_t *val);

/**
  * @brief  Mask hw function triggers when xl is settling.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0 or 1,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */

int32_t lsm6dsv16x_mask_trigger_xl_settl_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Mask hw function triggers when xl is settling.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0 or 1,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mask_trigger_xl_settl_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_SIXD_FEED_ODR_DIV_2 = 0x0,
  LSM6DSV16X_SIXD_FEED_LOW_PASS  = 0x1,
} lsm6dsv16x_filt_sixd_feed_t;

/**
  * @brief  LPF2 filter on 6D (sixd) function selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SIXD_FEED_ODR_DIV_2, SIXD_FEED_LOW_PASS,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_sixd_feed_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_filt_sixd_feed_t val);

/**
  * @brief  LPF2 filter on 6D (sixd) function selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SIXD_FEED_ODR_DIV_2, SIXD_FEED_LOW_PASS,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_sixd_feed_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_filt_sixd_feed_t *val);

typedef enum
{
  LSM6DSV16X_EIS_LP_NORMAL = 0x0,
  LSM6DSV16X_EIS_LP_LIGHT  = 0x1,
} lsm6dsv16x_filt_gy_eis_lp_bandwidth_t;

/**
  * @brief  Gyroscope digital LPF_EIS filter bandwidth selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      EIS_LP_NORMAL, EIS_LP_LIGHT,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_eis_lp_bandwidth_set(const stmdev_ctx_t *ctx,
                                                lsm6dsv16x_filt_gy_eis_lp_bandwidth_t val);

/**
  * @brief  Gyroscope digital LPF_EIS filter bandwidth selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      EIS_LP_NORMAL, EIS_LP_LIGHT,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_eis_lp_bandwidth_get(const stmdev_ctx_t *ctx,
                                                lsm6dsv16x_filt_gy_eis_lp_bandwidth_t *val);

typedef enum
{
  LSM6DSV16X_OIS_GY_LP_NORMAL     = 0x0,
  LSM6DSV16X_OIS_GY_LP_STRONG     = 0x1,
  LSM6DSV16X_OIS_GY_LP_AGGRESSIVE = 0x2,
  LSM6DSV16X_OIS_GY_LP_LIGHT      = 0x3,
} lsm6dsv16x_filt_gy_ois_lp_bandwidth_t;

/**
  * @brief  Gyroscope OIS digital LPF1 filter bandwidth selection. This function works also on OIS interface (SPI2_CTRL2_OIS = UI_CTRL2_OIS).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_GY_LP_NORMAL, OIS_GY_LP_STRONG, OIS_GY_LP_AGGRESSIVE, OIS_GY_LP_LIGHT,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_ois_lp_bandwidth_set(const stmdev_ctx_t *ctx,
                                                lsm6dsv16x_filt_gy_ois_lp_bandwidth_t val);

/**
  * @brief  Gyroscope OIS digital LPF1 filter bandwidth selection. This function works also on OIS interface (SPI2_CTRL2_OIS = UI_CTRL2_OIS).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_GY_LP_NORMAL, OIS_GY_LP_STRONG, OIS_GY_LP_AGGRESSIVE, OIS_GY_LP_LIGHT,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_gy_ois_lp_bandwidth_get(const stmdev_ctx_t *ctx,
                                                lsm6dsv16x_filt_gy_ois_lp_bandwidth_t *val);

typedef enum
{
  LSM6DSV16X_OIS_XL_LP_ULTRA_LIGHT = 0x0,
  LSM6DSV16X_OIS_XL_LP_VERY_LIGHT  = 0x1,
  LSM6DSV16X_OIS_XL_LP_LIGHT       = 0x2,
  LSM6DSV16X_OIS_XL_LP_NORMAL      = 0x3,
  LSM6DSV16X_OIS_XL_LP_STRONG      = 0x4,
  LSM6DSV16X_OIS_XL_LP_VERY_STRONG = 0x5,
  LSM6DSV16X_OIS_XL_LP_AGGRESSIVE  = 0x6,
  LSM6DSV16X_OIS_XL_LP_XTREME      = 0x7,
} lsm6dsv16x_filt_xl_ois_lp_bandwidth_t;

/**
  * @brief  Selects accelerometer OIS channel bandwidth. This function works also on OIS interface (SPI2_CTRL3_OIS = UI_CTRL3_OIS).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_XL_LP_ULTRA_LIGHT, OIS_XL_LP_VERY_LIGHT, OIS_XL_LP_LIGHT, OIS_XL_LP_NORMAL, OIS_XL_LP_STRONG, OIS_XL_LP_VERY_STRONG, OIS_XL_LP_AGGRESSIVE, OIS_XL_LP_XTREME,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_ois_lp_bandwidth_set(const stmdev_ctx_t *ctx,
                                                lsm6dsv16x_filt_xl_ois_lp_bandwidth_t val);

/**
  * @brief  Selects accelerometer OIS channel bandwidth. This function works also on OIS interface (SPI2_CTRL3_OIS = UI_CTRL3_OIS).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_XL_LP_ULTRA_LIGHT, OIS_XL_LP_VERY_LIGHT, OIS_XL_LP_LIGHT, OIS_XL_LP_NORMAL, OIS_XL_LP_STRONG, OIS_XL_LP_VERY_STRONG, OIS_XL_LP_AGGRESSIVE, OIS_XL_LP_XTREME,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_filt_xl_ois_lp_bandwidth_get(const stmdev_ctx_t *ctx,
                                                lsm6dsv16x_filt_xl_ois_lp_bandwidth_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  FSM Finite State Machine (FSM) Configuration
  * @brief     This section groups all the functions that manage the
  *            state_machine.
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_PROTECT_CTRL_REGS = 0x0,
  LSM6DSV16X_WRITE_CTRL_REG    = 0x1,
} lsm6dsv16x_fsm_permission_t;

/**
  * @brief  Enables the control of the CTRL registers to FSM (FSM can change some configurations of the device autonomously).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      PROTECT_CTRL_REGS, WRITE_CTRL_REG,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_permission_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_fsm_permission_t val);

/**
  * @brief  Enables the control of the CTRL registers to FSM (FSM can change some configurations of the device autonomously).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      PROTECT_CTRL_REGS, WRITE_CTRL_REG,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_permission_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_fsm_permission_t *val);

/**
  * @brief  Get the FSM permission status
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0: All reg writable from std if - 1: some regs are under FSM control.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_permission_status(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  uint8_t fsm1_en              : 1;
  uint8_t fsm2_en              : 1;
  uint8_t fsm3_en              : 1;
  uint8_t fsm4_en              : 1;
  uint8_t fsm5_en              : 1;
  uint8_t fsm6_en              : 1;
  uint8_t fsm7_en              : 1;
  uint8_t fsm8_en              : 1;
} lsm6dsv16x_fsm_mode_t;

/**
  * @brief  Enable Finite State Machine (FSM) feature.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable Finite State Machine (FSM) feature.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_fsm_mode_t val);

/**
  * @brief  Enable Finite State Machine (FSM) feature.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable Finite State Machine (FSM) feature.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_mode_get(const stmdev_ctx_t *ctx, lsm6dsv16x_fsm_mode_t *val);

/**
  * @brief  FSM long counter status register. Long counter value is an unsigned integer value (16-bit format).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM long counter status register. Long counter value is an unsigned integer value (16-bit format).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_long_cnt_set(const stmdev_ctx_t *ctx, uint16_t val);

/**
  * @brief  FSM long counter status register. Long counter value is an unsigned integer value (16-bit format).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM long counter status register. Long counter value is an unsigned integer value (16-bit format).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_long_cnt_get(const stmdev_ctx_t *ctx, uint16_t *val);


typedef struct
{
  uint8_t fsm_outs1;
  uint8_t fsm_outs2;
  uint8_t fsm_outs3;
  uint8_t fsm_outs4;
  uint8_t fsm_outs5;
  uint8_t fsm_outs6;
  uint8_t fsm_outs7;
  uint8_t fsm_outs8;
} lsm6dsv16x_fsm_out_t;

/**
  * @brief  FSM output registers[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM output registers
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_out_get(const stmdev_ctx_t *ctx, lsm6dsv16x_fsm_out_t *val);

typedef enum
{
  LSM6DSV16X_FSM_15Hz  = 0x0,
  LSM6DSV16X_FSM_30Hz  = 0x1,
  LSM6DSV16X_FSM_60Hz  = 0x2,
  LSM6DSV16X_FSM_120Hz = 0x3,
  LSM6DSV16X_FSM_240Hz = 0x4,
  LSM6DSV16X_FSM_480Hz = 0x5,
  LSM6DSV16X_FSM_960Hz = 0x6,
} lsm6dsv16x_fsm_data_rate_t;

/**
  * @brief  Finite State Machine Output Data Rate (ODR) configuration.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM_15Hz, FSM_30Hz, FSM_60Hz, FSM_120Hz, FSM_240Hz, FSM_480Hz, FSM_960Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_data_rate_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_fsm_data_rate_t val);

/**
  * @brief  Finite State Machine Output Data Rate (ODR) configuration.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM_15Hz, FSM_30Hz, FSM_60Hz, FSM_120Hz, FSM_240Hz, FSM_480Hz, FSM_960Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_data_rate_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_fsm_data_rate_t *val);

/**
  * @brief  External sensor sensitivity value register for the Finite State Machine (r/w). This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits). Default value is 0x1624 (when using an external magnetometer this value corresponds to 0.0015 gauss/LSB).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor sensitivity value register for the Finite State Machine (r/w). This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits). Default value is 0x1624 (when using an external magnetometer this value corresponds to 0.0015 gauss/LSB).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_sensitivity_set(const stmdev_ctx_t *ctx,
                                                uint16_t val);

/**
  * @brief  External sensor sensitivity value register for the Finite State Machine (r/w). This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits). Default value is 0x1624 (when using an external magnetometer this value corresponds to 0.0015 gauss/LSB).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor sensitivity value register for the Finite State Machine (r/w). This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits). Default value is 0x1624 (when using an external magnetometer this value corresponds to 0.0015 gauss/LSB).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_sensitivity_get(const stmdev_ctx_t *ctx,
                                                uint16_t *val);

typedef struct
{
  uint16_t z;
  uint16_t y;
  uint16_t x;
} lsm6dsv16x_xl_fsm_ext_sens_offset_t;

/**
  * @brief  External sensor offsets (X,Y,Z). The values are expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor offsets (X,Y,Z). The values are expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_offset_set(const stmdev_ctx_t *ctx,
                                           lsm6dsv16x_xl_fsm_ext_sens_offset_t val);

/**
  * @brief  External sensor offsets (X,Y,Z). The values are expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor offsets (X,Y,Z). The values are expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_offset_get(const stmdev_ctx_t *ctx,
                                           lsm6dsv16x_xl_fsm_ext_sens_offset_t *val);

typedef struct
{
  uint16_t xx;
  uint16_t xy;
  uint16_t xz;
  uint16_t yy;
  uint16_t yz;
  uint16_t zz;
} lsm6dsv16x_xl_fsm_ext_sens_matrix_t;

/**
  * @brief  External sensor transformation matrix. The value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor transformation matrix. The value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_matrix_set(const stmdev_ctx_t *ctx,
                                           lsm6dsv16x_xl_fsm_ext_sens_matrix_t val);

/**
  * @brief  External sensor transformation matrix. The value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor transformation matrix. The value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_matrix_get(const stmdev_ctx_t *ctx,
                                           lsm6dsv16x_xl_fsm_ext_sens_matrix_t *val);

typedef enum
{
  LSM6DSV16X_Z_EQ_Y     = 0x0,
  LSM6DSV16X_Z_EQ_MIN_Y = 0x1,
  LSM6DSV16X_Z_EQ_X     = 0x2,
  LSM6DSV16X_Z_EQ_MIN_X = 0x3,
  LSM6DSV16X_Z_EQ_MIN_Z = 0x4,
  LSM6DSV16X_Z_EQ_Z     = 0x5,
} lsm6dsv16x_fsm_ext_sens_z_orient_t;

/**
  * @brief  External sensor z-axis coordinates rotation.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Z_EQ_Y, Z_EQ_MIN_Y, Z_EQ_X, Z_EQ_MIN_X, Z_EQ_MIN_Z, Z_EQ_Z,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_z_orient_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_fsm_ext_sens_z_orient_t val);

/**
  * @brief  External sensor z-axis coordinates rotation.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Z_EQ_Y, Z_EQ_MIN_Y, Z_EQ_X, Z_EQ_MIN_X, Z_EQ_MIN_Z, Z_EQ_Z,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_z_orient_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_fsm_ext_sens_z_orient_t *val);

typedef enum
{
  LSM6DSV16X_Y_EQ_Y     = 0x0,
  LSM6DSV16X_Y_EQ_MIN_Y = 0x1,
  LSM6DSV16X_Y_EQ_X     = 0x2,
  LSM6DSV16X_Y_EQ_MIN_X = 0x3,
  LSM6DSV16X_Y_EQ_MIN_Z = 0x4,
  LSM6DSV16X_Y_EQ_Z     = 0x5,
} lsm6dsv16x_fsm_ext_sens_y_orient_t;

/**
  * @brief  External sensor Y-axis coordinates rotation.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Y_EQ_Y, Y_EQ_MIN_Y, Y_EQ_X, Y_EQ_MIN_X, Y_EQ_MIN_Z, Y_EQ_Z,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_y_orient_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_fsm_ext_sens_y_orient_t val);

/**
  * @brief  External sensor Y-axis coordinates rotation.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Y_EQ_Y, Y_EQ_MIN_Y, Y_EQ_X, Y_EQ_MIN_X, Y_EQ_MIN_Z, Y_EQ_Z,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_y_orient_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_fsm_ext_sens_y_orient_t *val);

typedef enum
{
  LSM6DSV16X_X_EQ_Y     = 0x0,
  LSM6DSV16X_X_EQ_MIN_Y = 0x1,
  LSM6DSV16X_X_EQ_X     = 0x2,
  LSM6DSV16X_X_EQ_MIN_X = 0x3,
  LSM6DSV16X_X_EQ_MIN_Z = 0x4,
  LSM6DSV16X_X_EQ_Z     = 0x5,
} lsm6dsv16x_fsm_ext_sens_x_orient_t;

/**
  * @brief  External sensor X-axis coordinates rotation.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      X_EQ_Y, X_EQ_MIN_Y, X_EQ_X, X_EQ_MIN_X, X_EQ_MIN_Z, X_EQ_Z,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_x_orient_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_fsm_ext_sens_x_orient_t val);

/**
  * @brief  External sensor X-axis coordinates rotation.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      X_EQ_Y, X_EQ_MIN_Y, X_EQ_X, X_EQ_MIN_X, X_EQ_MIN_Z, X_EQ_Z,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_ext_sens_x_orient_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_fsm_ext_sens_x_orient_t *val);

/**
  * @brief  FSM long counter timeout. The long counter timeout value is an unsigned integer value (16-bit format). When the long counter value reached this value, the FSM generates an interrupt.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM long counter timeout. The long counter timeout value is an unsigned integer value (16-bit format). When the long counter value reached this value, the FSM generates an interrupt.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_long_cnt_timeout_set(const stmdev_ctx_t *ctx, uint16_t val);

/**
  * @brief  FSM long counter timeout. The long counter timeout value is an unsigned integer value (16-bit format). When the long counter value reached this value, the FSM generates an interrupt.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM long counter timeout. The long counter timeout value is an unsigned integer value (16-bit format). When the long counter value reached this value, the FSM generates an interrupt.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_long_cnt_timeout_get(const stmdev_ctx_t *ctx, uint16_t *val);

/**
  * @brief  FSM number of programs.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM number of programs.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_number_of_programs_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  FSM number of programs.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM number of programs.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_number_of_programs_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  FSM start address. First available address is 0x35C.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM start address. First available address is 0x35C.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_start_address_set(const stmdev_ctx_t *ctx, uint16_t val);

/**
  * @brief  FSM start address. First available address is 0x35C.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      FSM start address. First available address is 0x35C.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_fsm_start_address_get(const stmdev_ctx_t *ctx, uint16_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  FF Free fall Configuration
  * @brief     This section group all the functions concerning the free
  *            fall detection.
  * @{
  *
  */

/**
  * @brief  Time windows configuration for Free Fall detection 1 LSB = 1/ODR_XL time[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time windows configuration for Free Fall detection 1 LSB = 1/ODR_XL time
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ff_time_windows_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Time windows configuration for Free Fall detection 1 LSB = 1/ODR_XL time[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time windows configuration for Free Fall detection 1 LSB = 1/ODR_XL time
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ff_time_windows_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_156_mg = 0x0,
  LSM6DSV16X_219_mg = 0x1,
  LSM6DSV16X_250_mg = 0x2,
  LSM6DSV16X_312_mg = 0x3,
  LSM6DSV16X_344_mg = 0x4,
  LSM6DSV16X_406_mg = 0x5,
  LSM6DSV16X_469_mg = 0x6,
  LSM6DSV16X_500_mg = 0x7,
} lsm6dsv16x_ff_thresholds_t;
/**
  * @brief  Free fall threshold setting.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      156_mg, 219_mg, 250_mg, 312_mg, 344_mg, 406_mg, 469_mg, 500_mg,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ff_thresholds_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_ff_thresholds_t val);
/**
  * @brief  Free fall threshold setting.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      156_mg, 219_mg, 250_mg, 312_mg, 344_mg, 406_mg, 469_mg, 500_mg,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ff_thresholds_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_ff_thresholds_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  MLC Machine Learning Core (MLC) Configuration
  * @brief      This section group all the functions concerning the
  *             usage of Machine Learning Core
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_MLC_OFF                             = 0x0,
  LSM6DSV16X_MLC_ON                              = 0x1,
  LSM6DSV16X_MLC_ON_BEFORE_FSM                   = 0x2,
} lsm6dsv16x_mlc_mode_t;

/**
  * @brief  It enables Machine Learning Core feature (MLC).
  *         When the Machine Learning Core is enabled the Finite State Machine (FSM)
  *         programs are executed before executing the MLC algorithms.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      MLC_OFF, MLC_ON, MLC_BEFORE_FSM,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_set(const stmdev_ctx_t *ctx, lsm6dsv16x_mlc_mode_t val);

/**
  * @brief  It enables Machine Learning Core feature (MLC).
  *         When the Machine Learning Core is enabled the Finite State Machine (FSM)
  *         programs are executed before executing the MLC algorithms.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      MLC_OFF, MLC_ON, MLC_BEFORE_FSM,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_get(const stmdev_ctx_t *ctx, lsm6dsv16x_mlc_mode_t *val);

typedef enum
{
  LSM6DSV16X_MLC_15Hz  = 0x0,
  LSM6DSV16X_MLC_30Hz  = 0x1,
  LSM6DSV16X_MLC_60Hz  = 0x2,
  LSM6DSV16X_MLC_120Hz = 0x3,
  LSM6DSV16X_MLC_240Hz = 0x4,
  LSM6DSV16X_MLC_480Hz = 0x5,
  LSM6DSV16X_MLC_960Hz = 0x6,
} lsm6dsv16x_mlc_data_rate_t;

/**
  * @brief  Machine Learning Core Output Data Rate (ODR) configuration.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      MLC_15Hz, MLC_30Hz, MLC_60Hz, MLC_120Hz, MLC_240Hz, MLC_480Hz, MLC_960Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_data_rate_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_mlc_data_rate_t val);

/**
  * @brief  Machine Learning Core Output Data Rate (ODR) configuration.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      MLC_15Hz, MLC_30Hz, MLC_60Hz, MLC_120Hz, MLC_240Hz, MLC_480Hz, MLC_960Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_data_rate_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_mlc_data_rate_t *val);

typedef struct
{
  uint8_t mlc1_src;
  uint8_t mlc2_src;
  uint8_t mlc3_src;
  uint8_t mlc4_src;
} lsm6dsv16x_mlc_out_t;

/**
  * @brief  Output value of all MLC decision trees.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Output value of all MLC decision trees.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_out_get(const stmdev_ctx_t *ctx, lsm6dsv16x_mlc_out_t *val);

/**
  * @brief  External sensor sensitivity value register for the Machine Learning Core. This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).Default value is 0x3C00 (when using an external magnetometer this value corresponds to 1 gauss/LSB).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor sensitivity value register for the Machine Learning Core. This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).Default value is 0x3C00 (when using an external magnetometer this value corresponds to 1 gauss/LSB).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_ext_sens_sensitivity_set(const stmdev_ctx_t *ctx,
                                                uint16_t val);

/**
  * @brief  External sensor sensitivity value register for the Machine Learning Core. This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).Default value is 0x3C00 (when using an external magnetometer this value corresponds to 1 gauss/LSB).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      External sensor sensitivity value register for the Machine Learning Core. This register corresponds to the conversion value of the external sensor. The register value is expressed as half-precision floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent bits; F: 10 fraction bits).Default value is 0x3C00 (when using an external magnetometer this value corresponds to 1 gauss/LSB).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_mlc_ext_sens_sensitivity_get(const stmdev_ctx_t *ctx,
                                                uint16_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  OIS Optical Image Stabilization (OIS) Configuration
  * @brief     This section groups all the functions concerning
  *            Optical Image Stabilization (OIS).
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_OIS_CTRL_FROM_OIS = 0x0,
  LSM6DSV16X_OIS_CTRL_FROM_UI  = 0x1,
} lsm6dsv16x_ois_ctrl_mode_t;

/**
  * @brief  Enable the full control of OIS configurations from the UI (User Interface).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_CTRL_FROM_OIS, OIS_CTRL_FROM_UI,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_ctrl_mode_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_ois_ctrl_mode_t val);

/**
  * @brief  Enable the full control of OIS configurations from the UI (User Interface).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_CTRL_FROM_OIS, OIS_CTRL_FROM_UI,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_ctrl_mode_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_ois_ctrl_mode_t *val);

/**
  * @brief  Resets the control registers of OIS from the UI (User Interface)[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Resets the control registers of OIS from the UI (User Interface)
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_reset_set(const stmdev_ctx_t *ctx, int8_t val);

/**
  * @brief  Resets the control registers of OIS from the UI (User Interface)[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Resets the control registers of OIS from the UI (User Interface)
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_reset_get(const stmdev_ctx_t *ctx, int8_t *val);

/**
  * @brief  Enable/disable pull up on OIS interface.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable/disable pull up on OIS interface.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_interface_pull_up_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enable/disable pull up on OIS interface.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable/disable pull up on OIS interface.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_interface_pull_up_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  uint8_t ack                  : 1;
  uint8_t req                  : 1;
} lsm6dsv16x_ois_handshake_t;
/**
  * @brief  Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_handshake_from_ui_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_ois_handshake_t val);

/**
  * @brief  Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_handshake_from_ui_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_ois_handshake_t *val);

/**
  * @brief  Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_handshake_from_ois_set(const stmdev_ctx_t *ctx,
                                              lsm6dsv16x_ois_handshake_t val);

/**
  * @brief  Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Handshake for (User Interface) UI / (OIS interface) SPI2 shared registers. ACK: This bit acknowledges the handshake. If the secondary interface is not accessing the shared registers, this bit is set to 1 by the device and the R/W operation on the UI_SPI2_SHARED registers is allowed on the primary interface. REQ: This bit is used by the primary interface master to request access to the UI_SPI2_SHARED registers. When the R/W operation is finished, the master must reset this bit.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_handshake_from_ois_get(const stmdev_ctx_t *ctx,
                                              lsm6dsv16x_ois_handshake_t *val);

/**
  * @brief  User interface (UI) / SPI2 (OIS) shared registers[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      User interface (UI) / SPI2 (OIS) shared registers
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_shared_set(const stmdev_ctx_t *ctx, uint8_t val[6]);

/**
  * @brief  User interface (UI) / SPI2 (OIS) shared registers[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      User interface (UI) / SPI2 (OIS) shared registers
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_shared_get(const stmdev_ctx_t *ctx, uint8_t val[6]);

/**
  * @brief  In User Interface (UI) full control mode, enables SPI2 (OIS Interface) for reading OIS data. This function works also on OIS (UI_CTRL1_OIS = SPI2_CTRL1_OIS).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      In User Interface (UI) full control mode, enables SPI2 (OIS Interface) for reading OIS data.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_on_spi2_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  In User Interface (UI) full control mode, enables SPI2 (OIS Interface) for reading OIS data. This function works also on OIS (UI_CTRL1_OIS = SPI2_CTRL1_OIS).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      In User Interface (UI) full control mode, enables SPI2 (OIS Interface) for reading OIS data.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_on_spi2_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  uint8_t gy                   : 1;
  uint8_t xl                   : 1;
} lsm6dsv16x_ois_chain_t;
/**
  * @brief  Enables gyroscope/accelerometer OIS chain. This function works also on OIS (UI_CTRL1_OIS = SPI2_CTRL1_OIS).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables gyroscope/accelerometer OIS chain.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_chain_set(const stmdev_ctx_t *ctx, lsm6dsv16x_ois_chain_t val);
/**
  * @brief  Enables gyroscope/accelerometer OIS chain.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables gyroscope/accelerometer OIS chain.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_chain_get(const stmdev_ctx_t *ctx,
                                 lsm6dsv16x_ois_chain_t *val);

typedef enum
{
  LSM6DSV16X_OIS_125dps  = 0x0,
  LSM6DSV16X_OIS_250dps  = 0x1,
  LSM6DSV16X_OIS_500dps  = 0x2,
  LSM6DSV16X_OIS_1000dps = 0x3,
  LSM6DSV16X_OIS_2000dps = 0x4,
} lsm6dsv16x_ois_gy_full_scale_t;
/**
  * @brief  Gyroscope OIS full-scale selection[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_125dps, OIS_250dps, OIS_500dps, OIS_1000dps, OIS_2000dps,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_gy_full_scale_set(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_ois_gy_full_scale_t val);
/**
  * @brief  Gyroscope OIS full-scale selection[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      OIS_125dps, OIS_250dps, OIS_500dps, OIS_1000dps, OIS_2000dps,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_gy_full_scale_get(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_ois_gy_full_scale_t *val);

typedef enum
{
  LSM6DSV16X_OIS_2g  = 0x0,
  LSM6DSV16X_OIS_4g  = 0x1,
  LSM6DSV16X_OIS_8g  = 0x2,
  LSM6DSV16X_OIS_16g = 0x3,
} lsm6dsv16x_ois_xl_full_scale_t;
/**
  * @brief  Selects accelerometer OIS channel full-scale.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_ois_xl_full_scale_t
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_xl_full_scale_set(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_ois_xl_full_scale_t val);
/**
  * @brief  Selects accelerometer OIS channel full-scale.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      lsm6dsv16x_ois_xl_full_scale_t
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ois_xl_full_scale_get(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_ois_xl_full_scale_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  6D_4D 6D (and 4D) Orientation Configuration
  * @brief     This section groups all the functions concerning six position
  *            detection (6D).
  * @{
  *
  */
typedef enum
{
  LSM6DSV16X_DEG_80 = 0x0,
  LSM6DSV16X_DEG_70 = 0x1,
  LSM6DSV16X_DEG_60 = 0x2,
  LSM6DSV16X_DEG_50 = 0x3,
} lsm6dsv16x_6d_threshold_t;
/**
  * @brief  Threshold for 4D/6D function.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      DEG_80, DEG_70, DEG_60, DEG_50,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_6d_threshold_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_6d_threshold_t val);
/**
  * @brief  Threshold for 4D/6D function.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      DEG_80, DEG_70, DEG_60, DEG_50,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_6d_threshold_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_6d_threshold_t *val);

/**
  * @brief  4D orientation detection enable. Z-axis position detection is disabled.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      4D orientation detection enable. Z-axis position detection is disabled.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_4d_mode_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  4D orientation detection enable. Z-axis position detection is disabled.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      4D orientation detection enable. Z-axis position detection is disabled.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_4d_mode_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  AH_QVAR AH_QVAR Configuration
  * @brief     This section group all the functions concerning the
  *            usage of AH_QVAR
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_2400MOhm = 0x0,
  LSM6DSV16X_730MOhm  = 0x1,
  LSM6DSV16X_300MOhm  = 0x2,
  LSM6DSV16X_255MOhm  = 0x3,
} lsm6dsv16x_ah_qvar_zin_t;
/**
  * @brief  Configures the equivalent input impedance of the AH_QVAR buffers.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      2400MOhm, 730MOhm, 300MOhm, 255MOhm,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ah_qvar_zin_set(const stmdev_ctx_t *ctx,
                                   lsm6dsv16x_ah_qvar_zin_t val);
/**
  * @brief  Configures the equivalent input impedance of the AH_QVAR buffers.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      2400MOhm, 730MOhm, 300MOhm, 255MOhm,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ah_qvar_zin_get(const stmdev_ctx_t *ctx,
                                   lsm6dsv16x_ah_qvar_zin_t *val);

typedef struct
{
  uint8_t ah_qvar_en           : 1;
} lsm6dsv16x_ah_qvar_mode_t;
/**
  * @brief  Enables AH_QVAR chain. When this bit is set to ‘1’, the AH_QVAR buffers are connected to the SDx/AH1/Qvar1 and SCx/AH2/Qvar2 pins. Before setting this bit to 1, the accelerometer and gyroscope sensor have to be configured in power-down mode.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables AH_QVAR chain. When this bit is set to ‘1’, the AH_QVAR buffers are connected to the SDx/AH1/Qvar1 and SCx/AH2/Qvar2 pins. Before setting this bit to 1, the accelerometer and gyroscope sensor have to be configured in power-down mode.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ah_qvar_mode_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_ah_qvar_mode_t val);

/**
  * @brief  Enables AH_QVAR chain. When this bit is set to ‘1’, the AH_QVAR buffers are connected to the SDx/AH1/Qvar1 and SCx/AH2/Qvar2 pins. Before setting this bit to 1, the accelerometer and gyroscope sensor have to be configured in power-down mode.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables AH_QVAR chain. When this bit is set to ‘1’, the AH_QVAR buffers are connected to the SDx/AH1/Qvar1 and SCx/AH2/Qvar2 pins. Before setting this bit to 1, the accelerometer and gyroscope sensor have to be configured in power-down mode.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ah_qvar_mode_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_ah_qvar_mode_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  I3C SenseWire (I3C) Configuration
  * @brief     This section group all the functions concerning the
  *            usage of SenseWire (I3C)
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_SW_RST_DYN_ADDRESS_RST = 0x0,
  LSM6DSV16X_I3C_GLOBAL_RST         = 0x1,
} lsm6dsv16x_i3c_reset_mode_t;
/**
  * @brief  Selects the action the device will perform after "Reset whole chip" I3C pattern.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SW_RST_DYN_ADDRESS_RST, GLOBAL_RST,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_i3c_reset_mode_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_i3c_reset_mode_t val);
/**
  * @brief  Selects the action the device will perform after "Reset whole chip" I3C pattern.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SW_RST_DYN_ADDRESS_RST, I3C_GLOBAL_RST,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_i3c_reset_mode_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_i3c_reset_mode_t *val);

/**
  * @brief  Enable/Disable INT pin when I3C is used.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0: disabled, 1: enabled
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_i3c_int_en_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Enable/Disable INT pin when I3C is used.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      0: disabled, 1: enabled
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_i3c_int_en_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_IBI_2us  = 0x0,
  LSM6DSV16X_IBI_50us = 0x1,
  LSM6DSV16X_IBI_1ms  = 0x2,
  LSM6DSV16X_IBI_25ms = 0x3,
} lsm6dsv16x_i3c_ibi_time_t;
/**
  * @brief  Select the us activity time for IBI (In-Band Interrupt) with I3C[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      IBI_2us, IBI_50us, IBI_1ms, IBI_25ms,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_i3c_ibi_time_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_i3c_ibi_time_t val);
/**
  * @brief  Select the us activity time for IBI (In-Band Interrupt) with I3C[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      IBI_2us, IBI_50us, IBI_1ms, IBI_25ms,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_i3c_ibi_time_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_i3c_ibi_time_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  SH Sensor hub Configuration
  * @brief     This section groups all the functions that manage the
  *            sensor hub.
  * @{
  *
  */

/**
  * @brief  Sensor Hub master I2C pull-up enable.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensor Hub master I2C pull-up enable.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_master_interface_pull_up_set(const stmdev_ctx_t *ctx,
                                                   uint8_t val);
/**
  * @brief  Sensor Hub master I2C pull-up enable.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensor Hub master I2C pull-up enable.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_master_interface_pull_up_get(const stmdev_ctx_t *ctx,
                                                   uint8_t *val);

/**
  * @brief  Sensor hub output registers.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensor hub output registers.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_read_data_raw_get(const stmdev_ctx_t *ctx, uint8_t *val,
                                        uint8_t len);

typedef enum
{
  LSM6DSV16X_SLV_0       = 0x0,
  LSM6DSV16X_SLV_0_1     = 0x1,
  LSM6DSV16X_SLV_0_1_2   = 0x2,
  LSM6DSV16X_SLV_0_1_2_3 = 0x3,
} lsm6dsv16x_sh_slave_connected_t;
/**
  * @brief  Number of external sensors to be read by the sensor hub.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SLV_0, SLV_0_1, SLV_0_1_2, SLV_0_1_2_3,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_slave_connected_set(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_sh_slave_connected_t val);
/**
  * @brief  Number of external sensors to be read by the sensor hub.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SLV_0, SLV_0_1, SLV_0_1_2, SLV_0_1_2_3,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_slave_connected_get(const stmdev_ctx_t *ctx,
                                          lsm6dsv16x_sh_slave_connected_t *val);

/**
  * @brief  Sensor hub I2C master enable.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensor hub I2C master enable.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_master_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Sensor hub I2C master enable.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Sensor hub I2C master enable.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_master_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  I2C interface pass-through.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      I2C interface pass-through.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_pass_through_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  I2C interface pass-through.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      I2C interface pass-through.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_pass_through_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_SH_TRG_XL_GY_DRDY = 0x0,
  LSM6DSV16X_SH_TRIG_INT2      = 0x1,
} lsm6dsv16x_sh_syncro_mode_t;
/**
  * @brief  Sensor hub trigger signal selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SH_TRG_XL_GY_DRDY, SH_TRIG_INT2,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_syncro_mode_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_sh_syncro_mode_t val);
/**
  * @brief  Sensor hub trigger signal selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SH_TRG_XL_GY_DRDY, SH_TRIG_INT2,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_syncro_mode_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_sh_syncro_mode_t *val);

typedef enum
{
  LSM6DSV16X_EACH_SH_CYCLE    = 0x0,
  LSM6DSV16X_ONLY_FIRST_CYCLE = 0x1,
} lsm6dsv16x_sh_write_mode_t;
/**
  * @brief  Slave 0 write operation is performed only at the first sensor hub cycle.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      EACH_SH_CYCLE, ONLY_FIRST_CYCLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_write_mode_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_sh_write_mode_t val);
/**
  * @brief  Slave 0 write operation is performed only at the first sensor hub cycle.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      EACH_SH_CYCLE, ONLY_FIRST_CYCLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_write_mode_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_sh_write_mode_t *val);

/**
  * @brief  Reset Master logic and output registers. Must be set to ‘1’ and then set it to ‘0’.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Reset Master logic and output registers. Must be set to ‘1’ and then set it to ‘0’.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_reset_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Reset Master logic and output registers. Must be set to ‘1’ and then set it to ‘0’.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Reset Master logic and output registers. Must be set to ‘1’ and then set it to ‘0’.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_reset_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  uint8_t   slv0_add;
  uint8_t   slv0_subadd;
  uint8_t   slv0_data;
} lsm6dsv16x_sh_cfg_write_t;
/**
  * @brief  Configure slave 0 for perform a write.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      a structure that contain
  *                      - uint8_t slv1_add;    8 bit i2c device address
  *                      - uint8_t slv1_subadd; 8 bit register device address
  *                      - uint8_t slv1_data;   8 bit data to write
  * @retval             interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_cfg_write(const stmdev_ctx_t *ctx,
                                lsm6dsv16x_sh_cfg_write_t *val);
typedef enum
{
  LSM6DSV16X_SH_15Hz  = 0x1,
  LSM6DSV16X_SH_30Hz  = 0x2,
  LSM6DSV16X_SH_60Hz  = 0x3,
  LSM6DSV16X_SH_120Hz = 0x4,
  LSM6DSV16X_SH_240Hz = 0x5,
  LSM6DSV16X_SH_480Hz = 0x6,
} lsm6dsv16x_sh_data_rate_t;
/**
  * @brief  Rate at which the master communicates.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SH_15Hz, SH_30Hz, SH_60Hz, SH_120Hz, SH_240Hz, SH_480Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_data_rate_set(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_sh_data_rate_t val);
/**
  * @brief  Rate at which the master communicates.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SH_15Hz, SH_30Hz, SH_60Hz, SH_120Hz, SH_240Hz, SH_480Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_data_rate_get(const stmdev_ctx_t *ctx,
                                    lsm6dsv16x_sh_data_rate_t *val);

typedef struct
{
  uint8_t   slv_add;
  uint8_t   slv_subadd;
  uint8_t   slv_len;
} lsm6dsv16x_sh_cfg_read_t;
/**
  * @brief  Configure slave idx for perform a read.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Structure that contain
  *                      - uint8_t slv_add;    8 bit i2c device address
  *                      - uint8_t slv_subadd; 8 bit register device address
  *                      - uint8_t slv_len;    num of bit to read
  * @retval             interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_slv_cfg_read(const stmdev_ctx_t *ctx, uint8_t idx,
                                   lsm6dsv16x_sh_cfg_read_t *val);

/**
  * @brief  Sensor hub source register.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      union of registers from STATUS_MASTER to
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sh_status_get(const stmdev_ctx_t *ctx,
                                 lsm6dsv16x_status_master_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  UI Serial interfaces Configuration
  * @brief     This section groups all the functions concerning
  *            serial interfaces management (not auxiliary)
  * @{
  *
  */

/**
  * @brief  Enables pull-up on SDO pin of UI (User Interface).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables pull-up on SDO pin of UI (User Interface).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ui_sdo_pull_up_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables pull-up on SDO pin of UI (User Interface).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables pull-up on SDO pin of UI (User Interface).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ui_sdo_pull_up_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_I2C_I3C_ENABLE  = 0x0,
  LSM6DSV16X_I2C_I3C_DISABLE = 0x1,
} lsm6dsv16x_ui_i2c_i3c_mode_t;

/**
  * @brief  Disables I2C and I3C on UI (User Interface).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      I2C_I3C_ENABLE, I2C_I3C_DISABLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ui_i2c_i3c_mode_set(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_ui_i2c_i3c_mode_t val);

/**
  * @brief  Disables I2C and I3C on UI (User Interface).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      I2C_I3C_ENABLE, I2C_I3C_DISABLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ui_i2c_i3c_mode_get(const stmdev_ctx_t *ctx,
                                       lsm6dsv16x_ui_i2c_i3c_mode_t *val);

typedef enum
{
  LSM6DSV16X_SPI_4_WIRE = 0x0,
  LSM6DSV16X_SPI_3_WIRE = 0x1,
} lsm6dsv16x_spi_mode_t;

/**
  * @brief  SPI Serial Interface Mode selection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SPI_4_WIRE, SPI_3_WIRE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_spi_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_spi_mode_t val);

/**
  * @brief  SPI Serial Interface Mode selection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SPI_4_WIRE, SPI_3_WIRE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_spi_mode_get(const stmdev_ctx_t *ctx, lsm6dsv16x_spi_mode_t *val);

/**
  * @brief  Enables pull-up on SDA pin.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables pull-up on SDA pin.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ui_sda_pull_up_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables pull-up on SDA pin.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables pull-up on SDA pin.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_ui_sda_pull_up_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef enum
{
  LSM6DSV16X_SPI2_4_WIRE = 0x0,
  LSM6DSV16X_SPI2_3_WIRE = 0x1,
} lsm6dsv16x_spi2_mode_t;

/**
  * @brief  SPI2 (OIS Inteface) Serial Interface Mode selection. This function works also on OIS (UI_CTRL1_OIS = SPI2_CTRL1_OIS).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SPI2_4_WIRE, SPI2_3_WIRE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_spi2_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_spi2_mode_t val);

/**
  * @brief  SPI2 (OIS Inteface) Serial Interface Mode selection. This function works also on OIS (UI_CTRL1_OIS = SPI2_CTRL1_OIS).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SPI2_4_WIRE, SPI2_3_WIRE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_spi2_mode_get(const stmdev_ctx_t *ctx,
                                 lsm6dsv16x_spi2_mode_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  Sigmot Significant motion detection Configuration
  * @brief     This section groups all the functions that manage the
  *            significant motion detection.
  * @{
  *
  */

/**
  * @brief  Enables significant motion detection function.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables significant motion detection function.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sigmot_mode_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enables significant motion detection function.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables significant motion detection function.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sigmot_mode_get(const stmdev_ctx_t *ctx, uint8_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  Pedometer Step Counter (Pedometer) Configuration
  * @brief     This section groups all the functions that manage pedometer.
  * @{
  *
  */

typedef struct
{
  uint8_t step_counter_enable  : 1;
  uint8_t false_step_rej       : 1;
} lsm6dsv16x_stpcnt_mode_t;

/**
  * @brief  Step counter mode[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Step counter mode
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_mode_set(const stmdev_ctx_t *ctx,
                                   lsm6dsv16x_stpcnt_mode_t val);

/**
  * @brief  Step counter mode[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      false_step_rej, step_counter, step_detector,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_mode_get(const stmdev_ctx_t *ctx,
                                   lsm6dsv16x_stpcnt_mode_t *val);

/**
  * @brief  Step counter output, number of detected steps.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Step counter output, number of detected steps.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_steps_get(const stmdev_ctx_t *ctx, uint16_t *val);

/**
  * @brief  Reset step counter.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Reset step counter.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_rst_step_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Reset step counter.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Reset step counter.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_rst_step_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Pedometer debounce configuration.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Pedometer debounce configuration.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_debounce_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Pedometer debounce configuration.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Pedometer debounce configuration.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_debounce_get(const stmdev_ctx_t *ctx, uint8_t *val);

/**
  * @brief  Time period register for step detection on delta time.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time period register for step detection on delta time.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_period_set(const stmdev_ctx_t *ctx, uint16_t val);

/**
  * @brief  Time period register for step detection on delta time.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time period register for step detection on delta time.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_stpcnt_period_get(const stmdev_ctx_t *ctx, uint16_t *val);

/**
  * @}
  *
  */

/**
  * @defgroup  SFLP Sensor Fusion Low Power (SFLP) Configuration
  * @brief     This section groups all the functions that manage pedometer.
  * @{
  *
  */

/**
  * @brief  Enable SFLP Game Rotation Vector (6x).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable/Disable game rotation value (0/1).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sflp_game_rotation_set(const stmdev_ctx_t *ctx, uint8_t val);

/**
  * @brief  Enable SFLP Game Rotation Vector (6x).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable/Disable game rotation value (0/1).
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sflp_game_rotation_get(const stmdev_ctx_t *ctx, uint8_t *val);

typedef struct
{
  float_t gbias_x; /* dps */
  float_t gbias_y; /* dps */
  float_t gbias_z; /* dps */
} lsm6dsv16x_sflp_gbias_t;

/**
  * @brief  SFLP GBIAS value. The register value is expressed as half-precision
  *         floating-point format: SEEEEEFFFFFFFFFF (S: 1 sign bit; E: 5 exponent
  *          bits; F: 10 fraction bits).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      GBIAS x/y/z val.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sflp_game_gbias_set(const stmdev_ctx_t *ctx,
                                       const lsm6dsv16x_sflp_gbias_t *val);

typedef enum
{
  LSM6DSV16X_SFLP_15Hz  = 0x0,
  LSM6DSV16X_SFLP_30Hz  = 0x1,
  LSM6DSV16X_SFLP_60Hz  = 0x2,
  LSM6DSV16X_SFLP_120Hz = 0x3,
  LSM6DSV16X_SFLP_240Hz = 0x4,
  LSM6DSV16X_SFLP_480Hz = 0x5,
} lsm6dsv16x_sflp_data_rate_t;

/**
  * @brief  SFLP Data Rate (ODR) configuration.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SFLP_15Hz, SFLP_30Hz, SFLP_60Hz, SFLP_120Hz, SFLP_240Hz, SFLP_480Hz
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sflp_data_rate_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_sflp_data_rate_t val);

/**
  * @brief  SFLP Data Rate (ODR) configuration.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SFLP_15Hz, SFLP_30Hz, SFLP_60Hz, SFLP_120Hz, SFLP_240Hz, SFLP_480Hz
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_sflp_data_rate_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_sflp_data_rate_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  DTap Tap/Double Tap Configuration
  * @brief     This section groups all the functions that manage the
  *            tap and double tap event generation.
  * @{
  *
  */

typedef struct
{
  uint8_t tap_x_en             : 1;
  uint8_t tap_y_en             : 1;
  uint8_t tap_z_en             : 1;
} lsm6dsv16x_tap_detection_t;

/**
  * @brief  Enable axis for Tap - Double Tap detection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable axis for Tap - Double Tap detection.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_detection_set(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_tap_detection_t val);
/**
  * @brief  Enable axis for Tap - Double Tap detection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enable axis for Tap - Double Tap detection.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_detection_get(const stmdev_ctx_t *ctx,
                                     lsm6dsv16x_tap_detection_t *val);

typedef struct
{
  uint8_t x                    : 5;
  uint8_t y                    : 5;
  uint8_t z                    : 5;
} lsm6dsv16x_tap_thresholds_t;
/**
  * @brief  axis Tap - Double Tap recognition thresholds.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      axis Tap - Double Tap recognition thresholds.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_thresholds_set(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_tap_thresholds_t val);
/**
  * @brief  axis Tap - Double Tap recognition thresholds.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      axis Tap - Double Tap recognition thresholds.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_thresholds_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_tap_thresholds_t *val);

typedef enum
{
  LSM6DSV16X_XYZ  = 0x0,
  LSM6DSV16X_YXZ  = 0x1,
  LSM6DSV16X_XZY  = 0x2,
  LSM6DSV16X_ZYX  = 0x3,
  LSM6DSV16X_YZX  = 0x5,
  LSM6DSV16X_ZXY  = 0x6,
} lsm6dsv16x_tap_axis_priority_t;
/**
  * @brief  Selection of axis priority for TAP detection.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XYZ , YXZ , XZY, ZYX , YZX , ZXY ,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_axis_priority_set(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_tap_axis_priority_t val);
/**
  * @brief  Selection of axis priority for TAP detection.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XYZ , YXZ , XZY, ZYX , YZX , ZXY ,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_axis_priority_get(const stmdev_ctx_t *ctx,
                                         lsm6dsv16x_tap_axis_priority_t *val);

typedef struct
{
  uint8_t shock                : 2;
  uint8_t quiet                : 2;
  uint8_t tap_gap              : 4;
} lsm6dsv16x_tap_time_windows_t;

/**
  * @brief  Time windows configuration for Tap - Double Tap SHOCK, QUIET, DUR : SHOCK Maximum duration is the maximum time of an overthreshold signal detection to be recognized as a tap event. The default value of these bits is 00b which corresponds to 4/ODR_XL time. If the SHOCK bits are set to a different value, 1LSB corresponds to 8/ODR_XL time. QUIET Expected quiet time after a tap detection. Quiet time is the time after the first detected tap in which there must not be any overthreshold event. The default value of these bits is 00b which corresponds to 2/ODR_XL time. If the QUIET bits are set to a different value, 1LSB corresponds to 4/ODR_XL time. DUR Duration of maximum time gap for double tap recognition. When double tap recognition is enabled, this register expresses the maximum time between two consecutive detected taps to determine a double tap event. The default value of these bits is 0000b which corresponds to 16/ODR_XL time. If the DUR_[3:0] bits are set to a different value, 1LSB corresponds to 32/ODR_XL time.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time windows configuration for Tap - Double Tap SHOCK, QUIET, DUR : SHOCK Maximum duration is the maximum time of an overthreshold signal detection to be recognized as a tap event. The default value of these bits is 00b which corresponds to 4/ODR_XL time. If the SHOCK bits are set to a different value, 1LSB corresponds to 8/ODR_XL time. QUIET Expected quiet time after a tap detection. Quiet time is the time after the first detected tap in which there must not be any overthreshold event. The default value of these bits is 00b which corresponds to 2/ODR_XL time. If the QUIET bits are set to a different value, 1LSB corresponds to 4/ODR_XL time. DUR Duration of maximum time gap for double tap recognition. When double tap recognition is enabled, this register expresses the maximum time between two consecutive detected taps to determine a double tap event. The default value of these bits is 0000b which corresponds to 16/ODR_XL time. If the DUR_[3:0] bits are set to a different value, 1LSB corresponds to 32/ODR_XL time.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_time_windows_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_tap_time_windows_t val);

/**
  * @brief  Time windows configuration for Tap - Double Tap SHOCK, QUIET, DUR : SHOCK Maximum duration is the maximum time of an overthreshold signal detection to be recognized as a tap event. The default value of these bits is 00b which corresponds to 4/ODR_XL time. If the SHOCK bits are set to a different value, 1LSB corresponds to 8/ODR_XL time. QUIET Expected quiet time after a tap detection. Quiet time is the time after the first detected tap in which there must not be any overthreshold event. The default value of these bits is 00b which corresponds to 2/ODR_XL time. If the QUIET bits are set to a different value, 1LSB corresponds to 4/ODR_XL time. DUR Duration of maximum time gap for double tap recognition. When double tap recognition is enabled, this register expresses the maximum time between two consecutive detected taps to determine a double tap event. The default value of these bits is 0000b which corresponds to 16/ODR_XL time. If the DUR_[3:0] bits are set to a different value, 1LSB corresponds to 32/ODR_XL time.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time windows configuration for Tap - Double Tap SHOCK, QUIET, DUR : SHOCK Maximum duration is the maximum time of an overthreshold signal detection to be recognized as a tap event. The default value of these bits is 00b which corresponds to 4/ODR_XL time. If the SHOCK bits are set to a different value, 1LSB corresponds to 8/ODR_XL time. QUIET Expected quiet time after a tap detection. Quiet time is the time after the first detected tap in which there must not be any overthreshold event. The default value of these bits is 00b which corresponds to 2/ODR_XL time. If the QUIET bits are set to a different value, 1LSB corresponds to 4/ODR_XL time. DUR Duration of maximum time gap for double tap recognition. When double tap recognition is enabled, this register expresses the maximum time between two consecutive detected taps to determine a double tap event. The default value of these bits is 0000b which corresponds to 16/ODR_XL time. If the DUR_[3:0] bits are set to a different value, 1LSB corresponds to 32/ODR_XL time.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_time_windows_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_tap_time_windows_t *val);

typedef enum
{
  LSM6DSV16X_ONLY_SINGLE        = 0x0,
  LSM6DSV16X_BOTH_SINGLE_DOUBLE = 0x1,
} lsm6dsv16x_tap_mode_t;
/**
  * @brief  Single/double-tap event enable.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      ONLY_SINGLE, BOTH_SINGLE_DOUBLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_tap_mode_t val);
/**
  * @brief  Single/double-tap event enable.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      ONLY_SINGLE, BOTH_SINGLE_DOUBLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tap_mode_get(const stmdev_ctx_t *ctx, lsm6dsv16x_tap_mode_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  Tilt Tilt detection Configuration
  * @brief     This section groups all the functions that manage the tilt
  *            event detection.
  * @{
  *
  */

/**
  * @brief  Tilt calculation.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Tilt calculation.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tilt_mode_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Tilt calculation.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Tilt calculation.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_tilt_mode_get(const stmdev_ctx_t *ctx, uint8_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  Timestamp Timestamp Configuration
  * @brief     This section groups all the functions that manage the
  *            timestamp generation.
  * @{
  *
  */

/**
  * @brief  Timestamp data output.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Timestamp data output.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_timestamp_raw_get(const stmdev_ctx_t *ctx, uint32_t *val);

/**
  * @brief  Enables timestamp counter.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables timestamp counter.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_timestamp_set(const stmdev_ctx_t *ctx, uint8_t val);
/**
  * @brief  Enables timestamp counter.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Enables timestamp counter.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_timestamp_get(const stmdev_ctx_t *ctx, uint8_t *val);


/**
  * @}
  *
  */

/**
  * @defgroup  Activity_Inactivity Wake Up/Activity/Inactivity (Sleep) Configuration
  * @brief     This section groups all the functions that manage the Wake Up
  *            event generation.
  * @{
  *
  */

typedef enum
{
  LSM6DSV16X_XL_AND_GY_NOT_AFFECTED       = 0x0,
  LSM6DSV16X_XL_LOW_POWER_GY_NOT_AFFECTED = 0x1,
  LSM6DSV16X_XL_LOW_POWER_GY_SLEEP        = 0x2,
  LSM6DSV16X_XL_LOW_POWER_GY_POWER_DOWN   = 0x3,
} lsm6dsv16x_act_mode_t;
/**
  * @brief  Enable activity/inactivity (sleep) function.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_AND_GY_NOT_AFFECTED, XL_LOW_POWER_GY_NOT_AFFECTED, XL_LOW_POWER_GY_SLEEP, XL_LOW_POWER_GY_POWER_DOWN,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_mode_set(const stmdev_ctx_t *ctx, lsm6dsv16x_act_mode_t val);
/**
  * @brief  Enable activity/inactivity (sleep) function.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      XL_AND_GY_NOT_AFFECTED, XL_LOW_POWER_GY_NOT_AFFECTED, XL_LOW_POWER_GY_SLEEP, XL_LOW_POWER_GY_POWER_DOWN,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_mode_get(const stmdev_ctx_t *ctx, lsm6dsv16x_act_mode_t *val);

typedef enum
{
  LSM6DSV16X_SLEEP_TO_ACT_AT_1ST_SAMPLE = 0x0,
  LSM6DSV16X_SLEEP_TO_ACT_AT_2ND_SAMPLE = 0x1,
  LSM6DSV16X_SLEEP_TO_ACT_AT_3RD_SAMPLE = 0x2,
  LSM6DSV16X_SLEEP_TO_ACT_AT_4th_SAMPLE = 0x3,
} lsm6dsv16x_act_from_sleep_to_act_dur_t;
/**
  * @brief  Duration in the transition from Stationary to Motion (from Inactivity to Activity).[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SLEEP_TO_ACT_AT_1ST_SAMPLE, SLEEP_TO_ACT_AT_2ND_SAMPLE, SLEEP_TO_ACT_AT_3RD_SAMPLE, SLEEP_TO_ACT_AT_4th_SAMPLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_from_sleep_to_act_dur_set(const stmdev_ctx_t *ctx,
                                                 lsm6dsv16x_act_from_sleep_to_act_dur_t val);
/**
  * @brief  Duration in the transition from Stationary to Motion (from Inactivity to Activity).[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      SLEEP_TO_ACT_AT_1ST_SAMPLE, SLEEP_TO_ACT_AT_2ND_SAMPLE, SLEEP_TO_ACT_AT_3RD_SAMPLE, SLEEP_TO_ACT_AT_4th_SAMPLE,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_from_sleep_to_act_dur_get(const stmdev_ctx_t *ctx,
                                                 lsm6dsv16x_act_from_sleep_to_act_dur_t *val);

typedef enum
{
  LSM6DSV16X_1Hz875 = 0x0,
  LSM6DSV16X_15Hz   = 0x1,
  LSM6DSV16X_30Hz   = 0x2,
  LSM6DSV16X_60Hz   = 0x3,
} lsm6dsv16x_act_sleep_xl_odr_t;
/**
  * @brief  Selects the accelerometer data rate during Inactivity.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      1Hz875, 15Hz, 30Hz, 60Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_sleep_xl_odr_set(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_act_sleep_xl_odr_t val);
/**
  * @brief  Selects the accelerometer data rate during Inactivity.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      1Hz875, 15Hz, 30Hz, 60Hz,
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_sleep_xl_odr_get(const stmdev_ctx_t *ctx,
                                        lsm6dsv16x_act_sleep_xl_odr_t *val);

typedef struct
{
  lsm6dsv16x_inactivity_dur_t inactivity_cfg;
  uint8_t inactivity_ths;
  uint8_t threshold;
  uint8_t duration;
} lsm6dsv16x_act_thresholds_t;
/**
  * @brief  Wakeup and activity/inactivity threshold.[set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Wakeup and activity/inactivity threshold.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_thresholds_set(const stmdev_ctx_t *ctx,
                                      const lsm6dsv16x_act_thresholds_t *val);
/**
  * @brief  Wakeup and activity/inactivity threshold.[get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Wakeup and activity/inactivity threshold.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_thresholds_get(const stmdev_ctx_t *ctx,
                                      lsm6dsv16x_act_thresholds_t *val);

typedef struct
{
  uint8_t shock                : 2;
  uint8_t quiet                : 4;
} lsm6dsv16x_act_wkup_time_windows_t;

/**
  * @brief  Time windows configuration for Wake Up - Activity - Inactivity (SLEEP, WAKE). Duration to go in sleep mode. Default value: 0000 (this corresponds to 16 ODR) 1 LSB = 512/ODR_XL time. Wake up duration event. 1 LSB = 1/ODR_XL time. [set]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time windows configuration for Wake Up - Activity - Inactivity (SLEEP, WAKE). Duration to go in sleep mode. Default value: 0000 (this corresponds to 16 ODR) 1 LSB = 512/ODR_XL time. Wake up duration event. 1 LSB = 1/ODR_XL time.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_wkup_time_windows_set(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_act_wkup_time_windows_t val);

/**
  * @brief  Time windows configuration for Wake Up - Activity - Inactivity (SLEEP, WAKE). Duration to go in sleep mode. Default value: 0000 (this corresponds to 16 ODR) 1 LSB = 512/ODR_XL time. Wake up duration event. 1 LSB = 1/ODR_XL time. [get]
  *
  * @param  ctx      read / write interface definitions
  * @param  val      Time windows configuration for Wake Up - Activity - Inactivity (SLEEP, WAKE). Duration to go in sleep mode. Default value: 0000 (this corresponds to 16 ODR) 1 LSB = 512/ODR_XL time. Wake up duration event. 1 LSB = 1/ODR_XL time.
  * @retval          interface status (MANDATORY: return 0 -> no Error)
  *
  */
int32_t lsm6dsv16x_act_wkup_time_windows_get(const stmdev_ctx_t *ctx,
                                             lsm6dsv16x_act_wkup_time_windows_t *val);

/**
  * @}
  *
  */


/**
  * @}
  *
  */
#ifdef __cplusplus
}
#endif

#endif /*LSM6DSV16X_DRIVER_H */
