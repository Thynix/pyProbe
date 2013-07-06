from __future__ import division
import random
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
from fnprobe import update_db
from fnprobe.db import probeTypes, errorTypes
from psycopg2.tz import LocalTimezone

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


def insert(cur, args, probe_type, result, duration, now):
    start = datetime.datetime.utcnow()

    header = result.name
    htl = args.hopsToLive

    insertResult(cur, header, htl, result, now, duration, probe_type)

    cur.commit()
    logging.debug("Committed {0} ({1}) in {2}.".format(header, probe_type,
                                                       datetime.datetime.utcnow() - start))


def insertResult(cur, header, htl, result, now, duration, probe_type):
    if header == "ProbeError":
        #type should always be defined, but the code might not be.
        code = None
        if CODE in result:
            code = result[CODE]

        local = None
        if result[LOCAL] == "true":
            local = True
        elif result[LOCAL] == "false":
            local = False
        else:
            logging.error("Node gave '{0}' as ProbeError Local, "
                          "which is neither 'true' nor 'false'.".format(
                          result[LOCAL]))

        error_type = getattr(errorTypes, result[TYPE]).index

        cur.execute("""
        INSERT INTO
          error(time, htl, probe_type, error_type, code, duration, local)
          values(?, ?, ?, ?, ?, ?, ?)
        """, (now, htl, probe_type, error_type, code, duration, local))
    elif header == "ProbeRefused":
        cur.execute("""
        INSERT INTO
          refused(time, htl, probe_type, duration)
          values(?, ?, ?, ?)
        """, (now, htl, probe_type, duration))
    elif probe_type == "BANDWIDTH":
        cur.execute("""
        INSERT INTO
          bandwidth(time, htl, KiB, duration)
          values(?, ?, ?, ?)
        """, (now, htl, result[BANDWIDTH], duration))
    elif probe_type == "BUILD":
        cur.execute(
            "insert into build(time, htl, build, duration) values(?, ?, ?, ?)",
            (now, htl, result[BUILD], duration))
    elif probe_type == "IDENTIFIER":
        cur.execute("""
        INSERT INTO
          identifier(time, htl, identifier, percent, duration)
          values(?, ?, ?, ?, ?)
        """, (now, htl, result[PROBE_IDENTIFIER], result[UPTIME_PERCENT],
              duration))
    elif probe_type == "LINK_LENGTHS":
        lengths = split(result[LINK_LENGTHS], ';')
        cur.execute("""
        INSERT INTO
          peer_count(time, htl, peers, duration)
          values(?, ?, ?, ?)
        RETURNING
          id
        """, (now, htl, len(lengths), duration))
        # PostgreSQL does not use OIDs by default, which would be exposed on
        # lastrowid. As a PostgreSQL extension it can return values from an
        # insert.
        new_id = cur.fetchone()[0]
        for length in lengths:
            cur.execute("""
            INSERT INTO
              link_lengths(time, htl, length, id)
              values(?, ?, ?, ?)
            """, (now, htl, length, new_id))
    elif probe_type == "LOCATION":
        cur.execute("""
        INSERT INTO
          location(time, htl, location, duration)
          values(?, ?, ?, ?)
        """, (now, htl, result[LOCATION], duration))
    elif probe_type == "REJECT_STATS":
        cur.execute("""
        INSERT INTO
          reject_stats(time, htl, bulk_request_chk, bulk_request_ssk,
                       bulk_insert_chk, bulk_insert_ssk)
          values(?, ?, ?, ?, ?, ?)
        """, (now, htl, result[REJECT_BULK_REQUEST_CHK],
              result[REJECT_BULK_REQUEST_SSK], result[REJECT_BULK_INSERT_CHK],
              result[REJECT_BULK_INSERT_SSK]))
    elif probe_type == "STORE_SIZE":
        cur.execute("""
        INSERT INTO
          store_size(time, htl, GiB, duration)
          values(?, ?, ?, ?)
        """, (now, htl, result[STORE_SIZE], duration))
    elif probe_type == "UPTIME_48H":
        cur.execute("""
        insert into
          uptime_48h(time, htl, percent, duration)
          values(?, ?, ?, ?)
        """, (now, htl, result[UPTIME_PERCENT], duration))
    elif probe_type == "UPTIME_7D":
        cur.execute("""
        INSERT INTO
          uptime_7d(time, htl, percent, duration)
          values(?, ?, ?, ?)
        """, (now, htl, result[UPTIME_PERCENT], duration))


class sigint_handler:
    def __init__(self, pool, cur):
        self.pool = pool
        self.cur = cur

    def __call__(self, signum, frame):
        logging.warning("Got signal {0}. Shutting down.".format(signum))
        self.pool.close()
        self.cur.commit()
        signal(SIGINT, SIG_DFL)
        reactor.stop()


#Inactive class for holding arguments in attributes.
class Arguments(object):
    pass


def MakeRequest(ProbeType, HopsToLive):
    return IdentifiedMessage("ProbeRequest",
                             [(TYPE, ProbeType), (HTL, HopsToLive)])


class SendHook:
    """
    Sends a probe of a random type and commits the result to the database.
    """

    def __init__(self, args, proto, database):
        self.sent = datetime.time.monotonic()
        self.args = args
        self.probeType = random.choice(self.args.types)
        self.cur = database.add
        logging.debug("Sending {0}.".format(self.probeType))

        proto.do_session(MakeRequest(self.probeType, self.args.hopsToLive),
                         self)

    def __call__(self, message):
        duration = datetime.timedelta(seconds=datetime.time.monotonic() -
                                      self.sent)
        now = datetime.datetime.now(LocalTimezone)
        probe_type_code = getattr(probeTypes, self.probeType).index
        insert(self.cur, self.args, probe_type_code, message, duration, now)
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
    """A protocol factory that uses FCP."""
    protocol = FreenetClientProtocol

    #Log disconnection and reconnection attempts
    noisy = True

    def __init__(self, args, cur):
        self.args = args
        self.cur = cur

    def buildProtocol(self, addr):
        proto = FreenetClientProtocol()
        proto.factory = self
        proto.timeout = self.args.timeout

        proto.deferred['NodeHello'] = self
        proto.deferred['ProtocolError'] = Complain()

        self.sendLoop = LoopingCall(SendHook, self.args, proto, self.cur)

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

    # TODO: Config as dictionary
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

    cur = update_db.main().add

    reactor.connectTCP(args.host, args.port,
                       FCPReconnectingFactory(args, cur))

#run main if run with twistd: it will start the reactor.
if __name__ == "__builtin__":
    main()

#Run main and start reactor if run as script
if __name__ == '__main__':
    main()
    reactor.run()
