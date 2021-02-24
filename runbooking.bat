@echo off
call activate base
title %1
python booking_request.py %1
title DONE
pause