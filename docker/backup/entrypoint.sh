#!/bin/sh
/backup.sh
exec crond -f -d 8
