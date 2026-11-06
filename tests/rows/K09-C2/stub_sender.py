#!/usr/bin/env python3
"""K09-C2 stub sender: usage `stub_sender.py <out file> <exit code> <message file>`.
Writes the bytes of the message file it was handed to the out file (so the out file exists only when the stub was called),
then exits with the given code. It sends nothing anywhere."""
import sys

out, code, msg = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(msg, 'rb') as fh:
    data = fh.read()
with open(out, 'wb') as fh:
    fh.write(data)
sys.exit(code)
