#!/usr/bin/env python3
import os
import slpy
import time
import sys
import shutil

def main():
    try:
        rows, columns = os.popen('stty size', 'r').read().split()
    except Exception:
        columns, rows = shutil.get_terminal_size()
        
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    for i in slpy.sl(int(columns), int(rows), arg):
        print(i)
        time.sleep(0.04)
