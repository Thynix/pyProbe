import telnetlib
import argparse
import random

rand = random.SystemRandom()

#Set up argument parsing
parser = argparse.ArgumentParser(description="Collect information gathered by making probes to random network locations, then update analysis thereof, generate graphs, and optionally upload the results.")
parser.add_argument('-u', dest="upload", default=False,\
                    action="store_true", help="Upload updated analysis. This is not done by default.")
parser.add_argument('-t', dest="numThreads", default=5,\
                    help="Number of simultanious probe threads to run. Default 5 threads.")
parser.add_argument('--host', dest="host", default="127.0.0.1",\
                    help="Telnet host; Freenet node to connect to. Default 127.0.0.1.")
parser.add_argument('-p', dest="port", default=2323,\
                    help="Port the target node is running TMCI on. Default port 2323.")
parser.add_argument('-N', dest="numProbes", default=120, type=int,\
                    help="Number of total probes to make in each thread. Default 120 probes.")
parser.add_argument('-w', dest="probeWait", default=30,
                    help="Number of seconds to wait for a probe response. Default 10 seconds.")

args = parser.parse_args()

prompt="TMCI> "
tn = telnetlib.Telnet(args.host, args.port)

#Read through intial help message.
tn.read_until(prompt)

#TODO: Thread this out into requested number of processes.
#Each thread will need its own sqlite and telnet connection.
#TODO: Better way to do this in Python? Having an array just to loop seems silly.
for i in range(args.numProbes):
	tn.write("PROBE:" + str(rand.random()) + "\n")
	print(tn.read_until(prompt, args.probeWait))
