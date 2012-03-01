from twisted.internet import reactor
from time import sleep
from signal import signal, SIGINT
from sys import exit

def ContinuousThread():
	while True:
		print("Start")
		#Pretend this is some collection process I'd like to run until user termination of the program
		sleep(2)
		print("Stop")

def handler(num, frame):
	exit(0)
	reactor.stop()

reactor.callInThread(ContinuousThread)
reactor.callWhenRunning(signal, SIGINT, handler)
reactor.run()

#Try to C^c / SIGINT. :/
#Must be kill -9'd it seems; doesn't respond to SIGTERM either.
