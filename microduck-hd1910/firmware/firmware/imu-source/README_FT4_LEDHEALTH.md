# FT4 RX-turnaround and LED health semantics

FT4 contains the unchanged FT3 USART/bus-direction fix and keeps the same
Feetech wire contract:

- native Feetech protocol, 1 Mbps, fixed ID 200;
- 20-byte IMU snapshot at addresses 56 and 124;
- no write, torque, ID, baud-rate, reset, or motion operations.

The firmware identity is 4.0.  LED behavior is now diagnostic:

- boot: two 200 ms pulses;
- healthy and idle/no host data read: off;
- fresh IMU quaternion plus a successfully transmitted address 56/124 data
  response: one 50 ms activity pulse, rate-limited to one pulse per 500 ms;
- IMU initialization failure: solid on;
- no first quaternion for 1000 ms, or no fresh quaternion for 500 ms after
  becoming ready: solid on; normal indication resumes if samples recover.

The visible rate limit is deliberate.  Directly driving the LED at the 120 Hz
sensor rate or the 50 Hz host request rate would look continuously illuminated
and could not be distinguished from the requested fault indication.
