#!/usr/bin/env python

########################################################

import datetime
import argparse
import socket
import select
import logging
import json

from dateutil import parser
########################################################

class ClientHandler:
    ''' Listens to clients and responds appropriately '''

    def __init__(self, port=30714, host='localhost'):
        self.addr = (host, port)
        self.CLIENT_LIST = []
        self.tasks = [
            {
                'name': 'lama driverlog 1',
                'planner': '/dcs/research/ais/planning/planners-64bit/seq-sat-lama-2011/plan',
                'domain': '/dcs/research/ais/planning/domains/driverlog/domain.pddl',
                'problem': '/dcs/research/ais/planning/domains/driverlog/pfile09.pddl',
                'duration': 60,
                'start_time': None,
                'expected_end_time': None,
                'host': None,
                'complete': False,
                'results': None
            },
            {
                'name': 'lama driverlog 2',
                'planner': '/dcs/research/ais/planning/planners-64bit/seq-sat-lama-2011/plan',
                'domain': '/dcs/research/ais/planning/domains/driverlog/domain.pddl',
                'problem': '/dcs/research/ais/planning/domains/driverlog/pfile10.pddl',
                'duration': 60,
                'start_time': None,
                'expected_end_time': None,
                'host': None,
                'complete': False,
                'results': None
            }
        ]

    # ----------------------------------------------

    def listen(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logging.info("Binding address %s:%i" % self.addr)

        try:
            server_sock.bind(self.addr)
        except socket.error as msg:
            logging.error('Bind failed, Error Code: ' + str(msg[0]) + ' Message ' + msg[1])
            return False

        logging.info('Now waiting for client connections')
        server_sock.listen(10)

        self.CLIENT_LIST.append(server_sock)

        while True:
            read_sockets, write_sockets, error_sockets = select.select(self.CLIENT_LIST, [], [])

            for sock in read_sockets:
                # if the server socket is ready, there must be new client to handle
                if sock == server_sock:
                    self.add_new_client(sock)
                # must be a current client communicating
                else:
                    self.handle_existing_client(sock)

        server_sock.close()

    # ----------------------------------------------

    def add_new_client(self, sock):
        client_sock, addr = sock.accept()
        logging.info("New client %s:%i" % addr)
        self.CLIENT_LIST.append(client_sock)

    # ----------------------------------------------

    def handle_existing_client(self, sock):

        data = None
        try:
            data = sock.recv(4096)
            logging.debug("Recieved client data: " + data)
        except socket.error as msg:
            logging.error('recv failed, Error Code: ' + str(msg[0]) + ' Message ' + msg[1])
            sock.close()
            self.CLIENT_LIST.remove(sock)
            return

        #client has closed connection
        if data == "":
            logging.debug("Removing client %s:%i because socket is closed" % sock.getpeername())
            sock.close()
            self.CLIENT_LIST.remove(sock)
            return

        logging.info("Handling existing client %s:%i" % sock.getpeername())

        client_message = json.loads(data)

        #handles client based on status returned
        if client_message['status'] == 'ready':
            logging.info('Client %s:%i is ready, finding available task' % sock.getpeername())
            self.send_client_task(sock)
        elif client_message['status'] == 'finished':
            logging.info('Client %s:%i has finished task' % sock.getpeername())
            self.set_tasks(client_message, sock)
        else:
            logging.info('Client is current status is: ' + client_message['status'])
            sock.send(json.dumps({'status': 'ok'}))

    # ----------------------------------------------

    def send_client_task(self, sock):
        task = self.find_available_task(sock)

        if task == None:
            logging.info('Could not find any available tasks for %s:%i' % sock.getpeername())
            self.notify_client(sock, {'status':'ok', 'task': None})

        sock.send(json.dumps({'status':'ok', 'task':task}))

    # ----------------------------------------------

    def find_available_task(self, sock):
        for task in self.tasks:
            if not task['complete'] and task['host'] == None:
                task['host'] = sock.getpeername()
                logging.info("Found task %s for client %s:%i" % (task['name'], task['host'][0], task['host'][1]))
                return task

        return None

    # ----------------------------------------------

    def set_tasks(self, client_message, sock):
        logging.info('Task %s has completed' % client_message['task']['name'])

        found_task = False

        for task in self.tasks:
            if task['name'] == client_message['task']['name']:
                found_task = True
                task['complete'] = True
                task['end_time'] = parser.parse(client_message['task']['end_time'])
                task['results'] = client_message['task']['results']

        if not found_task:
            logging.error("Can't find task '%s' recieved from client" % task['task']['name'])

        self.notify_client(sock, {'status': 'ok'})

    # ----------------------------------------------

    def notify_client(self, sock, message):
        json_message = json.dumps(message)
        sock.send(json_message)


########################################################

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--debug')
    arg_parser.add_argument('--port')
    args = arg_parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    PORT = 37014
    if args.port:
        PORT = int(args.port)

    client_handler = ClientHandler(port=PORT)
    client_handler.listen()

