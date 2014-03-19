#!/usr/bin/env python

########################################################

import datetime
import argparse
import socket
import ssl

import select
import logging
import json
import time
import sys
import os
import re
import pprint

import threading
import subprocess
import traceback
import shlex
import tarfile
import shutil

from urllib2 import urlopen, URLError, HTTPError

########################################################

class DependencyException(Exception):
    pass

########################################################

def execute_experiment(experiment):
    #create sandbox diretory for mbox
    if not os.path.exists(experiment.sandbox):
        os.makedirs(experiment.sandbox)

    #build cmd string and execute planner
    ulimit_cmd = "ulimit -v 400000; " + "ulimit -t %d" % experiment.duration + "; cd %s;" % os.path.dirname(experiment.planner)
    mbox_cmd = os.path.dirname(os.path.abspath(__file__)) + "/dependencies/mbox"
    main_cmd = ulimit_cmd + " " +  mbox_cmd + " -i -r " +\
        experiment.sandbox + " -- " + experiment.get_cmd()
    logging.info("Running command: %s" % main_cmd)

    start_time = int(time.time())
    rc = subprocess.call(main_cmd, shell=True)
    end_time = int(time.time())

    total_time = end_time - start_time

    logging.info("Planner executed with return code %s, for %s of limit %s seconds" % (rc, total_time, experiment.duration))

    #check if returned any results

    #if ran for less than x seconds and no results found then there was probably an error?

    if rc == 0:
        return True
    else:
        return False


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
        self.output_file = "/tmp/planner-output"
        self.results = []

    # ----------------------------------------------

    def get_cmd(self):
        return "./plan " + self.domain + " " + self.problem + " " + self.result_file + " > " + self.output_file

    # ----------------------------------------------

    def get_output(self):
        logging.info("Getting execution output")

        output = ""
        with open(self.output_file, 'r') as output_file:
          output = output_file.read()

        return output


########################################################

def dlfile(url, file_name):
    # Open the url
    try:
        f = urlopen(url)
        logging.info("downloading " + url)

        # Open our local file for writing
        with open(file_name, "wb") as local_file:
            local_file.write(f.read())

    #handle errors
    except HTTPError, e:
        logging.error("HTTP Error: %s, %s" % (e.code, url))
        return False
    except URLError, e:
        logging.error("URL Error: %s, %s" % (e.reason, url))
        return False

    return True


def resolve_dependencies(web_url, dependencies):
    temp_dir = "/tmp/dependencies_" + str(int(time.time()))
    os.mkdir(temp_dir)

    logging.info("Temp dir: %s" % temp_dir)

    #resolve planner
    planner_dir = temp_dir + "/planner"
    os.mkdir(planner_dir)
    planner_tar = planner_dir + "/planner.tar"

    if not dlfile(web_url + dependencies['planner'], planner_tar):
        raise DependencyException("Unable to download planner dependency from web server")

    logging.info("Unpacking planner tarball %s" % planner_tar)
    tarfile.open(planner_tar).extractall(planner_dir)
    os.remove(planner_tar)

    #resolve domain
    domain_dir = temp_dir + "/domain"
    os.mkdir(domain_dir)
    domain_tar = domain_dir + "/domain.tar"

    if not dlfile(web_url + dependencies['domain'], domain_tar):
        raise DependencyException("Unable to download domain dependency from web server")

    logging.info("Unpacking domain tarball %s" % domain_tar)
    tarfile.open(domain_tar).extractall(domain_dir)
    os.remove(domain_tar)

    return temp_dir, planner_dir, domain_dir


def validate_results(experiment):
    results_found = find_results(experiment.sandbox + "/" + experiment.result_file)
    results = []

    sorted(results_found, key=lambda res: int(res[-1]))
    
    for result in results_found:
        valid, quality, validation_output = validate_result(experiment, result)

        output = ""

        with open(result, 'r') as result_file:
            output = result_file.read()

        result = {
            'name': result,
            'result_number': int(result[-1]),
            'quality': quality,
            'output': output,
            'valid_plan': valid,
            'validation_output': validation_output,
        }

        if not valid:
            logging.info("Found invalid result: %s" % result)

        results.append(result)

    return results


