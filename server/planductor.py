#!/usr/bin/env python

########################################################

import datetime
import argparse
import socket
import select
import logging
import json
########################################################

#putting stub entries for experimentation
tasks = [
    {
        'name': 'task1',
        'planner': 'bsg001',
        'domain': 'city',
        'problem': 'deliveries1',
        'duration': 60,
        'start_time': None,
        'expected_end_time': None,
        'host': None,
        'complete': False
    },
    {
        'name': 'task2',
        'planner': 'bsg001',
        'domain': 'city',
        'problem': 'deliveries2',
        'duration': 60,
        'start_time': None,
        'expected_end_time': None,
        'host': None,
        'complete': False
    }
]

# ----------------------------------------------

def add_new_client(socket, client_list):
    client_sock, addr = socket.accept()
    logging.info("New client %s:%i" % addr)
    client_list.append(client_sock)

# ----------------------------------------------

def handle_existing_client(socket, client_list):
    logging.info("Handling existing client")

    data = None
    try:
        data = socket.recv(4096)
        logging.info("Recieved client data: " + data)
    except socket.error as msg:
        logging.error('recv failed, Error Code: ' + str(msg[0]) + ' Message ' + msg[1])
        socket.close()
        client_list.remove(socket)
        return

    #client has closed connection
    if data == "":
        logging.info("Removing client %s:%i because socket is closed" % socket.getpeername())
        socket.close()
        client_list.remove(socket)
        return

    client_message = json.loads(data)

    if client_message['status'] == 'ready':
        logging.info('Client %s:%i is ready, finding available task' % socket.getpeername())
        send_client_task(socket)
    elif client_message['status'] == 'finished':
        logging.info('Client %s:%i has finished task' % socket.getpeername())
        set_tasks(client_message, socket)
    else:
        logging.info('Client is current status is: ' + client_message['status'])
        socket.send(json.dumps({'status': 'ok'}))

# ----------------------------------------------

def send_client_task(socket):
    task = find_available_task(socket)

    if task == None:
        logging.info('Could not find any available tasks for %s:%i' % socket.getpeername())
        notify_client(socket, {'status':'ok', 'task': None})

    socket.send(json.dumps({'status':'ok', 'task':task}))

# ----------------------------------------------

def find_available_task(socket):
    for task in tasks:
        if not task['complete'] and task['host'] == None:
            task['host'] = socket.getpeername()
            return task

    return None

# ----------------------------------------------

def set_tasks(client_message, socket):
    logging.info('Task %s has completed with result: %d' % (task['name'], task['result']))

    for task in tasks:
        if task['name'] == client_message['task']['name']:
            task['complete'] = True
            task['end_time'] = client_message['task']['end_time']
            task['result'] = client_message['task']['result']

    notify_client(socket, {'status': 'ok'})

# ----------------------------------------------

def notify_client(socket, message):
    json_message = json.dumps(message)
    socket.send(json_message)

# ----------------------------------------------

########################################################
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    server_addr = ('localhost', 30914)
    CONNECTION_LIST = []

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logging.info("Binding address %s:%i" % server_addr)

    try:
        server_sock.bind(server_addr)
    except socket.error as msg:
        logging.error('Bind failed, Error Code: ' + str(msg[0]) + ' Message ' + msg[1])
        sys.exit()

    server_sock.listen(10)

    CONNECTION_LIST.append(server_sock)

    while True:
        read_sockets, write_sockets, error_sockets = select.select(CONNECTION_LIST, [], [])

        for sock in read_sockets:
            # if socket ready is the server socket, there must be new client to handle
            if sock == server_sock:
                add_new_client(sock, CONNECTION_LIST)
            # must be a current client communicating
            else:
                handle_existing_client(sock, CONNECTION_LIST)

    server_sock.close()
