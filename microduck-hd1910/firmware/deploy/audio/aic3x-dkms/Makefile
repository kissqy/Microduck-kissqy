# Out-of-tree build of the TI TLV320AIC3x ASoC codec driver (core +
# I2C interface), mirroring sound/soc/codecs/Makefile in-tree naming so
# the modules land as snd-soc-tlv320aic3x[-i2c].ko. Built via DKMS —
# see dkms.conf and README.md in this directory.

snd-soc-tlv320aic3x-objs := tlv320aic3x.o
snd-soc-tlv320aic3x-i2c-objs := tlv320aic3x-i2c.o

obj-m += snd-soc-tlv320aic3x.o
obj-m += snd-soc-tlv320aic3x-i2c.o
