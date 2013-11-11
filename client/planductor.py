#!/usr/bin/env python

import datetime
import argparse
import socket
import select
import logging
import json
import time
import sys

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    
    server_addr = (args.host, int(args.port))

    while True:
        socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
        socket.connect(server_addr)
    
        current_status = {
            'status': 'ready'
        }
    
        socket.send(json.dumps(current_status))
        response = json.loads(socket.recv(4096))

        if 'name' in response['task'] and response['task']['name'] != None:
            logging.info("Got task: " + response['task']['name'])
        else:
            logging.info("No task recieved")
            sys.exit(0)

        #stub - just sleeping for the time being...
        time.sleep(10)

        current_status = {
            'status': 'finished',
            'task': {
                'name': response['task']['name'],
                'end_time': datetime.datetime.now(),
                'result': 12.52
            }
        }

        socket.send(json.dumps(current_status))
        response = socket.recv(4096)

        logging.info("Server Response: " + response)

        socket.close()
