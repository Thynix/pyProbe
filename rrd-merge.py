from xml.etree.ElementTree import Element, ElementTree, SubElement, parse
from sys import argv, exit

# Takes RRDTool XML files on the command line. The last one should not exist
# and is written to as the merged version of the previous.
# The first file to contain a data source is used as its source for the merged
# version. All files must contain the same RRAs.

# Destination file - last argument
destinationPath = argv[-1]
try:
    with open(destinationPath, 'r') as destination:
        print("Destination file '{0}' already exists. Refusing to overwrite.".format(destinationPath))
        exit(1)
except IOError:
    # Okay - destination file should not exist.
    pass

# TODO: Race condition between checking if the file exists and opening it for writing.

# Holds <version/>, <step/>, and <lastupdate/> - the first elements of <rrd/>.
prelude = None

# Keyed by data source name.
# Value is a tuple of the root element and the index of the data source in its tree.
dataSources = dict()

# Every file should have the same <rrd>s as the first.
# For every <rrd/>:
#   Check the same: <cf/> <pdp_per_row/> <params><xff/></params>
#   Check the same number of elements: <database/>
rras = None

# TODO: Should this go in a module?
def getRraCheck(root):
    rras = []
    for rra in root.findall('rra'):
        rras.append((   rra.find('cf').text,
                        rra.find('pdp_per_row').text,
                        rra.find('params').find('xff').text,
                        len(rra.find('database').findall('row'))
                   ))

    return rras

# All command line arguments but the last are input. Read them in.
# Ensure the RRAs are the same.
for inFile in argv[1:-1]:
    print("Reading {0}.".format(inFile))
    root = parse(inFile).getroot()

    # Check the RRAs. No elements means first file.
    if rras == None:
        rras = getRraCheck(root)
        prelude = dict()
        for key in [ 'version', 'step', 'lastupdate' ]:
            prelude[key] = root.find(key).text

        print("Using from the first file: {0}".format(prelude))
    else:
        # Otherwise other files should match.
        if not getRraCheck(root) == rras:
            print("RRAs in '{0}' differ from those in '{1}'.".format(inFile, argv[0]))
            exit(2)

    # Find the data sources in each file.
    # Use each occurrence from the first file it appears in.
    # Index is which of the data sources in the file is used.
    index = 0
    for dataSource in [ ds.find('name').text for ds in root.findall('ds') ]:
        if dataSource not in dataSources:
            print("Using '{0}' from '{1}'.".format(dataSource, inFile))

            dataSources[dataSource] = (index, root)

        index += 1

# Build new XML file.
out = Element('rrd')

# Add header elements.
for item in prelude.iteritems():
    # Key is tag.
    element = Element(item[0])
    # Value is text.
    element.text = item[1]
    out.append(element)

# Though dataSources is a dictionary, as no further modifications are made to it
# iteration over its pairs will be consistent. This is important as the order of
# the data source definitions must match that of the values in the RRA rows.
# See http://docs.python.org/2/library/stdtypes.html#dict.items

# Copy top-level data source definitions.
for entry in dataSources.itervalues():
    dsRoot = entry[1]
    dsIndex = entry[0]
    out.append(dsRoot.findall('ds')[dsIndex])
  
# Copy RRAs; get values from each.
rraIndex = 0
for rra in rras:
    element = SubElement(out, 'rra')

    # Last element in rra is number of rows, not tag.
    # Add RRA descriptions.
    SubElement(element, 'cf').text = rra[0]
    SubElement(element, 'pdp_per_row').text = rra[1]
    SubElement(SubElement(element, 'params'), 'xff').text = rra[2]

    database = SubElement(element, 'database')

    # Build list of lists of elements for each DS:
    # Get list of rows out of this RRA for each ds.
    # Select the values for each ds out of the row.
    rows = []
    for ds in dataSources.itervalues():
        dsRoot = ds[1]
        dsIndex = ds[0]

        rows.append(map(lambda row: row[dsIndex].text,
                    dsRoot.findall('rra')[rraIndex].find('database').findall('row')))
    
    # Change from list of lists of values to list of tuples of the same row.
    for row in zip(*rows):
        rowElement = SubElement(database, 'row')
        for value in row:
            SubElement(rowElement, 'v').text = value

    rraIndex += 1

ElementTree(out).write(destinationPath)
