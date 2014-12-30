#!/bin/sh

bash -c 'cd /home/net/priya/ && echo -e "\n\nStarting urlshortner..." >> shortner.log && ./urlshort.py 8124 >> shortner.log 2>&1 &'

