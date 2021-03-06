# -*- coding: utf-8 -*-
"""
This file is part of PyFrac.

Created by Andreas Möri on Oct 9 13:36:21 2019.
Copyright (c) "ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, Geo-Energy Laboratory", 2016-2019.
All rights reserved. See the LICENSE.TXT file for more details.
"""

# importing module
import os
import matplotlib.pyplot as plt
import sys
import glob
import datetime
import socket

# Create (and closes) a dummy file to know it is a batch_run
with open('batch_run.txt', 'w') as fp:
    pass
fp.close()

# generate the list with all examples
example_list = glob.glob('*.py')
example_list.remove('batch_run.py')

# Open the timing file. The name gives the Machine and the starting time
with open('timing__' + socket.gethostname() + '__' + datetime.datetime.now().strftime("%Y-%m-%d__%H_%M_%S"), 'w') \
        as output:
    output.write("++++++++++++++ Batch run ++++++++++++++\n")

    # set the time when the batch_run started
    batch_start = datetime.datetime.now()

    # Loop over the examples
    for example in example_list:
        output.write('\n')
        output.write('+++++++++++++++++++++++++++++++++++++++\n')
        output.write('Example ' + example + '\n')

        # Start time of the example
        example_start = datetime.datetime.now()

        # Running the example
        exec(open(example).read())
        if len(plt.get_fignums()) > 0: # closes figures if still open
            plt.close('all')

        # write the runtime and the time since the start of the example to the log file
        example_runtime = datetime.datetime.now() - example_start
        output.write('Time for example: ' + str(example_runtime) + '\n')
        time_since_start = datetime.datetime.now() - batch_start
        output.write('Time since batch start: ' + str(time_since_start) + '\n')
        output.write('+++++++++++++++++++++++++++++++++++++++\n')

    # close the log file
    output.close()

# remove the dummy file (Very important! for normal runs we check if it exists or not!)
os.remove('batch_run.txt')

sys.exit(0)