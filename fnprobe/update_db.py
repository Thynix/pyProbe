from ConfigParser import SafeConfigParser
import db
import logging
import sys

# Update the version of the database if it is outdated, or create it if
# it does not exist.

# At least warning because the database initialization logs progress at
# warning. Standard output to provide feedback on the terminal.

logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s",
                    level=logging.INFO, stream=sys.stdout)

parser = SafeConfigParser()
parser.read("database.config")
config = parser.defaults()


def main():
    return db.Database(config)

if __name__ == '__main__':
    main()
