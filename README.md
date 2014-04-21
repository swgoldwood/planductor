planductor-client
==============

Steps for setting up Planductor-client:

1. Sign-up and Sign-in as an organiser to Planductor-web by visting http://localhost:3000/ clicking the "Sign up" link in the menu bar. Next, navigate to the "Hosts" page through the menu bar. Add the client machine's IP address as a trusted host.

2. Copy the same server.crt generated for Planductor-server onto the client machine.

3. On the client machine, open a terminal session and navigate to planductor-client source directory. Run this command to start the client:

        python planductor.py --host=[hostname/IP of Planductor-server] --cert=/path/to/server.crt --webport=3000
