import numpy
import sqlite3
from scipy import stats

# Build 1437 release
# https://emu.freenetproject.org/pipermail/devl/2013-March/036860.html
epoch = "strftime('%s', '2013-03-22')"

query = """SELECT
             "bulk_request_chk",
             "bulk_request_ssk",
             "bulk_insert_chk",
             "bulk_insert_ssk"
           FROM
             "reject_stats"
           WHERE
             "time" """

def apply_numpy(result, func):
    means = []
    if len(result) > 0:
        for i in xrange(len(result[0])):
            values = numpy.fromiter((entry[i] for entry in result), float, count=-1)
            means.append(getattr(numpy, func)(values, dtype=numpy.float64))
    return means

reject_types = [ "Bulk Request CHK:",
                 "Bulk Request SSK:",
                 "Bulk Insert CHK:",
                 "Bulk Insert SSK:" ]

db = sqlite3.connect("database.sql")

before = db.execute(query + " < " + epoch).fetchall()

before_samples = len(before)

print("Samples before epoch: {0:n}".format(before_samples))

print("---Mean Before---")
for element in zip(reject_types, apply_numpy(before, 'mean')):
    print(element[0] + " {0:n}".format(element[1]))

print("---Standard Deviation Before---")
for element in zip(reject_types, apply_numpy(before, 'std')):
    print(element[0] + " {0:n}".format(element[1]))

after  = db.execute(query + " > " + epoch).fetchall()

after_samples = len(after)

print("Samples after epoch: {0:n}".format(after_samples))

print("---Mean After---")
for element in zip(reject_types, apply_numpy(after, 'mean')):
    print(element[0] + " {0:n}".format(element[1]))

print("---Standard Deviation After---")
for element in zip(reject_types, apply_numpy(before, 'std')):
    print(element[0] + " {0:n}".format(element[1]))

print("---Pooled Two-Sample t-Test---")

for element in zip(reject_types, range(len(reject_types))):
    i = element[1]
    # Assumption of equal variance checked by the rule of thumb that
    # the ratio between the standard deviations of the sample not exceed
    # about 2.
    test_result = stats.ttest_ind(
        numpy.fromiter((entry[i] for entry in before), int, count=-1),
        numpy.fromiter((entry[i] for entry in after), int, count=-1))
    # SciPy gives two-sided p-value. /2 for one-sided.
    # t-statistic will be positive if the before mean is greater than
    # the after mean:
    # http://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html
    # uses a - b.
    print(element[0] + "t-statistic: {0:n} p-value: {1:n}".format(test_result[0], test_result[1]/2))
