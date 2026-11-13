#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# USB function excerpt from Armbian 26.2.1; https://www.armbian.com/authors
# https://github.com/armbian/build/blob/main/packages/bsp/common/usr/lib/armbian/armbian-hardware-optimization
# Unrelated board setup replaced by no-ops for isolated regression tests.
prepare_board() { :; }
add_usb_storage_quirks() {

	# check for /boot/armbianEnv.txt existence
	[ -f /boot/armbianEnv.txt ] || return

	# cleanup. add LF. This prevents adding parameters to the same line
	echo "" >> /boot/armbianEnv.txt
	sed -i '/^$/d;$G' /boot/armbianEnv.txt
	sed -i '/^$/d;$G' /boot/armbianEnv.txt

	# cleanup. remove empty lines in the middle
	sed -i '/^$/d' /boot/armbianEnv.txt

	# preserve old contents if existent
	TMPFILE=$(mktemp /tmp/${0##*/}.XXXXXX)
	trap "sleep 1 ; rm \"${TMPFILE}\" ; exit 0" 0 1 2 3 15
	awk -F"=" '/^usbstoragequirks/ {print $2}' < /boot/armbianEnv.txt | tr -d -c '[:graph:]' > ${TMPFILE}

	# UAS blacklist Norelsys NS1068X and NS1066X since broken. Can be removed once
	# they're blacklisted upstream
	[ -s ${TMPFILE} ] || echo "0x2537:0x1066:u,0x2537:0x1068:u" > ${TMPFILE}

	# check for connected Seagate or WD HDD enclosures and blacklist them all
	lsusb | awk -F" " '{print "0x"$6}' | sed 's/:/:0x/' | sort | uniq | while read; do
		case ${REPLY} in
			"0x0bc2:"* | "0x1058:"*)
				grep -q "${REPLY}" ${TMPFILE} || sed -i "1 s/\$/,${REPLY}:u/" ${TMPFILE}
				;;
		esac
	done

	read USBQUIRKS < ${TMPFILE}
	sed -i '/^usbstoragequirks/d' /boot/armbianEnv.txt
	echo "usbstoragequirks=${USBQUIRKS}" >> /boot/armbianEnv.txt
	sync &
	if [ -f /sys/module/usb_storage/parameters/quirks ]; then
		echo ${USBQUIRKS} > /sys/module/usb_storage/parameters/quirks
	fi

} # add_usb_storage_quirks
case $1 in
  *start*)
    prepare_board &
    add_usb_storage_quirks &
    ;;
esac
