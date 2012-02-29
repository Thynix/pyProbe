import concurrent.futures
import time

wait = 0.25
numThreads = 5

#Intent: Always be executing numThreads instances of do_something(), until SIGTERM.

def do_something():
	print("Thread starting")
	time.sleep(wait)
	print("Thread finished")

with concurrent.futures.ThreadPoolExecutor(max_workers=numThreads) as executor:
	threads = []
	for i in range(numThreads):
		threads.append(executor.submit(do_something))

	for thread in concurrent.futures.as_completed(threads):
		print("{0} threads.".format(len(threads)))
		print("Adding another thread to the pool.")
		threads.append(executor.submit(do_something))
