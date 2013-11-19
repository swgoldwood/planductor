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
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
        client_sock.connect(server_addr)
    
        current_status = {
            'status': 'ready'
        }
    
        client_sock.send(json.dumps(current_status))
        response = json.loads(client_sock.recv(4096))

        if response['task'] != None and 'name' in response['task'] and response['task']['name'] != None:
            logging.info("Got task: " + response['task']['name'])
        else:
            logging.info("No task recieved, exiting...")
            sys.exit(0)

        #stub - just sleeping for the time being...
        logging.info("Executing task %s (simulating)" % response['task']['name'])
        time.sleep(response['task']['duration'])

        current_status = {
            'status': 'finished',
            'task': {
                'name': response['task']['name'],
                'end_time': str(datetime.datetime.now()),
                'result': 12.52
            }
        }

        client_sock.send(json.dumps(current_status))
        response = client_sock.recv(4096)

        logging.info("Server Response: " + response)

        client_sock.close()
