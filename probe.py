from __future__ import division
import exceptions
import random
import datetime
from twisted.internet import protocol
from twisted.internet.task import LoopingCall
import logging
from twisted.application import service
from ConfigParser import SafeConfigParser
from string import split
from twisted.python.log import ILogObserver
from twistedfcp.protocol import FreenetClientProtocol, IdentifiedMessage
from twisted.python import log
from fnprobe import update_db
from fnprobe.db import probeTypes, errorTypes
from psycopg2.tz import LocalTimezone
from twisted.application import internet

__version__ = "0.1"
application = service.Application("pyProbe")

#Log twisted events to Python's standard logging. This will log reconnection
#information at INFO.
application.setComponent(ILogObserver, log.PythonLoggingObserver().emit)

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


def insert(conn, config, probe_type, result, duration, now):
    start = datetime.datetime.utcnow()

    header = result.name
    htl = config['hopsToLive']
    try:
        probe_type_code = getattr(probeTypes, probe_type).value
    except (exceptions.AttributeError):
        logging.error("Could not get type %s", probe_type)
        return

    insertResult(conn.cursor(), header, htl, result, now, duration,
                 probe_type, probe_type_code)

    conn.commit()
    logging.debug("Committed {0} ({1}) in {2}.".format(header, probe_type,
                                                       datetime.datetime.utcnow() - start))


# TODO: Would it make more sense to put some of these arguments in a dictionary?
def insertResult(cur, header, htl, result, now, duration, probe_type,
                 probe_type_code):
    if header == "ProbeError":
        #type should always be defined, but the code might not be.
        code = None
        if CODE in result:
            code = result[CODE]

        if result[LOCAL] == "true":
            local = True
        elif result[LOCAL] == "false":
            local = False
        else:
            # This will result in a constraint violation. Local cannot be null.
            logging.error("Node gave '{0}' as ProbeError Local, "
                          "which is neither 'true' nor 'false'.".format(
                          result[LOCAL]))
            raise ValueError

        error_type = getattr(errorTypes, result[TYPE]).value

        cur.execute("""
        INSERT INTO
          error(time, duration, htl, probe_type, error_type, local, code)
          values(%s, %s, %s, %s, %s, %s, %s)
        """, (now, duration, htl, probe_type_code, error_type, local, code))
    elif header == "ProbeRefused":
        cur.execute("""
        INSERT INTO
          refused(time, duration, htl, probe_type)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, probe_type_code))
    elif probe_type == "BANDWIDTH":
        cur.execute("""
        INSERT INTO
          bandwidth(time, duration, htl, KiB)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, result[BANDWIDTH]))
    elif probe_type == "BUILD":
        cur.execute("""
        INSERT INTO
          build(time, duration, htl, build)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, result[BUILD]))
    elif probe_type == "IDENTIFIER":
        cur.execute("""
        INSERT INTO
          identifier(time, duration, htl, identifier, percent)
          values(%s, %s, %s, %s, %s)
        """, (now, duration, htl, result[PROBE_IDENTIFIER],
              result[UPTIME_PERCENT]))
    elif probe_type == "LINK_LENGTHS":
        lengths = split(result[LINK_LENGTHS], ';')
        cur.execute("""
        INSERT INTO
          peer_count(time, duration, htl, peers)
          values(%s, %s, %s, %s)
        RETURNING
          id
        """, (now, duration, htl, len(lengths)))
        # PostgreSQL does not use OIDs by default, which would be exposed on
        # lastrowid. As a PostgreSQL extension to SQL it can return values from
        # an insert.
        peer_count_id = cur.fetchone()[0]
        for length in lengths:
            cur.execute("""
            INSERT INTO
              link_lengths(length, count_id)
              values(%s, %s)
            """, (length, peer_count_id))
    elif probe_type == "LOCATION":
        cur.execute("""
        INSERT INTO
          location(time, duration, htl, location)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, result[LOCATION]))
    elif probe_type == "REJECT_STATS":
        cur.execute("""
        INSERT INTO
          reject_stats(time, duration, htl, bulk_request_chk, bulk_request_ssk,
                       bulk_insert_chk, bulk_insert_ssk)
          values(%s, %s, %s, %s, %s, %s, %s)
        """, (now, duration, htl, result[REJECT_BULK_REQUEST_CHK],
              result[REJECT_BULK_REQUEST_SSK], result[REJECT_BULK_INSERT_CHK],
              result[REJECT_BULK_INSERT_SSK]))
    elif probe_type == "STORE_SIZE":
        cur.execute("""
        INSERT INTO
          store_size(time, duration, htl, GiB)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, result[STORE_SIZE]))
    elif probe_type == "UPTIME_48H":
        cur.execute("""
        insert into
          uptime_48h(time, duration, htl, percent)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, result[UPTIME_PERCENT]))
    elif probe_type == "UPTIME_7D":
        cur.execute("""
        INSERT INTO
          uptime_7d(time, duration, htl, percent)
          values(%s, %s, %s, %s)
        """, (now, duration, htl, result[UPTIME_PERCENT]))
    else:
        logging.warning("Unrecognized result type '%s'" % probe_type)


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
    class Log:
        def __call__(self, message):
            logging.error(message)

    def __init__(self, config, proto, conn):
        self.sent = datetime.datetime.now(LocalTimezone())
        self.config = config
        self.probeType = random.choice(self.config['types'])
        self.conn = conn
        logging.debug("Sending {0}.".format(self.probeType))

        request = proto.do_session(MakeRequest(self.probeType,
                                               self.config['hopsToLive']),
                                   self)

        request.addErrback(SendHook.Log())

    def __call__(self, message):
        now = datetime.datetime.now(LocalTimezone())
        # TODO: This may be inaccurate or even negative due to time changes.
        # However Python 2 does not have Python 3.3's time.monotonic().
        duration = now - self.sent
        insert(self.conn, self.config, self.probeType, message, duration, now)
        return True


