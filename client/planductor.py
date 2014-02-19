#!/usr/bin/env python

########################################################

import datetime
import argparse
import socket
import select
import logging
import json
import time
import sys
import os
import re

import threading
import subprocess
import traceback
import shlex
########################################################
  
class Command(object):
    """
    Enables to run subprocess commands in a different thread with TIMEOUT option.
    """

    command = None
    process = None
    status = None
    output, error = '', ''

    def __init__(self, command):
        if isinstance(command, basestring):
            command = shlex.split(command)
        self.command = command

    # ----------------------------------------------

    def run(self, timeout=None, **kwargs):
        """ Run a command then return: (status, output, error). """
        def target(**kwargs):
            logging.info("Executing: " + self.command.__str__())
            try:
                self.process = subprocess.Popen(self.command, **kwargs)
                self.output, self.error = self.process.communicate()
                self.status = self.process.returncode
            except:
                self.error = traceback.format_exc()
                self.status = -1

        # default stdout and stderr
        if 'stdout' not in kwargs:
            kwargs['stdout'] = subprocess.PIPE
        if 'stderr' not in kwargs:
            kwargs['stderr'] = subprocess.PIPE

        saved_dir = os.getcwd()
        os.chdir("/tmp")

        # thread
        thread = threading.Thread(target=target, kwargs=kwargs)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()

        os.chdir(saved_dir)

        return self.status, self.output, self.error

########################################################

def execute_experiment(experiment):
    #create sandbox diretory for mbox
    if not os.path.exists(experiment.sandbox):
        os.makedirs(experiment.sandbox)

    #build cmd string and execute planner
    ulimit_cmd = "ulimit -v 400000; " + "ulimit -t %d" % experiment.duration + ";"
    mbox_cmd = os.path.dirname(os.path.abspath(__file__)) + "/dependencies/mbox"
    main_cmd = ulimit_cmd + " " +  mbox_cmd + " -i -r " +\
        experiment.sandbox + " -- " + experiment.get_cmd()
    logging.info("Running command: %s" % main_cmd)

    start_time = int(time.time())
    rc = subprocess.call(main_cmd, shell=True)
    end_time = int(time.time())

    total_time = end_time - start_time

    logging.info("Planner executed with return code %s, for %s of limit %s seconds" % (rc, total_time, experiment.duration))

    if total_time < experiment.duration:
        logging.error("The planner exited with bad return code and only ran for %s seconds. Check logs!" % total_time)
    else:
        logging.info("Planner execution looks good!")

    return validate_results(experiment)


########################################################

class Experiment:
    """
    Encapsulate experiment variables
    """
    def __init__(self, planner, domain, problem, duration):
        self.planner = planner
        self.domain = domain
        self.problem = problem
        self.duration = duration
        self.sandbox = "/tmp/sandbox-" + str(int(time.time()))
        self.result_file = "/tmp/planner-results"
        self.real_result_file = self.sandbox + self.result_file
        self.results = []

    # ----------------------------------------------

    def get_cmd(self):
        return self.planner + " " + self.domain + " " + self.problem + " " + self.result_file

    # ----------------------------------------------

    def get_results(self):
        logging.info("Getting results for experiment. Result files in form of %s*" % self.result_file)


########################################################

def validate_results(experiment):
    results_found = find_results(experiment.result_file)
    results_score = []
    
    for result in results_found:
        valid, score = validate_result(experiment, result)

        result_dict = {
            'name': result,
            'valid': valid
        }

        if not valid:
            logging.error("Found invalid result: %s" % result)
        else:
            result_dict['score'] = score
            results_score.append(result_dict)

    return results_score


def find_results(result_name):
    results = []
    logging.info("FINDING dirname of %s" % result_name)
    for (pathname, dirnames, filenames) in os.walk(os.path.dirname(result_name)):
        for filename in filenames:
            if re.match('^%s\.\d+$' % os.path.basename(result_name), filename):
                logging.info("Found result file %s" % os.path.dirname(result_name) + '/' + filename)
                results.append(os.path.dirname(result_name) + '/' + filename)
        logging.info("DONE finding results...")
    logging.info("REALLY DONE")
    return results


def validate_result(experiment, result):
    cmd = "/dcs/research/ais/planning/planners/validate -t 0.001 %s %s %s" % (experiment.domain, experiment.problem, result)
    output = subprocess.check_output(cmd, shell=True)
    output_lines = output.split("\n")

    if output_lines[2] != "Plan valid":
        return False, -1

    match = re.search("(\d+)$", output_lines[6])
    score = int(match.group(1))

    return True, score


########################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    
    server_addr = (args.host, int(args.port))

    print os.path.abspath(__file__)

    while True:
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
        client_sock.connect(server_addr)
    
        current_status = {
            'status': 'ready'
        }
    
        client_sock.send(json.dumps(current_status))
        raw_data = client_sock.recv(4096)

        if raw_data == "":
            logging.error("Server connection failed")
            sys.exit(1)

        response = json.loads(raw_data)

        if response['task'] != None and 'name' in response['task'] and response['task']['name'] != None:
            logging.info("Got task: " + response['task']['name'])
        else:
            logging.info("No task recieved, exiting...")
            sys.exit(0)

        experiment = Experiment(response['task']['planner'], response['task']['domain'], response['task']['problem'], response['task']['duration'])

        #command = Command(experiment.get_cmd())

        #command.run(timeout=experiment.duration)

        #if command.status != 0:
        #    logging.error("Command failed!")
        #else:
        #    logging.info("Command succeeded!")

        results_array = execute_experiment(experiment)

        logging.info("Printing scores")

        for res in results_array:
            print res['name'] + ": " + str(res['score'])

        current_status = {
            'status': 'finished',
            'task': {
                'name': response['task']['name'],
                'end_time': str(datetime.datetime.now()),
                'results': results_array
            }
        }

        client_sock.send(json.dumps(current_status))
        response = client_sock.recv(4096)

        logging.info("Server Response: " + response)

        client_sock.close()

        sys.exit(0)