def find_results(result_name):
    results = []
    logging.info("FINDING dirname of %s" % result_name)
    for (pathname, dirnames, filenames) in os.walk(os.path.dirname(result_name)):
        for filename in filenames:
            if re.match('^%s\.\d+$' % os.path.basename(result_name), filename):
                logging.info("Found result file %s" % os.path.dirname(result_name) + '/' + filename)
                results.append(os.path.dirname(result_name) + '/' + filename)
    return results


def validate_result(experiment, result):
    validate_path = os.path.dirname(os.path.abspath(__file__)) + "/dependencies/validate"
    cmd = "%s -t 0.001 %s %s %s" % (validate_path, experiment.domain, experiment.problem, result)
    output = subprocess.check_output(cmd, shell=True)
    output_lines = output.split("\n")

    if output_lines[2] != "Plan valid":
        return False, -1, output

    match = re.search("(\d+)$", output_lines[6])
    quality = int(match.group(1))

    return True, quality, output


def clear_temporary_files(directories):
    for directory in directories:
        logging.info("Removing directory tree %s" % directory)
        shutil.rmtree(directory)


########################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    pp = pprint.PrettyPrinter(indent=2)

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', required=True)
    parser.add_argument('--webport', nargs='?', type=int, default=80)
    parser.add_argument('--cert', required=True)
    args = parser.parse_args()

    web_url = "http://" + args.host
    if args.webport != 80:
        web_url = web_url + ":" + str(args.webport)
    
    server_addr = (args.host, int(args.port))

    print os.path.abspath(__file__)

    while True:
        plain_sock = None
        client_sock = None

        plain_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock = ssl.wrap_socket(plain_sock, ca_certs=args.cert, cert_reqs=ssl.CERT_REQUIRED)

        logging.info("Connecting to %s:%i" % server_addr)

        try:
            client_sock.connect(server_addr)
        except socket.error as e:
            logging.info("Cannot connect to %s:%i, probably down" % server_addr)
            logging.error(pp.pformat(e))
            sys.exit(1)
    
        current_status = {
            'status': 'ready'
        }
    
        client_sock.send(json.dumps(current_status))

        raw_data = ""

        try:
            raw_data = client_sock.recv(1048576)
        except socket.error as e:
            logging.error("Error with socket connection, machine IP address might not be trusted in database")
            logging.info(pp.pformat(e))
            sys.exit(1)

        if raw_data == "":
            logging.error("Server connection failed")
            sys.exit(1)

        logging.info(raw_data)

        response = json.loads(raw_data)

        if response['status'] == 'ok' and response['task_id'] == None:
            logging.info("No available tasks")
        elif response['status'] == 'ok':

            temp_dir = planner_dir = domain_dir = ""
            try:
                temp_dir, planner_dir, domain_dir = resolve_dependencies(web_url, response['dependencies'])
            except DependencyException as e:
                logging.error("Problem resolving dependencies")
                logging.info(pp.pformat(e))
                sys.exit(1)

            planner_plan = planner_dir + "/plan"
            domain_pddl = domain_dir + "/domain.pddl"
            problem_pddl = domain_dir + "/pfile%02d.pddl" % response['dependencies']['problem_number']
            cpu_time = 1800

            if 'cpu_time' in response:
                cpu_time = response['cpu_time']

            experiment = Experiment(planner_plan, domain_pddl, problem_pddl, cpu_time) #will be 1800 in future (30 minutes)

            if not execute_experiment(experiment):
                logging.error("Execution failed")
                sys.exit(1)

            results_array = validate_results(experiment)

            logging.info("Printing results")

            for res in results_array:
                logging.info(pp.pformat(res))

            #sending complete message to server
            send_request = {'status': 'complete'}
            client_sock.send(json.dumps(send_request))
            raw_data = client_sock.recv(1048576)
            new_response = json.loads(raw_data)

            #server is ready to receive response, sending now
            if new_response['status'] == 'ok':
                logging.info("Server is read to receive results, sending now")

                current_status = {
                    'status': 'complete',
                    'task': {
                        'task_id': response['task_id'],
                        'end_time': str(datetime.datetime.now()),
                        'output': experiment.get_output(),
                        'results': results_array
                    }
                }

                current_status_json = json.dumps(current_status)

                logging.info("SENDING RESULTS")
                logging.info(current_status_json)

                client_sock.send(current_status_json)
            
            clear_temporary_files([experiment.sandbox, temp_dir])

        client_sock.close()
        plain_sock.close()

        logging.info("Waiting 30 seconds before requesting task...")
        time.sleep(30)