class FCPReconnectingFactory(protocol.ReconnectingClientFactory):
    """A protocol factory that uses FCP."""
    protocol = FreenetClientProtocol

    #Log disconnection and reconnection attempts
    noisy = True

    def __init__(self, config, conn):
        self.config = config
        self.conn = conn

    def buildProtocol(self, _):
        proto = FreenetClientProtocol()
        proto.factory = self
        proto.timeout = self.config['timeout']

        proto.deferred['NodeHello'] = self

        self.sendLoop = LoopingCall(SendHook, self.config, proto, self.conn)

        return proto

    def callback(self, _):
        self.sendLoop.start(self.config['probePeriod'])

    def clientConnectionLost(self, connector, reason):
        logging.warning("Lost connection: {0}".format(reason))
        self.sendLoop.stop()

        #Any connection loss is failure; reconnect.
        protocol.ReconnectingClientFactory.clientConnectionFailed(self,
                                                                  connector,
                                                                  reason)


def main():
    config_parser = SafeConfigParser()
    # Case-sensitive option names.
    config_parser.optionxform = str
    config_parser.read("probe.config")
    config = config_parser.defaults()

    for arg, value in config_parser.items('OVERRIDE'):
        config[arg] = value

    #Convert integer options
    for arg in ["port", "hopsToLive", "probeRate"]:
        config[arg] = int(config[arg])

    #Convert floating point options.
    for arg in ["timeout", "databaseTimeout"]:
        config[arg] = float(config[arg])

    #Convert types list to list
    config['types'] = split(config['types'], ",")

    # Compute probe period. Rate is easier to think about, so it's used in the
    # config file. probeRate is probes/minute. Period is seconds/probe.
    # 60 seconds   1 minute           seconds
    # ---------- * ---------------- = -------
    # 1 minute     probeRate probes   probe
    config['probePeriod'] = 60 / config['probeRate']

    logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s",
                        level=getattr(logging, config['verbosity']),
                        filename=config['logFile'])
    logging.info("Starting up.")

    conn = update_db.main(log_to_stdout=False).add

    return internet.TCPClient(config['host'], config['port'],
                              FCPReconnectingFactory(config, conn))

# Run with twistd: set up application; let it start the reactor.
if __name__ == "__builtin__":
    client = main()
    client.setServiceParent(application)

# Run as a script: complain.
if __name__ == '__main__':
    print('Run this with twistd.')
