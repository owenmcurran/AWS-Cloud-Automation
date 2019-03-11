#!/usr/bin/python3

"""A tiny Python program to check that httpd is running.
Try running this program from the command line like this:
  python3 check_webserver.py
"""

import subprocess
import time

def checkhttpd():
  try:
    cmd = 'ps -A | grep httpd'
   
    subprocess.run(cmd, check=True, shell=True)
    time.sleep(1.5)
    print('')
    print("\rWeb Server IS running")
    print('')
    time.sleep(1.5)
   
  except subprocess.CalledProcessError:
    print("\rWeb Server IS NOT running")
    
# Define a main() function.
def main():
    checkhttpd()
      
# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()