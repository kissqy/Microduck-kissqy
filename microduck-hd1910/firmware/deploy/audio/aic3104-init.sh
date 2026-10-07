#!/bin/bash
# TLV320AIC3104 mixer setup. The kernel codec driver handles PLL / DAC / line
# output configuration via the devicetree overlay; this script only applies the
# default mixer levels and microphone routing on top.

sleep 2

# The ALSA card may not be registered immediately after boot — retry a few
# times if amixer can't find it yet. The window is generous because on the
# Radxa the card probe is deferred until the DKMS codec module autoloads.
for i in $(seq 1 15); do
    if amixer -c aic3104 info >/dev/null 2>&1; then
        # Speaker path: the speaker amp hangs off the codec's line outputs
        # (LEFT_LOP/RIGHT_LOP). 'Line Playback Switch' is the LOP output-stage
        # MUTE (not a line-in bypass — this script used to set it off, which
        # silences the robot; the Pi only worked because alsa-restore happened
        # to re-apply an old saved state with it on). 'Line Playback Volume'
        # is the LOP stage gain, 0..9 dB.
        amixer -c aic3104 cset name='PCM Playback Volume'      127,127 >/dev/null
        amixer -c aic3104 cset name='Line DAC Playback Volume' 118,118 >/dev/null
        amixer -c aic3104 cset name='Line Playback Switch'     on,on   >/dev/null
        amixer -c aic3104 cset name='Line Playback Volume'     9,9     >/dev/null

        # Onboard microphone: route Mic3R → Right PGA only
        amixer -c aic3104 sset 'Right PGA Mixer Mic3R'  on  >/dev/null
        amixer -c aic3104 sset 'Left PGA Mixer Mic3R'   off >/dev/null
        amixer -c aic3104 sset 'Left PGA Mixer Mic3L'   off >/dev/null
        amixer -c aic3104 sset 'Right PGA Mixer Mic3L'  off >/dev/null
        amixer -c aic3104 sset 'Right PGA Mixer Line1R' off >/dev/null
        amixer -c aic3104 sset 'Right PGA Mixer Line1L' off >/dev/null
        amixer -c aic3104 sset 'Left PGA Mixer Line1R'  off >/dev/null
        amixer -c aic3104 sset 'Left PGA Mixer Line1L'  off >/dev/null
        amixer -c aic3104 sset 'Right PGA Mixer Line2R' off >/dev/null
        # Capture path: enable PGA capture switch and set gain (0-119)
        amixer -c aic3104 cset name='PGA Capture Switch' on,on >/dev/null
        amixer -c aic3104 cset name='PGA Capture Volume' 60,60 >/dev/null

        echo "TLV320AIC3104 mixer levels set"
        break
    fi
    sleep 1
done
