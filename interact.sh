#!/bin/bash

#interact -q gpu -g 1 -m 32g -t 8:00:00

interact -n 64 -m 32g -t 8:00:00
module load cmake
