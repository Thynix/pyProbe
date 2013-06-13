from __future__ import division
import random
import sqlite3
import datetime
from sys import stderr
from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall
from signal import signal, SIGINT, SIG_DFL
import thread
import logging
from twisted.application import service
from ConfigParser import SafeConfigParser
from string import split
from twistedfcp.protocol import FreenetClientProtocol, IdentifiedMessage
from twisted.python import log
from fnprobe.db import Database, probeTypes, errorTypes
from fnprobe.time import toPosix, totalSeconds
from dateutil.tz import tzlocal

__version__ = "0.1"
application = service.Application("pyProbe")

#Log twisted events to Python's standard logging. This will log reconnection
#information at INFO.
log.PythonLoggingObserver().start()

#Which random generator to use.
rand = random.SystemRandom()

#FCP Message fields
BANDWIDTH = "OutputBandwidth"
BUILD = "Build"
CODE = "Code"
PROBE_IDENTIFIER = "ProbeIdentifier"
UPTIME_PERCENT = "UptimePercent"
LINK_LENGTHS = "LinkLengths"
LOCATION = "Location"
REJECT_BULK_REQUEST_CHK = "Rejects.Bulk.Request.CHK"
REJECT_BULK_REQUEST_SSK = "Rejects.Bulk.Request.SSK"
REJECT_BULK_INSERT_CHK = "Rejects.Bulk.Insert.CHK"
REJECT_BULK_INSERT_SSK = "Rejects.Bulk.Insert.SSK"
STORE_SIZE = "StoreSize"
TYPE = "Type"
HTL = "HopsToLive"
LOCAL = "Local"


def insert(db, args, probe_type, result, duration, now):
    start = datetime.datetime.utcnow()

    header = result.name
    htl = args.hopsToLive

    # Retry insert on locking timeout.
    tries = 0
    success = False
    while not success:
        try:
            insertResult(db, header, htl, result, now, duration, probe_type)
            success = True
        except sqlite3.OperationalError as ex:
            # Database locked. Try again.
            db.rollback()
            logging.warning(
                "Got operational error '{0}'. Tried {1} times before. Retrying.".format(
                    ex, tries))
            tries += 1

    db.commit()
    logging.debug("Committed {0} ({1}) in {2}.".format(header, probe_type,
                                                       datetime.datetime.utcnow() - start))


def insertResult(db, header, htl, result, now, duration, probe_type):
    if header == "ProbeError":
        #type should always be defined, but the code might not be.
        code = None
        if CODE in result:
            code = result[CODE]

        local = 0
        if result[LOCAL] == "true":
            local = 1
        elif result[LOCAL] == "false":
            local = 0
        else:
            logging.error("Node gave '{0}' as ProbeError Local, "
                          "which is neither 'true' nor 'false'.".format(
                result[LOCAL]))

        error_type = getattr(errorTypes, result[TYPE]).index

        db.execute(
            "insert into error(time, htl, probe_type, error_type, code, duration, local) values(?, ?, ?, ?, ?, ?, ?)",
            (now, htl, probe_type, error_type, code, duration, local))
    elif header == "ProbeRefused":
        db.execute(
            "insert into refused(time, htl, probe_type, duration) values(?, ?, ?, ?)",
            (now, htl, probe_type, duration))
    elif probe_type == "BANDWIDTH":
        db.execute(
            "insert into bandwidth(time, htl, KiB, duration) values(?, ?, ?, ?)",
            (now, htl, result[BANDWIDTH], duration))
    elif probe_type == "BUILD":
        db.execute(
            "insert into build(time, htl, build, duration) values(?, ?, ?, ?)",
            (now, htl, result[BUILD], duration))
    elif probe_type == "IDENTIFIER":
        db.execute(
            "insert into identifier(time, htl, identifier, percent, duration) values(?, ?, ?, ?, ?)",
            (now, htl, result[PROBE_IDENTIFIER], result[UPTIME_PERCENT],
             duration))
    elif probe_type == "LINK_LENGTHS":
        cur = db.cursor()
        lengths = split(result[LINK_LENGTHS], ';')
        cur.execute(
            "insert into peer_count(time, htl, peers, duration) values(?, ?, ?, ?)",
            (now, htl, len(lengths), duration))
        new_id = cur.lastrowid
        for length in lengths:
            cur.execute(
                "insert into link_lengths(time, htl, length, id) values(?, ?, ?, ?)",
                (now, htl, length, new_id))
        cur.close()
    elif probe_type == "LOCATION":
        db.execute(
            "insert into location(time, htl, location, duration) values(?, ?, ?, ?)",
            (now, htl, result[LOCATION], duration))
    elif probe_type == "REJECT_STATS":
        db.execute(
            "insert into reject_stats(time, htl, bulk_request_chk, bulk_request_ssk, bulk_insert_chk, bulk_insert_ssk) values(?, ?, ?, ?, ?, ?)",
            (now, htl, result[REJECT_BULK_REQUEST_CHK],
             result[REJECT_BULK_REQUEST_SSK], result[REJECT_BULK_INSERT_CHK],
             result[REJECT_BULK_INSERT_SSK]))
    elif probe_type == "STORE_SIZE":
        db.execute(
            "insert into store_size(time, htl, GiB, duration) values(?, ?, ?, ?)",
            (now, htl, result[STORE_SIZE], duration))
    elif probe_type == "UPTIME_48H":
        db.execute(
            "insert into uptime_48h(time, htl, percent, duration) values(?, ?, ?, ?)",
            (now, htl, result[UPTIME_PERCENT], duration))
    elif probe_type == "UPTIME_7D":
        db.execute(
            "insert into uptime_7d(time, htl, percent, duration) values(?, ?, ?, ?)",
            (now, htl, result[UPTIME_PERCENT], duration))


