#!/bin/sh
set -eu
exec tsh ssh -N -L 127.0.0.1:18765:127.0.0.1:18765 admin-mnvo-vm-01@mnvo-mv-01
