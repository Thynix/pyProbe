import Gnuplot
import logging

# Check for empty lists because Gnuplot-py will not plot if there are no entries.

default_width = 900
default_height = 600

reject_types = [ "bulk_request_chk",
                 "bulk_request_ssk",
                 "bulk_insert_chk",
                 "bulk_insert_ssk"  ]

# TODO: Repetitive width, height, filename existence and defaults; using them to initialize. Method annotation?

def CDF(in_list):
    """
    Takes an input list as from a database query: a list of singleton tuples
    of values.

    Returns a sorted version of the list of X values with  a Y value that sums
    to 100 over the list.
    """
    # Appended for each entry - should all add up to 1.
    height = 100.0 / max(1.0, len(in_list))

    # For GNUPlot smooth cumulative to work as intended the input must be sorted.
    # TODO: Might consider avoiding the copy and sorting the list in-place.
    out_list = sorted(in_list)

    # TODO: This is strange. Is there a better way to add an element to each singleton tuple?
    for index in xrange(len(out_list)):
        out_list[index] = [out_list[index][0], height]

    return out_list


def g_init(width, height, filename):
    g = Gnuplot.Gnuplot()
    g('set terminal png size {:n},{:n}'.format(width, height))
    g.set(output=filename)

    return g


def plot_link_length(lengths, width=default_width, height=default_height, filename='plot_link_length.png'):
    if len(lengths) is 0:
        logging.warning("No link lengths to plot.")
        lengths = [[0.01]]

    g = g_init(width, height, filename)
    g('set key off')

    g.title('Link Length Distribution')
    g.xlabel('Link Length (delta location)')
    g.ylabel('Percent links with this length or less')

    g('set logscale x')
    # As location is circular and [0,1), largest difference is 0.5.
    g.set(xrange='[0.00001:0.5]')
    g.set(yrange='[0:100]')

    g.plot(Gnuplot.Data(CDF(lengths), smooth='cumulative'))

def plot_location_dist(locations, width=default_width, height=default_height, filename='plot_location_dist.png'):
    if len(locations) is 0:
        logging.warning("No locations to plot.")
        locations = [[0.5]]

    g = g_init(width, height, filename)
    g('set key off')

    g.title('Location Distribution')
    g.xlabel('Location')
    g.ylabel('Percent nodes with this location or less')

    g.set(xrange='[0:1.0]')
    # TODO: Percentage goes to 100, not 1.
    g.set(yrange='[0:1]')

    g.plot(Gnuplot.Data(CDF(locations), smooth='cumulative'))

def plot_peer_count(counts, width=default_width, height=default_height, filename='plot_peer_count.png'):
    if len(counts) is 0:
        logging.warning("No peer counts to plot.")
        counts = [[0]]

    g = g_init(width, height, filename)
    g('set key off')

    g.title('Peer Count Distribution')
    g.xlabel('Reported Peers')
    g.ylabel('Percent of Reports')

    g('set style data histogram')
    g('set style fill solid border -1')

    # Could mean missing the details of things beyond the bounds.
    g.set(xrange='[1:50]')
    g('set xtics 5')

    g.plot(Gnuplot.Data(counts, with_='boxes'))

def plot_reject_percentages(counts, width=default_width, height=default_height, filename='plot_week_reject.png'):
    assert len(counts) > 0
    for item in counts.iteritems():
        if len(item) is 0:
            logging.warning("No entries for {}.".format(item[0]))
            item[1] = [[0, 0]]

    g = g_init(width, height, filename)

    g.title('Reject Distribution')
    g.xlabel('Reported reject percentage')
    g.ylabel('Percent reports')

    g('set style data histogram')
    g('set logscale x')

    g.set(xrange='[1:100]')
    g.set(yrange='[0:]')

    # Title of each is the database table name, which is the map key.
    g.plot(*[Gnuplot.Data(item[1], title=item[0], with_='lines') for item in counts.iteritems()])

def plot_uptime(uptimes, width=default_width, height=default_height, filename='plot_week_uptime.png'):
    if len(uptimes) is 0:
        logging.warning("No uptimes to plot.")
        uptimes = [[0, 0]]

    g = g_init(width, height, filename)

    g.title('Uptime Distribution')
    g.xlabel('Reported 7-day uptime percentage')
    g.ylabel('Percent reports')

    g('set style data histogram')
    g('set style fill solid border -1')

    g.set(xrange='[0:120]')
    g.set(yrange='[0:]')

    g.plot(Gnuplot.Data(uptimes, with_='boxes'))
