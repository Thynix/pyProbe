from ConfigParser import SafeConfigParser
import db
import logging
import sys

# Update the version of the database if it is outdated, or create it if
# it does not exist.


def main(log_to_stdout=True):
    # At least warning because the database initialization logs progress at
    # warning. Standard output to provide feedback on the terminal.
    if log_to_stdout:
        logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s",
                            level=logging.INFO, stream=sys.stdout)

    parser = SafeConfigParser()
    parser.read("database.config")
    config = parser.defaults()

    return db.Database(config)

if __name__ == '__main__':
    main()
