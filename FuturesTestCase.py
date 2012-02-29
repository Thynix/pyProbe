import concurrent.futures
import time
import signal
from sys import exit

wait = 10
numThreads = 1

#Intent: Always be executing numThreads instances of do_something(), until SIGINT.

def handler(signum, frame):
	print('Signal handler called with signal', signum)
	exit(0)

def do_something(threadNum):
	print("Thread {0} starting".format(threadNum))
	time.sleep(wait)
	print("Thread {0} finished".format(threadNum))

class PoolManager:
	def __init__(self, numThreads):
		self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=numThreads)
		self.threadNum = 0
		self.method = do_something
		self.args = self.threadNum
		signal.signal(signal.SIGINT, handler)

	def add_thread(self):
		future = self.executor.submit(self.method, self.args)
		future.add_done_callback(self.callback)
		self.threadNum += 1

	def callback(self, future):
		print("Result {0}".format(future.result()))
		self.add_thread()
	
	def __del__(self):
		print("Destructing PoolManager")
		#Shut down without waiting - the threads never terminate otherwise.
		self.executor.shutdown(False)

with concurrent.futures.ThreadPoolExecutor(max_workers=numThreads) as executor:
	manager = PoolManager(numThreads)
	for i in range(numThreads):
		manager.add_thread()