class sigint_handler:
    def __init__(self, pool):
        self.pool = pool

    def __call__(self, signum, frame):
        logging.warning("Got signal {0}. Shutting down.".format(signum))
        self.pool.close()
        signal(SIGINT, SIG_DFL)
        reactor.stop()

#Inactive class for holding arguments in attributes.
class Arguments(object):
    pass


def MakeRequest(ProbeType, HopsToLive):
    return IdentifiedMessage("ProbeRequest", \
                             [(TYPE, ProbeType), (HTL, HopsToLive)])


class SendHook:
    """
	Sends a probe of a random type and commits the result to the database.
	"""

    def __init__(self, args, proto, database):
        self.sent = datetime.datetime.utcnow()
        self.args = args
        self.probeType = random.choice(self.args.types)
        self.db = database.get_connection()
        logging.debug("Sending {0}.".format(self.probeType))

        proto.do_session(MakeRequest(self.probeType, self.args.hopsToLive),
                         self)

    def __call__(self, message):
        delta = datetime.datetime.utcnow() - self.sent
        duration = totalSeconds(delta)
        now = toPosix(datetime.datetime.utcnow())
        probe_type_code = getattr(probeTypes, self.probeType).index
        insert(self.db, self.args, probe_type_code, message, duration, now)
        return True


class Complain:
    """
	Registered on ProtocolError. If the callback is hit, complains loudly
	and exits, as it's an indication that probes are not supported on the
	target node.
	"""

    def callback(self, message):
        errStr = "Got ProtocolError - node does not support probes."
        logging.error(errStr)
        stderr.write(errStr + '\n')
        thread.interrupt_main()


class FCPReconnectingFactory(protocol.ReconnectingClientFactory):
    "A protocol factory that uses FCP."
    protocol = FreenetClientProtocol

    #Log disconnection and reconnection attempts
    noisy = True

    def __init__(self, args, database):
        self.args = args
        self.database = database

    def buildProtocol(self, addr):
        proto = FreenetClientProtocol()
        proto.factory = self
        proto.timeout = self.args.timeout

        proto.deferred['NodeHello'] = self
        proto.deferred['ProtocolError'] = Complain()

        self.sendLoop = LoopingCall(SendHook, self.args, proto, self.database)

        return proto

    def callback(self, message):
        self.sendLoop.start(self.args.probePeriod)

    def clientConnectionLost(self, connector, reason):
        logging.warning("Lost connection: {0}".format(reason))
        self.sendLoop.stop()

        #Any connection loss is failure; reconnect.
        protocol.ReconnectingClientFactory.clientConnectionFailed(self,
                                                                  connector,
                                                                  reason)


def main():
    config = SafeConfigParser()
    #Case-sensitive to set args attributes correctly.
    config.optionxform = str
    config.read("probe.config")
    defaults = config.defaults()

    def get(option):
        return config.get("OVERRIDE", option) or defaults[option]

    args = Arguments()
    for arg in defaults.keys():
        setattr(args, arg, get(arg))

    #Convert integer options
    for arg in ["port", "hopsToLive", "probeRate"]:
        setattr(args, arg, int(getattr(args, arg)))

    #Convert floating point options.
    for arg in ["timeout", "databaseTimeout"]:
        setattr(args, arg, float(getattr(args, arg)))

    #Convert types list to list
    args.types = split(args.types, ",")

    # Compute probe period. Rate is easier to think about, so it's used in the
    # config file. probeRate is probes/minute. Period is seconds/probe.
    # 60 seconds   1 minute           seconds
    # ---------- * ---------------- = -------
    # 1 minute     probeRate probes   probe
    args.probePeriod = 60 / args.probeRate

    logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s",
                        level=getattr(logging, args.verbosity),
                        filename=args.logFile)
    logging.info("Starting up.")

    database = Database(args.databaseFile)

    reactor.connectTCP(args.host, args.port,
                       FCPReconnectingFactory(args, database))

#run main if run with twistd: it will start the reactor.
if __name__ == "__builtin__":
    main()

#Run main and start reactor if run as script
if __name__ == '__main__':
    main()
    reactor.run()
