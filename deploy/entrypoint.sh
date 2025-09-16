#!/bin/sh
set -eu

nginx
exec python run.py
