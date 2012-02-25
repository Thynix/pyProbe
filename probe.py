import telnetlib
import argparse
import random
import re

rand = random.SystemRandom()
location = re.compile(r"Completed probe request: 0\.\d+ -> (0\.\d+)")
uid = re.compile(r"peer UIDs=\[([-\d ,]*)\]")

#Set up argument parsing
parser = argparse.ArgumentParser(description="Make probes to random network locations, analyze the results for estimates of network size, generate graphs, and optionally upload the results.")
parser.add_argument('-u', dest="upload", default=False,\
                    action="store_true", help="Upload updated analysis. This is not done by default.")
parser.add_argument('-t', dest="numThreads", default=5, type=int,\
                    help="Number of simultanious probe threads to run. Default 5 threads.")
parser.add_argument('--host', dest="host", default="127.0.0.1",\
                    help="Telnet host; Freenet node to connect to. Default 127.0.0.1.")
parser.add_argument('-p', dest="port", default=2323, type=int,\
                    help="Port the target node is running TMCI on. Default port 2323.")
parser.add_argument('-N', dest="numProbes", default=120, type=int,\
                    help="Number of total probes to make in each thread. Default 120 probes.")
parser.add_argument('-w', dest="probeWait", default=30, type=int,\
                    help="Number of seconds to wait for a probe response. Default 30 seconds.")

args = parser.parse_args()

prompt="TMCI> "
tn = telnetlib.Telnet(args.host, args.port)

#Read through intial help message.
tn.read_until(prompt)

#TODO: Thread this out into requested number of processes.
#Each thread will need its own sqlite and telnet connection.
for _ in range(args.numProbes):
	tn.write("PROBE:" + str(rand.random()) + "\n")
	raw = tn.read_until(prompt, args.probeWait)
	#TODO: What if timeout elapses? Need to skip parsing attempt.
	#TODO: Wait time between probe attempts.
	
	#Take the right side of "Completed probe request: <target location> -> <closest found location>"
	print("Found location: ", location.search(raw).group(1))
	
	#Follow probe traces for list of UIDs.
	for group in uid.findall(raw):
		print(group.split(','))
	
	#TODO: Take peer locations into account, giving infromation on distribution and average peer count.
