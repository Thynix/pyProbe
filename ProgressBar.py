# A Python Library to create a Progress Bar.
# Copyright (C) 2008  BJ Dierkes <wdierkes@5dollarwhitebox.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# This class is an improvement from the original found at:
#
#   http://code.activestate.com/recipes/168639/
# 
# This version is based off of the version available at:
#
#   http://www.5dollarwhitebox.org/drupal/node/65
#
 
import sys,os
 
class ProgressBar:
    def __init__(self, min_value = 0, max_value = 100, width=73,**kwargs):
        self.char = kwargs.get('char', '#')
        self.mode = kwargs.get('mode', 'dynamic') # fixed or dynamic
        if not self.mode in ['fixed', 'dynamic']:
            self.mode = 'fixed'
 
        self.bar = ''
        self.min = min_value
        self.max = max_value
        self.span = max_value - min_value
        self.width = width
        self.amount = 0       # When amount == max, we are 100% done 
        self.prev_num_hashes = -1
        self.visually_changed = False
        self.update_amount(0)
 
 
    def increment_amount(self, add_amount = 1):
        """
        Increment self.amount by 'add_ammount' or default to incrementing
        by 1, and then rebuild the bar string. 
        """
        new_amount = self.amount + add_amount
        if new_amount < self.min: new_amount = self.min
        if new_amount > self.max: new_amount = self.max
        self.amount = new_amount
        self.build_bar()
 
 
    def update_amount(self, new_amount = None):
        """
        Update self.amount with 'new_amount', and then rebuild the bar 
        string.
        """
        if not new_amount: new_amount = self.amount
        if new_amount < self.min: new_amount = self.min
        if new_amount > self.max: new_amount = self.max
        self.amount = new_amount
        self.build_bar()
 
 
    def build_bar(self):
        """
        Figure new percent complete, and rebuild the bar string base on 
        self.amount.
        """
        diff = float(self.amount - self.min)
        percent_done = int(round((diff / float(self.span)) * 100.0))
 
        # figure the proper number of 'character' make up the bar 
        all_full = self.width - 2
        num_hashes = int(round((percent_done * all_full) / 100))

	if self.prev_num_hashes == num_hashes:
            return
        
        self.visually_changed = True
        self.prev_num_hashes = num_hashes
        
        if self.mode == 'dynamic':
            # build a progress bar with self.char (to create a dynamic bar
            # where the percent string moves along with the bar progress.
            self.bar = self.char * num_hashes
        else:
            # build a progress bar with self.char and spaces (to create a 
            # fixe bar (the percent string doesn't move)
            self.bar = self.char * num_hashes + ' ' * (all_full-num_hashes)
 
        percent_str = str(percent_done) + "%"
        self.bar = '[ ' + self.bar + ' ] ' + percent_str
 
 
    def __str__(self):
        return str(self.bar)
 
    def print_changed(self):
        if self.visually_changed:
            print self, "\r",
            sys.stdout.flush()
            self.visually_changed = False
 
def main():
    print
    limit = 1000000
 
    print 'Example 1: Fixed Bar'
    prog = ProgressBar(0, limit, mode='fixed')
    for i in xrange(limit+1):
        prog.update_amount(i)
        prog.print_changed()
 
    print '\n\n'
 
    print 'Example 2: Dynamic Bar'
    prog = ProgressBar(0, limit, mode='dynamic', char='-')
    for i in xrange(limit+1):
        prog.increment_amount()
        prog.print_changed()
 
    print '\n\n'
 
 
if __name__ == '__main__':
    main()
